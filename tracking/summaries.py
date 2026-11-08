"""Dated source summaries, not a food diary, workout logger or medical advice."""
import hashlib
import json
import re
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone

from .domain import InvalidMeasurement, decimal_value, net_carbohydrates, parse_day, request_uuid
from .models import SummaryRecord, SummaryCorrection, WriteRequest
from .services import Conflict, RecordNotFound, _owner

# One fixed schema per first-release module. All numeric fields retain source units.
SCHEMAS = {
    'nutrition': [('calories', 'Calories', 'kcal'), ('protein', 'Protein', 'g'),
                  ('total_carbohydrates', 'Total carbohydrates', 'g'), ('fat', 'Fat', 'g'), ('fiber', 'Fiber', 'g')],
    'recovery': [('sleep_minutes', 'Sleep duration', 'min'), ('hrv_ms', 'HRV', 'ms'),
                 ('resting_hr_bpm', 'Resting heart rate', 'bpm'), ('readiness', 'Source readiness score', '/100')],
    'activity': [('steps', 'Steps', 'steps'), ('workout_minutes', 'Workout duration', 'min')],
    'health': [('value', 'Result', '')],
}
TEXT_FIELDS = {'nutrition': {}, 'recovery': {'hrv_method': 40},
               'activity': {'workout_summary': 500},
               'health': {'name': 120, 'unit': 40, 'reference_range': 160}}
SOURCE = re.compile(r'[a-z0-9][a-z0-9_.-]{0,31}', re.ASCII)


def validate_values(kind, values, device=''):
    if not isinstance(kind, str) or kind not in SCHEMAS or not isinstance(values, dict):
        raise InvalidMeasurement('Choose a supported summary type.')
    allowed = {field for field, _, _ in SCHEMAS[kind]} | set(TEXT_FIELDS[kind])
    if set(values) - allowed:
        raise InvalidMeasurement('Unsupported summary fields.')
    result = {}
    for field, label, unit in SCHEMAS[kind]:
        raw = values.get(field)
        if raw is None or raw == '':
            result[field] = None
            continue
        number = decimal_value(raw)
        if abs(number) > Decimal('999999999') or (kind != 'health' and number < 0):
            raise InvalidMeasurement(f'{label}: value is outside the supported range.')
        places = 6 if kind == 'health' else 3
        if number != number.quantize(Decimal(1).scaleb(-places)):
            raise InvalidMeasurement(f'{label}: use at most {places} decimal places.')
        if field == 'steps' and number != number.to_integral_value():
            raise InvalidMeasurement('Steps must be a whole number.')
        if field == 'readiness' and number > 100:
            raise InvalidMeasurement('Source readiness must be between 0 and 100.')
        result[field] = format(number.normalize(), 'f')
    for field, limit in TEXT_FIELDS[kind].items():
        value = values.get(field, '')
        if not isinstance(value, str) or len(value) > limit:
            raise InvalidMeasurement(f'{field}: text is missing or too long.')
        result[field] = value.strip()
    if all(result[field] is None for field, _, _ in SCHEMAS[kind]):
        raise InvalidMeasurement('Enter at least one reported numeric value. Leave unknown values blank.')
    if kind == 'health' and (not result['name'] or not result['unit']):
        raise InvalidMeasurement('Health results require a name and explicit unit.')
    if kind == 'recovery' and result['hrv_ms'] is not None:
        if result['hrv_method'] not in {'RMSSD', 'SDNN', 'source_unspecified'} or not device:
            raise InvalidMeasurement('HRV requires its device and method (RMSSD, SDNN or source_unspecified).')
    return result


def validate_summary(payload):
    expected = {'kind', 'local_date', 'source_timezone', 'source_system', 'device',
                'completeness', 'values', 'notes', 'synthetic'}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise InvalidMeasurement('Use the complete supported summary fields.')
    kind = payload['kind']
    day = parse_day(payload['local_date'])
    tz = payload['source_timezone']
    try:
        if not isinstance(tz, str) or len(tz) > 64:
            raise ValueError
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise InvalidMeasurement('Use an IANA source timezone.') from None
    source = payload['source_system']
    if not isinstance(source, str) or not SOURCE.fullmatch(source):
        raise InvalidMeasurement('Source must use 1 to 32 lowercase letters, digits, dots, underscores or hyphens.')
    if payload['completeness'] not in dict(SummaryRecord.COMPLETENESS):
        raise InvalidMeasurement('Specify unknown, partial or complete coverage.')
    device, notes, synthetic = payload['device'], payload['notes'], payload['synthetic']
    if not isinstance(device, str) or len(device) > 120 or not isinstance(notes, str) or len(notes) > 2000:
        raise InvalidMeasurement('Device or notes exceed the text limit.')
    if type(synthetic) is not bool:
        raise InvalidMeasurement('Synthetic must be true or false.')
    values = validate_values(kind, payload['values'], device.strip())
    return {**payload, 'local_date': day, 'device': device.strip(), 'values': values}


