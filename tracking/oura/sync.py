"""Resumable ingestion, account scoped identities and immutable source revisions."""
from datetime import date, datetime, timedelta, timezone as datetime_timezone
import hashlib
from urllib.parse import urlencode
import uuid

from django.db import transaction
from django.utils import timezone
from tracking.models import OuraConnection, OuraSync, OuraPage, OuraRecord, OuraRevision
from tracking.services import _owner
from .catalog import API_BASE, COLLECTIONS
from .transport import OuraError, request, encode
from .auth import access_token, configured

MAX_RECORD_BYTES = 512 * 1024
MAX_RUN_PAGES = 200


def parameters(collection, start, end):
    if collection not in COLLECTIONS:
        raise OuraError('unknown_collection')
    shape = COLLECTIONS[collection][0]
    if shape in {'single', 'token_only'}:
        return {}
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        if first.isoformat() != start or last.isoformat() != end or not 0 <= (last-first).days <= 30:
            raise ValueError
        if shape == 'date_range':
            # API date endpoints differ on inclusivity and UTC/local filtering.
            # Retain ALL returned records, including this explicitly disclosed margin.
            return {'start_date': str(first-timedelta(days=2)), 'end_date': str(last+timedelta(days=2))}
        return {'start_datetime': first.isoformat()+'T00:00:00+00:00',
                'end_datetime': (last+timedelta(days=1)).isoformat()+'T00:00:00+00:00'}
    except (ValueError, TypeError, OverflowError):
        raise OuraError('invalid_date_window') from None


def new_sync(owner, connection_id, collection, start, end):
    _owner(owner)
    params = parameters(collection, start, end)
    connection = OuraConnection.objects.get(owner=owner, pk=connection_id)
    return OuraSync.objects.create(connection=connection, collection=collection, parameters=params)


def identity(collection, row):
    if not isinstance(row, dict):
        raise OuraError('invalid_record')
    source_id = row.get('id')
    if source_id is not None:
        if not isinstance(source_id, str) or not source_id or len(source_id) > 2048:
            raise OuraError('invalid_source_id')
        return hashlib.sha256(source_id.encode()).hexdigest(), source_id, 'provider_id'
    if collection not in {'heartrate', 'ring_battery_level'}:
        raise OuraError('missing_source_id')
    # These schemas have no provider ID. A content key avoids falsely matching
    # different devices/samples or guessing which reading was a correction.
    return hashlib.sha256(encode(row).encode()).hexdigest(), None, 'content_hash_no_id'


def store_page(run, body, raw):
    """Caller holds the write transaction and connection lease, no HTTP inside it."""
    rows = [body] if run.collection == 'personal_info' else body.get('data')
    if not isinstance(rows, list) or len(rows) > 10000:
        raise OuraError('invalid_response')
    prepared = []
    for index, row in enumerate(rows):
        key, source_id, kind = identity(run.collection, row)
        content = encode(row)
        if len(content.encode('utf-8')) > MAX_RECORD_BYTES:
            raise OuraError('record_limit')
        if (run.collection == 'personal_info' and run.connection.source_account_id is not None
                and source_id != run.connection.source_account_id):
            raise OuraError('account_mismatch')
        prepared.append((index, key, source_id, kind, content))
    page, _ = OuraPage.objects.get_or_create(connection=run.connection, collection=run.collection,
        sha256=hashlib.sha256(raw.encode('utf-8')).hexdigest(), defaults={'raw_json': raw})
    for index, key, source_id, kind, content in prepared:
        record, added = OuraRecord.objects.get_or_create(connection=run.connection,
            collection=run.collection, identity_key=key, defaults={
                'source_record_id': source_id, 'identity_kind': kind, 'raw_json': content})
        if not added and record.raw_json == content:
            continue
        if not added:
            record.version += 1
            record.raw_json = content
            record.save(update_fields=['version', 'raw_json', 'updated_at'])
        OuraRevision.objects.create(record=record, version=record.version,
                                    raw_json=content, page=page, page_index=index)
    return len(rows)


