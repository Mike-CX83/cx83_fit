"""Reviewed CSV persistence. Only authenticated browser callers may use this API.

The browser owns the session-bound preview, expiry and CSRF confirmation. This
module revalidates its stored rows and checks every source ID in one transaction.
Imported originals cannot be overwritten by another upload or manual/MCP write.
"""
import hashlib
import json
import re
from uuid import UUID, uuid5

from django.db import IntegrityError, OperationalError, transaction

from .csv_measurements import MAX_ROWS
from .domain import InvalidMeasurement, request_uuid, validate_measurement
from .models import Correction, Measurement, WriteRequest
from .services import Conflict, _json_value, _owner, serialize


_NAMESPACE = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}", re.ASCII)
_SOURCE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}", re.ASCII)


def validate_namespace(namespace):
    if not isinstance(namespace, str) or not _NAMESPACE.fullmatch(namespace):
        raise InvalidMeasurement(
            "Use a source namespace of 1 to 32 lowercase letters, digits, underscores "
            "or hyphens, starting with a letter or digit.")
    return namespace


def _validated_rows(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise InvalidMeasurement(f"Import 1 to {MAX_ROWS} measurements at a time.")
    clean_rows = []
    seen = set()
    for index, row in enumerate(rows, start=2):
        if not isinstance(row, dict) or set(row) != {"source_record_id", "measurement"}:
            raise InvalidMeasurement(f"CSV row {index}: invalid stored measurement row.")
        source_id = row["source_record_id"]
        if not isinstance(source_id, str) or not _SOURCE_ID.fullmatch(source_id):
            raise InvalidMeasurement(f"CSV row {index}: invalid source record ID.")
        if source_id in seen:
            raise InvalidMeasurement(f"CSV row {index}: duplicate source record ID.")
        payload = row["measurement"]
        if not isinstance(payload, dict) or not {"synthetic", "source_timezone"} <= set(payload):
            raise InvalidMeasurement(f"CSV row {index}: explicit synthetic and source timezone fields are required.")
        try:
            clean = validate_measurement(payload)
        except InvalidMeasurement as exc:
            raise InvalidMeasurement(f"CSV row {index}: {exc}") from None
        except (ArithmeticError, ValueError, TypeError):
            raise InvalidMeasurement(f"CSV row {index}: invalid measurement value.") from None
        clean_rows.append({"source_record_id": source_id, "measurement": clean})
        seen.add(source_id)
    return clean_rows


def _json_safe(value):
    return json.loads(json.dumps(value, default=_json_value))


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=_json_value).encode()).hexdigest()


def _classify(owner, source_system, rows):
    existing = {record.source_record_id: record for record in Measurement.objects.filter(
        owner=owner, source_system=source_system,
        source_record_id__in=[row["source_record_id"] for row in rows])}
    results = []
    for row in rows:
        record = existing.get(row["source_record_id"])
        if record is None:
            status, reason = "new", "Ready to import."
        elif record.deleted_at is not None:
            status, reason = "conflict", "This source ID was deleted. It cannot be imported again."
        elif (record.entry_method != "imported" or
              any(getattr(record, field) != value for field, value in row["measurement"].items())):
            status, reason = "conflict", "This source ID already exists with different values."
        else:
            status, reason = "skip", "Identical measurement already stored; it will be skipped."
        results.append({**row, "status": status, "reason": reason, "record": record})
    return results


def preview_rows(owner, namespace, rows):
    """Classify without creating measurements, requests or audit records."""
    _owner(owner)
    source_system = "csv:" + validate_namespace(namespace)
    classified = _classify(owner, source_system, _validated_rows(rows))
    return [_json_safe({key: value for key, value in row.items() if key != "record"})
            for row in classified]


def confirm_rows(owner, namespace, rows, batch_id):
    """Import all new rows atomically; duplicates skip and any conflict blocks.

    Each new measurement has its own deterministic request and audit event. The
    separate batch receipt makes an exact confirmation retry return the same result.
    Every retry still checks current records, so a tombstone can never be revived.
    """
    _owner(owner)
    namespace = validate_namespace(namespace)
    source_system = "csv:" + namespace
    rows = _validated_rows(rows)
    batch_id = request_uuid(batch_id)
    digest = _digest({"operation": "csv_batch", "source_system": source_system, "rows": rows})
    try:
        with transaction.atomic():
            # SQLite IMMEDIATE transactions serialize competing writers before
            # this read. No select_for_update row-lock semantics are assumed.
            receipt = WriteRequest.objects.filter(owner=owner, request_id=batch_id).first()
            if receipt is not None and receipt.payload_hash != digest:
                raise Conflict("This import confirmation was already used with different content.")
            classified = _classify(owner, source_system, rows)
            if any(row["status"] == "conflict" for row in classified):
                raise Conflict("Import blocked: an existing source ID has changed or was deleted. Review the file again.")
            if receipt is not None:
                if any(row["status"] != "skip" for row in classified):
                    raise Conflict("Previously imported records are unavailable. This batch cannot recreate them.")
                return receipt.response
            receipt = WriteRequest.objects.create(owner=owner, request_id=batch_id, payload_hash=digest)
            result = {"created": 0, "skipped": 0, "record_ids": []}
            for row in classified:
                record = row["record"]
                if row["status"] == "skip":
                    result["skipped"] += 1
                else:
                    row_request_id = uuid5(UUID(batch_id), json.dumps(
                        ["csv_row", namespace, row["source_record_id"]]))
                    request = WriteRequest.objects.create(
                        owner=owner, request_id=row_request_id,
                        payload_hash=_digest({"source_system": source_system,
                                              "source_record_id": row["source_record_id"],
                                              "measurement": row["measurement"]}))
                    record = Measurement(owner=owner, **row["measurement"],
                                         source_system=source_system,
                                         source_record_id=row["source_record_id"],
                                         entry_method="imported")
                    record.full_clean()
                    record.save(force_insert=True)
                    snapshot = serialize(record)
                    Correction.objects.create(measurement=record, request=request,
                                              actor_source=source_system, operation="create",
                                              before=None, after=snapshot)
                    request.response = snapshot
                    request.save(update_fields=["response"])
                    result["created"] += 1
                result["record_ids"].append(str(record.id))
            receipt.response = result
            receipt.save(update_fields=["response"])
            return result
    except IntegrityError:
        raise Conflict("A conflicting import occurred. Retry the same confirmation.") from None
    except OperationalError:
        raise Conflict("Storage is temporarily busy. Retry the same confirmation.") from None
