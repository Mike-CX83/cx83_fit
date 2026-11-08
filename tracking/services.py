"""Shared browser and MCP operations. Callers must authenticate and authorize first."""
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from .domain import InvalidMeasurement, bounded_range, request_uuid, validate_measurement
from .models import Correction, Measurement, WriteRequest


class Conflict(ValueError):
    pass


class RecordNotFound(ValueError):
    pass


def _json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    raise TypeError("Unsupported value")


def serialize(record):
    fields = ("id", "metric", "value", "unit", "side", "location", "local_date", "observed_at",
              "source_timezone", "source_system", "source_record_id", "entry_method", "notes",
              "synthetic", "version", "imported_at", "created_at", "updated_at", "deleted_at")
    return json.loads(json.dumps({k: getattr(record, k) for k in fields}, default=_json_value))


def _owner(owner):
    if not owner or not owner.is_authenticated or not owner.is_active or not owner.pk:
        raise PermissionError("An active authenticated owner is required.")


def _replay(owner, request_id, digest):
    existing = WriteRequest.objects.filter(owner=owner, request_id=request_id).first()
    if existing:
        if existing.payload_hash != digest:
            raise Conflict("This request_id was already used with different content.")
        return existing.response
    return None


def put_measurement(owner, payload, request_id, record_id=None, expected_version=None, *, source_system="manual"):
    """Create or correct manual tracking. source_system is set by the trusted caller.

    This is a full replacement of editable fields. source_record_id, original source,
    timestamps and imported values cannot be supplied by an MCP/client payload.
    """
    _owner(owner)
    if source_system not in ("manual", "mcp"):
        raise PermissionError("This operation only accepts manual tracking writes.")
    request_id = request_uuid(request_id)
    clean = validate_measurement(payload)
    if record_id is not None:
        record_id = request_uuid(record_id)
        if type(expected_version) is not int or expected_version < 1:
            raise InvalidMeasurement("A positive expected_version is required for corrections.")
    elif expected_version is not None:
        raise InvalidMeasurement("expected_version is only valid for corrections.")
    canonical = json.dumps({"payload": clean, "record_id": record_id, "expected_version": expected_version,
                            "actor_source": source_system}, default=_json_value, sort_keys=True)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    replay = _replay(owner, request_id, digest)
    if replay is not None:
        return replay
    try:
        with transaction.atomic():
            request = WriteRequest.objects.create(owner=owner, request_id=request_id, payload_hash=digest)
            if record_id:
                record = Measurement.objects.filter(id=record_id, owner=owner, deleted_at__isnull=True).first()
                if record is None:
                    raise RecordNotFound("Measurement not found.")
                if record.source_system not in ("manual", "mcp"):
                    raise PermissionError("Imported source records are read only; add an annotation separately.")
                if record.synthetic != clean["synthetic"]:
                    raise InvalidMeasurement("Synthetic records cannot be converted into personal records.")
                before = serialize(record)
                # SQLite does not implement select_for_update. This compare-and-swap is essential.
                changed = Measurement.objects.filter(id=record_id, owner=owner, version=expected_version,
                                                     deleted_at__isnull=True).update(
                    **clean, version=expected_version + 1, updated_at=timezone.now())
                if changed != 1:
                    raise Conflict("The measurement changed. Read its current version before correcting it.")
                record.refresh_from_db()
                operation = "update"
            else:
                record = Measurement(owner=owner, **clean, source_system=source_system,
                                     source_record_id=request_id, entry_method="manually_reported")
                record.full_clean()
                record.save(force_insert=True)
                before, operation = None, "create"
            result = serialize(record)
            Correction.objects.create(measurement=record, request=request, actor_source=source_system,
                                      operation=operation, before=before, after=result)
            request.response = result
            request.save(update_fields=["response"])
            return result
    except IntegrityError:
        replay = _replay(owner, request_id, digest)
        if replay is not None:
            return replay
        raise Conflict("A conflicting write occurred. Retry the same request_id.") from None
    except OperationalError:
        raise Conflict("Storage is temporarily busy. Retry the same request_id.") from None


def list_measurements(owner, start, end, include_synthetic=False, limit=100, offset=0):
    _owner(owner)
    first, last = bounded_range(start, end)
    if type(include_synthetic) is not bool:
        raise InvalidMeasurement("include_synthetic must be true or false.")
    if type(limit) is not int or not 1 <= limit <= 200 or type(offset) is not int or not 0 <= offset <= 100000:
        raise InvalidMeasurement("Use limit 1 to 200 and offset 0 to 100000.")
    records = Measurement.objects.filter(owner=owner, local_date__range=(first, last), deleted_at__isnull=True)
    if not include_synthetic:
        records = records.filter(synthetic=False)
    count = records.count()
    items = [serialize(x) for x in records[offset:offset + limit]]
    dates = records.order_by().values("local_date").distinct().count()
    return {"items": items, "count": count, "returned": len(items),
            "next_offset": offset + limit if offset + limit < count else None,
            "coverage": {"start": first.isoformat(), "end": last.isoformat(),
                         "days_with_observations": dates, "requested_days": (last - first).days + 1},
            "includes_synthetic": include_synthetic}


def delete_measurement(owner, record_id, expected_version, request_id):
    """Hide an owned record and retain its source tombstone and audit history."""
    _owner(owner)
    record_id, request_id = request_uuid(record_id), request_uuid(request_id)
    if type(expected_version) is not int or expected_version < 1:
        raise InvalidMeasurement('A current version is required for deletion.')
    digest = hashlib.sha256(json.dumps({'operation': 'delete_measurement', 'record_id': record_id,
        'expected_version': expected_version}, sort_keys=True).encode()).hexdigest()
    try:
        with transaction.atomic():
            replay = _replay(owner, request_id, digest)
            if replay is not None:
                return replay
            record = Measurement.objects.filter(owner=owner, id=record_id, deleted_at__isnull=True).first()
            if record is None:
                raise RecordNotFound('Measurement not found.')
            receipt = WriteRequest.objects.create(owner=owner, request_id=request_id, payload_hash=digest)
            before = serialize(record)
            changed = Measurement.objects.filter(owner=owner, id=record_id, version=expected_version,
                deleted_at__isnull=True).update(deleted_at=timezone.now(), version=expected_version+1, updated_at=timezone.now())
            if changed != 1:
                raise Conflict('This measurement changed. Review it before deleting.')
            record.refresh_from_db()
            result = serialize(record)
            Correction.objects.create(measurement=record, request=receipt, actor_source='manual',
                                      operation='delete', before=before, after=result)
            receipt.response = result
            receipt.save(update_fields=['response'])
            return result
    except (IntegrityError, OperationalError):
        raise Conflict('Storage is busy. Retry the same deletion request.') from None