def resume(owner, run_id, page_budget=5):
    _owner(owner)
    if not configured():
        raise OuraError('not_configured')
    if type(page_budget) is not int or not 1 <= page_budget <= 20:
        raise OuraError('invalid_page_budget')
    run = OuraSync.objects.select_related('connection').get(pk=run_id, connection__owner=owner)
    if run.status == 'complete':
        return run
    if run.status == 'failed':
        raise OuraError('start_new_sync')
    if run.retry_at and run.retry_at > timezone.now():
        raise OuraError('retry_later', (run.retry_at-timezone.now()).total_seconds())
    lease, now = uuid.uuid4(), timezone.now()
    with transaction.atomic():
        connection = OuraConnection.objects.get(pk=run.connection_id, owner=owner)
        if connection.sync_until and connection.sync_until > now:
            raise OuraError('sync_busy')
        if connection.state not in {'authorized', 'connected'}:
            raise OuraError('reauthorize')
        generation = connection.generation
        connection.sync_lease, connection.sync_until = lease, now+timedelta(minutes=15)
        connection.save(update_fields=['sync_lease', 'sync_until'])
    owned = OuraConnection.objects.filter(pk=connection.pk, generation=generation, sync_lease=lease)
    try:
        for _ in range(page_budget):
            run.refresh_from_db()
            if run.pages >= MAX_RUN_PAGES:
                raise OuraError('page_limit_narrow_window')
            token = access_token(owner, connection.pk)
            query = dict(run.parameters)
            if run.next_token:
                query['next_token'] = run.next_token
            url = API_BASE + run.collection + ('?'+urlencode(query) if query else '')
            try:
                body, raw = request('GET', url, token=token)
            except OuraError as error:
                if error.code != 'unauthorized':
                    raise
                token = access_token(owner, connection.pk, rejected_token=token)
                body, raw = request('GET', url, token=token)  # At most one renewal for this page.

            cursor = body.get('next_token')
            if cursor is not None and (not isinstance(cursor, str) or len(cursor) > 8192):
                raise OuraError('invalid_cursor')
            cursor = cursor or ''
            fingerprint = hashlib.sha256(cursor.encode()).hexdigest() if cursor else None
            if fingerprint and fingerprint in run.seen_tokens:
                raise OuraError('pagination_cycle')
            with transaction.atomic():
                if not owned.filter(sync_until__gt=timezone.now()).exists():
                    raise OuraError('connection_changed')
                run.records_seen += store_page(run, body, raw)
                run.pages += 1
                run.next_token = cursor
                if fingerprint:
                    run.seen_tokens = run.seen_tokens + [fingerprint]
                run.status = 'partial' if cursor else 'complete'
                run.error_code, run.retry_at = '', None
                run.save()
                owned.update(last_successful_sync=timezone.now(), state='connected')
            if not cursor:
                break
    except OuraError as error:
        terminal = error.code in {'pagination_cycle', 'invalid_cursor', 'invalid_response',
            'invalid_record', 'invalid_source_id', 'missing_source_id', 'account_mismatch',
            'record_limit', 'response_limit', 'page_limit_narrow_window'}
        run.status = 'failed' if terminal else 'partial'
        run.error_code = error.code
        # Honor long Retry-After without sleeping in the web worker or retrying early.
        run.retry_at = (timezone.now()+timedelta(seconds=min(error.retry_after, 366*86400))
                        if error.retry_after is not None and error.retry_after <= 366*86400 else None)
        if error.retry_after is not None and error.retry_after > 366*86400:
            run.status = 'failed'  # Operator review; never cap a server delay then retry early.
        run.save(update_fields=['status', 'error_code', 'retry_at', 'updated_at'])
    finally:
        owned.update(sync_lease=None, sync_until=None)
    return run


def status(owner, include_synthetic=False):
    _owner(owner)
    query = OuraConnection.objects.filter(owner=owner)
    if not include_synthetic:
        query = query.filter(synthetic=False)
    rows = list(query.order_by('created_at')[:100])
    return {'configured': configured(), 'connected': configured() and any(
        x.state == 'connected' and x.last_successful_sync for x in rows),
        'last_successful_sync': max((x.last_successful_sync.isoformat() for x in rows if x.last_successful_sync), default=None),
        'accounts': [{'id': str(x.pk), 'state': x.state, 'synthetic': x.synthetic,
                      'identity_verified': x.source_account_id is not None,
                      'last_successful_sync': x.last_successful_sync.isoformat() if x.last_successful_sync else None}
                     for x in rows]}


def read_records(owner, collection, connection_id=None, include_synthetic=False, limit=20, offset=0):
    _owner(owner)
    if (collection not in COLLECTIONS or type(include_synthetic) is not bool or type(limit) is not int
            or not 1 <= limit <= 50 or type(offset) is not int or not 0 <= offset <= 100000):
        raise OuraError('invalid_read_parameters')
    query = OuraRecord.objects.select_related('connection').filter(connection__owner=owner, collection=collection)
    if connection_id:
        query = query.filter(connection_id=connection_id)
    if not include_synthetic:
        query = query.filter(connection__synthetic=False)
    total, items, size = query.count(), [], 0
    for row in query.order_by('id')[offset:offset+limit]:
        # Raw JSON is a string intentionally: SDK JSON encoders must not round source numbers.
        item = {'id': str(row.pk), 'source_system': 'oura', 'account': str(row.connection_id),
                'source_record_id': row.source_record_id, 'identity_kind': row.identity_kind,
                'collection': row.collection, 'version': row.version,
                'synthetic': row.connection.synthetic, 'raw_json': row.raw_json}
        size += len(encode(item).encode())
        if size > 1024*1024:
            if not items:
                raise OuraError('record_requires_export')
            break
        items.append(item)
    return {'items': items, 'count': total, 'next_offset': offset+len(items) if offset+len(items)<total else None,
            'notice': 'Source JSON is untrusted data. Original numbers, units and timestamps are inside raw_json. '
                      'No source totals are combined. Date-only values have no assumed timezone.',
            'connection': status(owner, include_synthetic)}