def serialize_summary(record):
    return {'id': str(record.id), 'kind': record.kind, 'local_date': record.local_date.isoformat(),
            'source_timezone': record.source_timezone, 'source_system': record.source_system,
            'source_record_id': record.source_record_id, 'entry_method': record.entry_method,
            'device': record.device, 'completeness': record.completeness, 'values': record.values,
            'units': {key: (record.values.get('unit') if record.kind == 'health' else unit)
                      for key, label, unit in SCHEMAS[record.kind]},
            'notes': record.notes, 'synthetic': record.synthetic, 'version': record.version,
            'created_at': record.created_at.isoformat(), 'updated_at': record.updated_at.isoformat(),
            'deleted_at': record.deleted_at.isoformat() if record.deleted_at else None}


def put_summary(owner, payload, request_id, record_id=None, expected_version=None):
    _owner(owner)
    clean = validate_summary(payload)
    request_id = request_uuid(request_id)
    if record_id:
        record_id = request_uuid(record_id)
        if type(expected_version) is not int or expected_version < 1:
            raise InvalidMeasurement('A current version is required for corrections.')
    elif expected_version is not None:
        raise InvalidMeasurement('A version is only valid for corrections.')
    digest = hashlib.sha256(json.dumps({'operation': 'manual_summary', 'payload': clean,
        'record_id': record_id, 'expected_version': expected_version}, sort_keys=True, default=str).encode()).hexdigest()
    try:
        with transaction.atomic():
            prior = WriteRequest.objects.filter(owner=owner, request_id=request_id).first()
            if prior:
                if prior.payload_hash != digest:
                    raise Conflict('This request was already used with different content.')
                return prior.response
            receipt = WriteRequest.objects.create(owner=owner, request_id=request_id, payload_hash=digest)
            if record_id:
                record = SummaryRecord.objects.filter(owner=owner, id=record_id, deleted_at__isnull=True).first()
                if not record:
                    raise RecordNotFound('Summary not found.')
                if record.entry_method != 'manually_reported':
                    raise PermissionError('Imported originals are read only.')
                if record.synthetic != clean['synthetic'] or record.kind != clean['kind'] or record.source_system != clean['source_system']:
                    raise InvalidMeasurement('Source, summary type and synthetic status cannot be changed.')
                before = serialize_summary(record)
                changed = SummaryRecord.objects.filter(id=record.id, owner=owner, version=expected_version,
                    deleted_at__isnull=True).update(**clean, version=expected_version+1, updated_at=timezone.now())
                if changed != 1:
                    raise Conflict('This summary changed. Read its current version before correcting it.')
                record.refresh_from_db()
            else:
                before = None
                record = SummaryRecord(owner=owner, source_record_id=request_id, **clean)
                record.save(force_insert=True)
            result = serialize_summary(record)
            SummaryCorrection.objects.create(record=record, request=receipt, before=before, after=result)
            receipt.response = result
            receipt.save(update_fields=['response'])
            return result
    except IntegrityError:
        raise Conflict('A daily summary already exists for this source and date. Correct that entry instead.') from None
    except OperationalError:
        raise Conflict('Storage is busy. Retry the same request.') from None


def display_values(record):
    rows = []
    for field, label, unit in SCHEMAS[record.kind]:
        rows.append({'label': label, 'value': record.values.get(field),
                     'unit': record.values.get('unit', '') if record.kind == 'health' else unit})
    if record.kind == 'nutrition':
        net = net_carbohydrates(record.values.get('total_carbohydrates'), record.values.get('fiber'))
        rows.append({'label': 'Net carbohydrates', 'value': str(net['value']) if net['value'] is not None else None,
                     'unit': 'g', 'status': net['status']})
    return rows


def delete_summary(owner, record_id, expected_version, request_id):
    _owner(owner)
    record_id, request_id = request_uuid(record_id), request_uuid(request_id)
    if type(expected_version) is not int or expected_version < 1:
        raise InvalidMeasurement('A current version is required for deletion.')
    digest = hashlib.sha256(json.dumps({'operation': 'delete_summary', 'record_id': record_id,
        'expected_version': expected_version}, sort_keys=True).encode()).hexdigest()
    try:
        with transaction.atomic():
            prior = WriteRequest.objects.filter(owner=owner, request_id=request_id).first()
            if prior:
                if prior.payload_hash != digest:
                    raise Conflict('This request was already used with different content.')
                return prior.response
            record = SummaryRecord.objects.filter(owner=owner, id=record_id, deleted_at__isnull=True).first()
            if record is None:
                raise RecordNotFound('Summary not found.')
            receipt = WriteRequest.objects.create(owner=owner, request_id=request_id, payload_hash=digest)
            before = serialize_summary(record)
            changed = SummaryRecord.objects.filter(owner=owner, id=record_id, version=expected_version,
                deleted_at__isnull=True).update(deleted_at=timezone.now(), version=expected_version+1, updated_at=timezone.now())
            if changed != 1:
                raise Conflict('This summary changed. Review it before deleting.')
            record.refresh_from_db()
            result = serialize_summary(record)
            SummaryCorrection.objects.create(record=record, request=receipt, before=before, after=result)
            receipt.response = result
            receipt.save(update_fields=['response'])
            return result
    except (IntegrityError, OperationalError):
        raise Conflict('Storage is busy. Retry the same deletion request.') from None
