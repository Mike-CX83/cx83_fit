"""Bounded reviewed CSV summaries in the application's documented format."""
import csv
import io
import json
import hashlib
import re
from uuid import UUID, uuid5

from django.db import transaction, IntegrityError, OperationalError

from .domain import InvalidMeasurement
from .imports import validate_namespace
from .models import SummaryRecord, SummaryCorrection, WriteRequest
from .services import Conflict, _owner
from .summaries import validate_summary, serialize_summary

MAX_BYTES = 262144
MAX_ROWS = 200
HEADER = ('source_record_id', 'kind', 'local_date', 'source_timezone', 'completeness', 'synthetic', 'values', 'device', 'notes')
REQUIRED = set(HEADER[:-2])
SOURCE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}', re.ASCII)


def _clean_rows(namespace, rows):
    namespace = validate_namespace(namespace)
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise InvalidMeasurement('Import 1 to 200 summary rows.')
    cleaned, ids, days = [], set(), set()
    for number, row in enumerate(rows, 2):
        if not isinstance(row, dict) or set(row) != {'source_record_id', 'summary'} or not isinstance(row['summary'], dict):
            raise InvalidMeasurement(f'CSV row {number}: invalid summary structure.')
        source_id = row['source_record_id']
        if not isinstance(source_id, str) or not SOURCE_ID.fullmatch(source_id):
            raise InvalidMeasurement(f'CSV row {number}: invalid source record ID.')
        clean = validate_summary({**row['summary'], 'source_system': namespace})
        key = (clean['kind'], source_id)
        day_key = (clean['kind'], clean['local_date'])
        if key in ids or (clean['kind'] != 'health' and day_key in days):
            raise InvalidMeasurement(f'CSV row {number}: duplicate source ID or daily summary in this file.')
        ids.add(key); days.add(day_key)
        clean['source_system'] = 'csv:' + namespace
        cleaned.append({'source_record_id': source_id, 'summary': clean})
    return cleaned


def parse_summary_csv(content):
    if not isinstance(content, bytes) or len(content) > MAX_BYTES:
        raise InvalidMeasurement('Summary CSV must be at most 256 KiB.')
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise InvalidMeasurement('Summary CSV must use UTF-8.') from None
    if '\0' in text:
        raise InvalidMeasurement('Summary CSV cannot contain NUL characters.')
    rows = []
    try:
        reader = csv.reader(io.StringIO(text, newline=''), strict=True)
        header = next(reader, [])
        if not REQUIRED <= set(header) or set(header) - set(HEADER) or len(set(header)) != len(header):
            raise InvalidMeasurement('Use the documented summary CSV headers without duplicates.')
        for number, fields in enumerate(reader, 2):
            if len(rows) >= MAX_ROWS or len(fields) != len(header):
                raise InvalidMeasurement(f'CSV row {number}: invalid column count or more than 200 rows.')
            row = dict(zip(header, fields))
            if row['synthetic'] not in {'true', 'false'}:
                raise InvalidMeasurement(f'CSV row {number}: synthetic must be true or false.')
            try:
                values = json.loads(row['values'])
            except (ValueError, RecursionError):
                raise InvalidMeasurement(f'CSV row {number}: values must contain a supported JSON object.') from None
            rows.append({'source_record_id': row['source_record_id'], 'summary': {
                'kind': row['kind'], 'local_date': row['local_date'], 'source_timezone': row['source_timezone'],
                'completeness': row['completeness'], 'synthetic': row['synthetic'] == 'true',
                'values': values, 'device': row.get('device', ''), 'notes': row.get('notes', '')}})
        # JSON-safe canonical rows for server-side review. The real namespace is supplied separately.
        cleaned = _clean_rows('reviewed-csv', rows)
        for row in cleaned:
            row['summary'].pop('source_system')
            row['summary']['local_date'] = row['summary']['local_date'].isoformat()
        return cleaned
    except csv.Error:
        raise InvalidMeasurement('Malformed summary CSV.') from None


def _classify(owner, rows):
    result = []
    for row in rows:
        data = row['summary']
        record = SummaryRecord.objects.filter(owner=owner, kind=data['kind'], source_system=data['source_system'],
                                               source_record_id=row['source_record_id']).first()
        daily = SummaryRecord.objects.filter(owner=owner, kind=data['kind'], source_system=data['source_system'],
                                              local_date=data['local_date']).first() if data['kind'] != 'health' else None
        if record is None and daily is None:
            status, reason = 'new', 'Ready to import.'
        elif record is None or (daily and daily.id != record.id):
            status, reason = 'conflict', 'A different source record already covers this date.'
        elif record.deleted_at is not None:
            status, reason = 'conflict', 'This source record was deleted.'
        elif record.entry_method != 'imported' or any(getattr(record, key) != value for key, value in data.items()):
            status, reason = 'conflict', 'This source ID already exists with different values.'
        else:
            status, reason = 'skip', 'Identical record already stored; it will be skipped.'
        result.append({**row, 'record': record, 'status': status, 'reason': reason})
    return result


def preview_summaries(owner, namespace, rows):
    _owner(owner)
    return [{key: value for key, value in row.items() if key != 'record'}
            for row in _classify(owner, _clean_rows(namespace, rows))]


def confirm_summaries(owner, namespace, rows, batch_id):
    from .domain import request_uuid
    _owner(owner)
    rows = _clean_rows(namespace, rows)
    batch_id = request_uuid(batch_id)
    digest = hashlib.sha256(json.dumps({'operation': 'summary_csv', 'rows': rows}, sort_keys=True, default=str).encode()).hexdigest()
    try:
        with transaction.atomic():
            prior = WriteRequest.objects.filter(owner=owner, request_id=batch_id).first()
            if prior and prior.payload_hash != digest:
                raise Conflict('This confirmation was already used with different content.')
            classified = _classify(owner, rows)
            if any(row['status'] == 'conflict' for row in classified):
                raise Conflict('Import blocked by a changed, conflicting or deleted source record. No rows were added.')
            if prior:
                if any(row['status'] != 'skip' for row in classified):
                    raise Conflict('A prior import cannot recreate missing records.')
                return prior.response
            receipt = WriteRequest.objects.create(owner=owner, request_id=batch_id, payload_hash=digest)
            result = {'created': 0, 'skipped': 0, 'record_ids': []}
            for row in classified:
                record = row['record']
                if row['status'] == 'skip':
                    result['skipped'] += 1
                else:
                    row_id = uuid5(UUID(batch_id), json.dumps(['summary', row['summary']['kind'], row['source_record_id']]))
                    row_request = WriteRequest.objects.create(owner=owner, request_id=row_id,
                        payload_hash=hashlib.sha256(json.dumps(row['summary'], sort_keys=True, default=str).encode()).hexdigest())
                    record = SummaryRecord.objects.create(owner=owner, source_record_id=row['source_record_id'],
                                                           entry_method='imported', **row['summary'])
                    snapshot = serialize_summary(record)
                    SummaryCorrection.objects.create(record=record, request=row_request, before=None, after=snapshot)
                    row_request.response = snapshot; row_request.save(update_fields=['response'])
                    result['created'] += 1
                result['record_ids'].append(str(record.id))
            receipt.response = result; receipt.save(update_fields=['response'])
            return result
    except (IntegrityError, OperationalError):
        raise Conflict('Storage is busy or a source record conflicts. Retry the same confirmation.') from None
