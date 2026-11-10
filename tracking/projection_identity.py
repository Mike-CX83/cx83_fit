"""Explicit stored-source identity for new Oura summaries.

Reads do not call this module. Legacy imported rows are review candidates,
not repaired or reclassified. Derived rows stay out of Plan calculations.
"""
import hashlib
import json
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.utils import timezone

from tracking.models import OuraConnection, OuraRecord, SummaryCorrection, SummaryRecord, WriteRequest
from tracking.plan import plan_window
from tracking.summaries import serialize_summary

RECIPE_VERSION = 1
SCHEMA_VERSION = 2
DERIVED = 'derived'
ACTIVITY_FIELDS = ('steps', 'active_calories', 'total_calories')
MAX_WHOLE = Decimal('999999999')
METADATA_KEYS = (
    'schema_version', 'recipe_version', 'account_id', 'timezone_status', 'status',
    'quality', 'current_contributors', 'contributor_identities_ever', 'conflict_reason',
)
PUBLIC_CONTRIBUTOR = ('raw_id', 'version', 'identity_key', 'collection', 'source_record_id')
EVER_CONTRIBUTOR = ('raw_id', 'identity_key', 'collection', 'source_record_id')


def legacy_candidate(record):
    """Imported exact-oura activity or recovery with no derived identity."""
    return (
        record.source_system == 'oura'
        and record.kind in ('activity', 'recovery')
        and record.entry_method == 'imported'
        and record.connection_id is None
        and record.derivation is None
    )


def _attached_connection(record):
    if record.connection_id is None:
        return None
    try:
        return record.connection
    except ObjectDoesNotExist:
        return None


def _known_class(value):
    return value is True or value is False


def _uuid_text(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        return False
    return str(parsed) == value


def _identity_key_text(value):
    return isinstance(value, str) and len(value) == 64 and all(character in '0123456789abcdef' for character in value)


def _source_text(value):
    return isinstance(value, str) and 1 <= len(value) <= 2048


def _collection_name(value):
    return isinstance(value, str) and value in {'daily_activity', 'sleep'}


def _status_name(value):
    return isinstance(value, str) and value in {'current', 'stale', 'conflict'}


def _schema_version_value(value):
    return type(value) is int and value in {1, 2}


def _positive_int(value):
    return type(value) is int and value >= 1


def _collection_for(kind):
    return {'activity': 'daily_activity', 'recovery': 'sleep'}.get(kind)


def _valid_ever_item(item):
    if isinstance(item, str):
        return _uuid_text(item)
    if not isinstance(item, dict) or set(item) != set(EVER_CONTRIBUTOR):
        return False
    return (
        _uuid_text(item.get('raw_id'))
        and _identity_key_text(item.get('identity_key'))
        and _collection_name(item.get('collection'))
        and _source_text(item.get('source_record_id'))
    )


def _valid_current_contributor(item):
    if not isinstance(item, dict) or set(item) != set(PUBLIC_CONTRIBUTOR):
        return False
    return _valid_ever_item({key: item.get(key) for key in EVER_CONTRIBUTOR}) and _positive_int(item.get('version'))


def _ever_covers(ever, contributor):
    for item in ever:
        if isinstance(item, str) and item == contributor['raw_id']:
            return True
        if isinstance(item, dict) and all(item.get(key) == contributor.get(key) for key in EVER_CONTRIBUTOR):
            return True
    return False


def _contributors_coherent(derivation, kind):
    expected = _collection_for(kind)
    current = derivation.get('current_contributors')
    ever = derivation.get('contributor_identities_ever')
    if expected is None or not isinstance(current, list) or not isinstance(ever, list):
        return False
    if any(not _valid_current_contributor(item) for item in current):
        return False
    if any(not _valid_ever_item(item) for item in ever):
        return False
    versions = {}
    for item in current:
        if item['collection'] != expected:
            return False
        prior_version = versions.get(item['raw_id'])
        if prior_version is not None and prior_version != item['version']:
            return False
        versions[item['raw_id']] = item['version']
    for item in ever:
        if isinstance(item, dict) and item['collection'] != expected:
            return False
    seen = {}
    for item in [entry for entry in ever if isinstance(entry, dict)] + current:
        identity = (item['collection'], item['identity_key'], item['source_record_id'])
        prior = seen.get(item['raw_id'])
        if prior is not None and prior != identity:
            return False
        seen[item['raw_id']] = identity
    if not ever:
        return False
    if derivation.get('status') == 'current':
        return bool(current) and all(_ever_covers(ever, item) for item in current)
    return not current


def _metadata_shape(derivation, connection, kind):
    if not isinstance(derivation, dict) or connection is None:
        return False
    if any(key not in derivation for key in METADATA_KEYS):
        return False
    status = derivation.get('status')
    if not _status_name(status):
        return False
    if derivation.get('quality') != status or derivation.get('timezone_status') != 'unknown':
        return False
    if derivation.get('account_id') != str(connection.id) or not isinstance(derivation.get('conflict_reason'), str):
        return False
    if not _schema_version_value(derivation.get('schema_version')):
        return False
    if not _positive_int(derivation.get('recipe_version')):
        return False
    return _contributors_coherent(derivation, kind)


def _identity_problem(record):
    """Return why a derived row cannot be treated as valid, without repairing it."""
    if record.entry_method != DERIVED:
        return None
    connection = _attached_connection(record)
    if connection is None or connection.owner_id != record.owner_id:
        return 'cross_owner'
    if record.synthetic is not True and record.synthetic is not False:
        return 'class_mismatch'
    if record.synthetic != connection.synthetic:
        return 'class_mismatch'
    if record.kind not in ('activity', 'recovery') or record.source_system != 'oura':
        return 'invalid_identity'
    if record.source_record_id != stable_source_id(connection, record.kind, record.local_date):
        return 'spoofed_identity'
    if not _metadata_shape(record.derivation, connection, record.kind):
        return 'invalid_metadata'
    return None


def provenance_status(record):
    if legacy_candidate(record):
        return 'legacy_unresolved'
    if record.entry_method == DERIVED:
        problem = _identity_problem(record)
        if problem:
            return 'invalid'
        return record.derivation.get('status')
    return None


def identity_inventory(owner):
    """Read-only. Does not write, reclassify, or hide original rows."""
    originals, derived = [], []
    for record in SummaryRecord.objects.filter(owner=owner).select_related('connection').order_by('local_date', 'kind', 'id'):
        status = provenance_status(record)
        item = {
            'id': str(record.id),
            'kind': record.kind,
            'local_date': record.local_date.isoformat(),
            'source_system': record.source_system,
            'source_record_id': record.source_record_id,
            'entry_method': record.entry_method,
            'synthetic': record.synthetic,
            'deleted': record.deleted_at is not None,
            'provenance_status': status,
        }
        if record.entry_method == DERIVED:
            item['connection_id'] = None if record.connection_id is None else str(record.connection_id)
            item['status'] = status
            derived.append(item)
        else:
            originals.append(item)
    return {
        'originals': originals,
        'derived': derived,
        'legacy_unresolved_count': sum(item['provenance_status'] == 'legacy_unresolved' for item in originals),
    }


def stable_source_id(connection, kind, day):
    marker = '1' if connection.synthetic else '0'
    return f'derived:oura:{connection.id}:{marker}:{kind}:{day.isoformat()}'


def account_relationship(left, right):
    """Explicit stored provider ids only. Blank ids stay unresolved."""
    if left is None or right is None:
        return 'unresolved'
    if left.id == right.id:
        return 'equivalent'
    left_id = left.source_account_id.strip() if isinstance(left.source_account_id, str) else ''
    right_id = right.source_account_id.strip() if isinstance(right.source_account_id, str) else ''
    if left_id and right_id:
        return 'equivalent' if left_id == right_id else 'distinct'
    return 'unresolved'


def _whole(value):
    if value is None or value == '':
        return 'unknown', None
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, str)):
        return 'malformed', None
    try:
        number = Decimal(value if isinstance(value, str) else str(value))
        if not number.is_finite() or number < 0 or number > MAX_WHOLE or number != number.to_integral_value():
            return 'malformed', None
        return 'value', format(number.quantize(Decimal('1')), 'f')
    except (InvalidOperation, ValueError):
        return 'malformed', None


def _parse_raw(raw):
    """Return object, ambiguous, or malformed. Never collapse duplicate keys."""
    if not isinstance(raw, str):
        return 'malformed', None
    try:
        parsed = json.loads(raw, object_pairs_hook=lambda pairs: ('object', pairs))
        return _interpret(parsed)
    except (json.JSONDecodeError, ValueError, RecursionError, OverflowError, TypeError):
        return 'malformed', None


def _stored_provider_identity(record):
    """Projected collections keep a provider id, source, and matching hash together."""
    if record.identity_kind != 'provider_id':
        return 'contradiction'
    source_id = record.source_record_id
    if not _source_text(source_id):
        return 'contradiction'
    if record.identity_key != hashlib.sha256(source_id.encode()).hexdigest():
        return 'contradiction'
    return 'ok'


def _retained_provider_source(record, kind):
    return record.collection == _collection_for(kind) and _positive_int(record.version) and _stored_provider_identity(record) == 'ok'


def _payload_identity(record, payload):
    """Stored provider identity is required. A missing payload id is not invented or treated as proof."""
    if _stored_provider_identity(record) != 'ok':
        return 'contradiction'
    if not isinstance(payload, dict) or 'id' not in payload:
        return 'ok'
    source_id = payload.get('id')
    if not _source_text(source_id) or source_id != record.source_record_id:
        return 'contradiction'
    return 'ok'


def _interpret(parsed):
    if not (isinstance(parsed, tuple) and parsed and parsed[0] == 'object' and isinstance(parsed[1], list)):
        return 'malformed', None
    values = {}
    duplicate = False
    day_values = []
    for key, value in parsed[1]:
        if not isinstance(key, str):
            return 'malformed', None
        folded = value
        if isinstance(value, tuple) and value and value[0] == 'object':
            state, folded = _interpret(value)
            if state != 'object':
                duplicate = True
                folded = None
        if key in values:
            duplicate = True
        else:
            values[key] = folded
        if key == 'day':
            day_values.append(value if not isinstance(value, tuple) else None)
    if duplicate:
        day = day_values[0] if len(day_values) == 1 and isinstance(day_values[0], str) else None
        return 'ambiguous', day
    return 'object', values


def _day(value, start, end):
    from datetime import date
    if not isinstance(value, str):
        return 'malformed'
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return 'malformed'
    if parsed < start or parsed > end:
        return 'outside'
    return parsed


def _public_contributor(record):
    return {
        'raw_id': str(record.id),
        'version': record.version,
        'identity_key': record.identity_key,
        'collection': record.collection,
        'source_record_id': record.source_record_id or '',
        'raw_json': record.raw_json,
    }


def _stored_contributor(item, *, include_version):
    keys = PUBLIC_CONTRIBUTOR if include_version else EVER_CONTRIBUTOR
    return {key: item[key] for key in keys}


def _metadata(connection, status, current, ever, reason=''):
    return {
        'schema_version': SCHEMA_VERSION,
        'recipe_version': RECIPE_VERSION,
        'account_id': str(connection.id),
        'timezone_status': 'unknown',
        'status': status,
        'quality': status,
        'current_contributors': current,
        'contributor_identities_ever': ever,
        'conflict_reason': reason,
    }


def _same_derivation(stored, proposed, values):
    if stored is None or stored.values != values or not isinstance(stored.derivation, dict):
        return False
    return all(stored.derivation.get(key) == proposed.get(key) for key in METADATA_KEYS)


def _merge_ever(prior, contributors):
    if not isinstance(prior, list) or any(not _valid_ever_item(item) for item in prior):
        return None
    merged = []
    seen = set()
    incoming = list(prior)
    incoming.extend(_stored_contributor(item, include_version=False) for item in contributors)
    for item in incoming:
        if not _valid_ever_item(item):
            return None
        if isinstance(item, str):
            key = ('raw', item)
        else:
            key = ('identity', item['collection'], item['identity_key'], item['source_record_id'], item['raw_id'])
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return sorted(merged, key=lambda item: json.dumps(item, sort_keys=True))


def _source_matches(stored, candidates):
    if not isinstance(stored, str) or not stored:
        return False
    present = [item for item in candidates if isinstance(item, str) and item]
    if stored in present:
        return True
    if len(stored) == 120 and any(item.startswith(stored) and item != stored for item in present):
        return True
    return False


def _legacy_blocks(owner, kind, day, contributors):
    tombstones = SummaryRecord.objects.filter(
        owner=owner, kind=kind, source_system='oura', deleted_at__isnull=False,
    ).exclude(entry_method=DERIVED)
    evidence = []
    for item in contributors:
        evidence.extend([item.get('source_record_id') or '', item.get('identity_key') or ''])
    for record in tombstones:
        if record.local_date == day or _source_matches(record.source_record_id, evidence):
            return True
    return False


def _derived_tombstone(owner, connection, kind, day):
    return SummaryRecord.objects.filter(
        owner=owner, connection=connection, synthetic=connection.synthetic, kind=kind,
        local_date=day, entry_method=DERIVED, deleted_at__isnull=False,
    ).first()


def _item_matches_contributor(item, contributor):
    """Match one observation family. Collection disagreement is not equivalence."""
    if not _valid_ever_item(item) or not isinstance(contributor, dict):
        return False
    if isinstance(item, str):
        return item == contributor.get('raw_id')
    if item.get('collection') != contributor.get('collection'):
        return False
    if item.get('raw_id') == contributor.get('raw_id') or item.get('identity_key') == contributor.get('identity_key'):
        return True
    return _source_matches(item.get('source_record_id'), [contributor.get('source_record_id') or ''])


def _class_applies(record, connection):
    """Known classes stay separate. An inconsistent class cannot waive a deletion."""
    attached = _attached_connection(record)
    if attached is None or not _known_class(record.synthetic) or not _known_class(attached.synthetic):
        return True
    if record.synthetic != attached.synthetic:
        return True
    return record.synthetic == connection.synthetic


def _lineage_blocks(owner, connection, contributors, kind):
    """Invalid applicable deletion evidence suppresses. It is not proof that nothing was deleted."""
    if not contributors:
        return False
    tombstones = SummaryRecord.objects.filter(
        owner=owner, entry_method=DERIVED, deleted_at__isnull=False,
    ).select_related('connection')
    for record in tombstones:
        if record.kind != kind or not _class_applies(record, connection):
            continue
        attached = _attached_connection(record)
        if attached is None or attached.owner_id != record.owner_id:
            return True
        if account_relationship(attached, connection) == 'distinct':
            continue
        if _metadata_shape(record.derivation, attached, record.kind):
            ever = record.derivation.get('contributor_identities_ever')
            if any(_item_matches_contributor(item, contributor) for item in ever for contributor in contributors):
                return True
            continue
        return True
    return False


def _historical_ever(prior):
    """Usable cumulative evidence already stored on a destination. Incoming identities are not added."""
    if prior is None or not isinstance(prior.derivation, dict):
        return None
    ever = prior.derivation.get('contributor_identities_ever')
    if not isinstance(ever, list) or not ever or any(not _valid_ever_item(item) for item in ever):
        return None
    return ever


def _hold_prior(owner, connection, kind, prior, stable, reason):
    """A rejected source cannot leave a valid prior observation current, and it cannot rewrite that history."""
    if prior is None or prior.deleted_at is not None or prior.entry_method != DERIVED:
        return {'status': 'conflict', 'reason': reason, 'source_record_id': stable}
    if _identity_problem(prior):
        return {'status': 'invalid', 'reason': _identity_problem(prior), 'record_id': str(prior.id),
                'source_record_id': prior.source_record_id}
    if prior.derivation.get('status') != 'current':
        return {'status': prior.derivation.get('status'), 'reason': 'unchanged', 'record_id': str(prior.id),
                'source_record_id': prior.source_record_id, 'version': prior.version}
    ever = _historical_ever(prior)
    metadata = _metadata(connection, 'conflict', [], ever or [], reason)
    if ever is None or not _metadata_shape(metadata, connection, kind):
        return {'status': 'invalid', 'reason': 'invalid_metadata', 'record_id': str(prior.id),
                'source_record_id': prior.source_record_id}
    return _revise(owner, prior, prior.values, metadata)


def _audit(owner, record, before):
    after = serialize_summary(record)
    digest = hashlib.sha256(json.dumps(
        {'operation': 'derived_refresh', 'record_id': str(record.id), 'before': before, 'after': after},
        sort_keys=True, default=str).encode()).hexdigest()
    receipt = WriteRequest.objects.create(
        owner=owner, request_id=uuid4(), payload_hash=digest, response=after)
    SummaryCorrection.objects.create(record=record, request=receipt, before=before, after=after)


def _live_derived(owner, connection, kind, day, stable):
    return SummaryRecord.objects.filter(
        owner=owner, kind=kind, source_system='oura', source_record_id=stable).first() or SummaryRecord.objects.filter(
        owner=owner, connection=connection, synthetic=connection.synthetic, kind=kind,
        local_date=day, entry_method=DERIVED).first()


def _foreign_collision(owner, kind, stable, connection, day):
    row = SummaryRecord.objects.filter(
        owner=owner, kind=kind, source_system='oura', source_record_id=stable).first()
    if row is None:
        return None
    if row.entry_method != DERIVED or row.connection_id != connection.id or row.synthetic != connection.synthetic or row.local_date != day:
        return row
    return None


def _sources_match(owner, connection, contributors):
    fresh = OuraConnection.objects.filter(pk=connection.id, owner=owner).first()
    if fresh is None or fresh.synthetic != connection.synthetic or fresh.owner_id != owner.id:
        return False
    for item in contributors:
        row = OuraRecord.objects.select_related('connection').filter(pk=item['raw_id'], connection=fresh).first()
        if row is None or row.version != item['version'] or row.raw_json != item['raw_json']:
            return False
        if row.identity_key != item['identity_key'] or row.collection != item['collection']:
            return False
        if (row.source_record_id or '') != item['source_record_id'] or row.connection.owner_id != owner.id:
            return False
        if row.connection.synthetic != connection.synthetic:
            return False
    return True


def _proposal_ready(connection, kind, metadata):
    return _metadata_shape(metadata, connection, kind)


def _store(owner, connection, kind, day, stable, values, metadata, contributors):
    if _identity_problem_for_new(owner, connection, kind, day, stable):
        return {'status': 'invalid', 'reason': 'invalid_identity', 'source_record_id': stable}
    if not _proposal_ready(connection, kind, metadata):
        return {'status': 'conflict', 'reason': 'invalid_metadata', 'source_record_id': stable}
    if metadata['status'] == 'current' and not _sources_match(owner, connection, contributors):
        metadata = _metadata(connection, 'conflict', [], metadata['contributor_identities_ever'], 'source_changed')
        prior = _live_derived(owner, connection, kind, day, stable)
        values = prior.values if prior is not None and prior.deleted_at is None and prior.entry_method == DERIVED else None
        if values is None:
            return {'status': 'conflict', 'reason': 'source_changed', 'source_record_id': stable}
    blocked = _legacy_blocks(owner, kind, day, contributors) or _derived_tombstone(
        owner, connection, kind, day) or _lineage_blocks(owner, connection, contributors, kind)
    if blocked:
        existing = _live_derived(owner, connection, kind, day, stable)
        if existing is not None and existing.deleted_at is None and existing.entry_method == DERIVED and _identity_problem(existing) is None:
            return _revise(owner, existing, existing.values, metadata)
        return {'status': 'suppressed', 'reason': metadata['conflict_reason'] or 'tombstone', 'source_record_id': stable}
    collision = _foreign_collision(owner, kind, stable, connection, day)
    if collision is not None:
        return {'status': 'conflict', 'reason': 'source_key_collision', 'source_record_id': stable,
                'record_id': str(collision.id)}
    existing = _live_derived(owner, connection, kind, day, stable)
    if existing is not None and existing.deleted_at is not None:
        return {'status': 'suppressed', 'reason': 'derived_tombstone', 'source_record_id': stable,
                'record_id': str(existing.id)}
    if existing is not None and (existing.entry_method != DERIVED or _identity_problem(existing)):
        return {'status': 'invalid' if existing.entry_method == DERIVED else 'conflict',
                'reason': _identity_problem(existing) or 'source_key_collision',
                'source_record_id': existing.source_record_id, 'record_id': str(existing.id)}
    if existing is not None:
        return _revise(owner, existing, values, metadata)
    if metadata['status'] != 'current':
        return {'status': metadata['status'], 'reason': metadata['conflict_reason'], 'source_record_id': stable}
    try:
        with transaction.atomic():
            record = SummaryRecord.objects.create(
                owner=owner, kind=kind, local_date=day, source_timezone='', source_system='oura',
                source_record_id=stable, entry_method=DERIVED, device='Oura', completeness='partial',
                values=values, synthetic=connection.synthetic, connection=connection, derivation=metadata)
            _audit(owner, record, None)
    except IntegrityError:
        record = SummaryRecord.objects.filter(
            owner=owner, kind=kind, source_system='oura', source_record_id=stable).first()
        if record is None or record.entry_method != DERIVED or record.connection_id != connection.id or record.synthetic != connection.synthetic:
            return {'status': 'conflict', 'reason': 'source_key_collision', 'source_record_id': stable}
        if record.deleted_at is not None or _identity_problem(record):
            return {'status': 'suppressed' if record.deleted_at is not None else 'invalid',
                    'reason': 'derived_tombstone' if record.deleted_at is not None else _identity_problem(record),
                    'source_record_id': stable, 'record_id': str(record.id)}
        return _revise(owner, record, values, metadata)
    return {'status': metadata['status'], 'reason': metadata['conflict_reason'], 'source_record_id': stable,
            'record_id': str(record.id), 'version': record.version}


def _identity_problem_for_new(owner, connection, kind, day, stable):
    return (
        connection.owner_id != owner.id
        or connection.synthetic is not True and connection.synthetic is not False
        or kind not in ('activity', 'recovery')
        or stable != stable_source_id(connection, kind, day)
    )


def _revise(owner, existing, values, metadata):
    problem = _identity_problem(existing)
    attached = _attached_connection(existing)
    if attached is None or not _proposal_ready(attached, existing.kind, metadata):
        return {'status': 'conflict', 'reason': 'invalid_metadata', 'record_id': str(existing.id),
                'source_record_id': existing.source_record_id}
    if problem or existing.deleted_at is not None or existing.entry_method != DERIVED:
        return {'status': 'invalid' if problem else 'conflict', 'reason': problem or 'lost_compare_and_swap',
                'record_id': str(existing.id), 'source_record_id': existing.source_record_id}
    if _same_derivation(existing, metadata, values):
        return {'status': metadata['status'], 'reason': 'unchanged', 'source_record_id': existing.source_record_id,
                'record_id': str(existing.id), 'version': existing.version}
    before = serialize_summary(existing)
    changed = SummaryRecord.objects.filter(
        pk=existing.pk, version=existing.version, deleted_at__isnull=True, entry_method=DERIVED,
        synthetic=existing.synthetic, source_record_id=existing.source_record_id,
    ).update(
        values=values, derivation=metadata, device='Oura', completeness='partial',
        version=existing.version + 1, updated_at=timezone.now())
    if changed != 1:
        fresh = SummaryRecord.objects.get(pk=existing.pk)
        return {'status': 'conflict', 'reason': 'lost_compare_and_swap', 'record_id': str(fresh.id),
                'deleted': fresh.deleted_at is not None, 'version': fresh.version}
    existing.refresh_from_db()
    _audit(owner, existing, before)
    return {'status': metadata['status'], 'reason': metadata['conflict_reason'], 'source_record_id': existing.source_record_id,
            'record_id': str(existing.id), 'version': existing.version}


def _group_decision(records, kind):
    eligible, malformed = [], False
    for record, payload in records:
        if payload is None:
            malformed = True
            continue
        if kind == 'activity':
            parsed = [_whole(payload.get(field)) for field in ACTIVITY_FIELDS]
            if any(state == 'malformed' for state, _ in parsed):
                malformed = True
                continue
            values = {field: parsed[index][1] for index, field in enumerate(ACTIVITY_FIELDS)}
            if all(value is None for value in values.values()):
                continue
            values.update({'workout_minutes': None, 'workout_summary': ''})
            eligible.append((record, values))
        else:
            state, seconds = _whole(payload.get('total_sleep_duration'))
            if state == 'malformed':
                malformed = True
                continue
            if state != 'value':
                continue
            try:
                minutes = (Decimal(seconds) / Decimal('60')).quantize(Decimal('0.001'))
                if minutes < 0 or minutes > MAX_WHOLE:
                    raise InvalidOperation
                text = format(minutes, 'f')
            except (InvalidOperation, ValueError):
                malformed = True
                continue
            eligible.append((record, {
                'sleep_minutes': text, 'hrv_ms': None, 'resting_hr_bpm': None,
                'readiness': None, 'hrv_method': ''}))
    return eligible, malformed


def _snapshot(owner, start, end):
    grouped, rejected = {}, []
    rows = OuraRecord.objects.select_related('connection').filter(
        connection__owner=owner, collection__in=('daily_activity', 'sleep')).order_by('id')
    for record in rows:
        connection = record.connection
        if connection.owner_id != owner.id:
            rejected.append({'status': 'rejected', 'reason': 'cross_owner', 'raw_id': str(record.id)})
            continue
        state, payload = _parse_raw(record.raw_json)
        kind = 'activity' if record.collection == 'daily_activity' else 'recovery'
        if state == 'malformed':
            rejected.append({'status': 'rejected', 'reason': 'malformed_json', 'raw_id': str(record.id)})
            continue
        if state == 'ambiguous':
            day = _day(payload, start, end) if isinstance(payload, str) else 'malformed'
            if day == 'outside':
                continue
            if day == 'malformed':
                rejected.append({'status': 'rejected', 'reason': 'duplicate_member', 'raw_id': str(record.id)})
                continue
            grouped.setdefault((connection.id, kind, day), []).append((record, None))
            continue
        day = _day(payload.get('day'), start, end)
        if day == 'outside':
            continue
        if day == 'malformed':
            rejected.append({'status': 'rejected', 'reason': 'malformed_day', 'raw_id': str(record.id)})
            continue
        if _payload_identity(record, payload) == 'contradiction':
            grouped.setdefault((connection.id, kind, day), []).append((record, None))
            continue
        grouped.setdefault((connection.id, kind, day), []).append((record, payload))
    return grouped, rejected


def refresh_stored_sources(owner, today=None):
    """Refresh accepted stored Oura rows for one owner. This is not a read side effect."""
    start, end = plan_window(today)
    with transaction.atomic():
        grouped, results = _snapshot(owner, start, end)
        seen = set()
        ordered = sorted(grouped.items(), key=lambda item: (str(item[0][0]), item[0][1], item[0][2].isoformat()))
        for (connection_id, kind, day), rows in ordered:
            connection = OuraConnection.objects.filter(pk=connection_id, owner=owner).first()
            if connection is None or (connection.synthetic is not True and connection.synthetic is not False):
                results.append({'status': 'rejected', 'reason': 'class_mismatch'})
                continue
            eligible, malformed = _group_decision(rows, kind)
            reason = ''
            status = 'current'
            if status == 'current' and any(not _retained_provider_source(record, kind) for record, _parsed in eligible):
                status = 'conflict'
                reason = 'invalid_source'
            if malformed or len(eligible) != 1:
                status = 'conflict'
                reason = 'malformed_input' if malformed and len(eligible) <= 1 else (
                    'multiple_activity' if kind == 'activity' and len(eligible) > 1 else (
                        'overlapping_sleep' if kind == 'recovery' and len(eligible) > 1 else 'missing_input'))
                if len(eligible) == 0 and not malformed:
                    status, reason = 'stale', 'missing_input'
            chosen_rows = eligible if status == 'current' else (eligible or [(record, None) for record, _ in rows])
            contributors = sorted((_public_contributor(record) for record, _ in chosen_rows), key=lambda item: item['raw_id'])
            stable = stable_source_id(connection, kind, day)
            prior = _live_derived(owner, connection, kind, day, stable)
            if prior is not None and prior.entry_method == DERIVED and _identity_problem(prior):
                results.append({'status': 'invalid', 'reason': _identity_problem(prior), 'record_id': str(prior.id),
                                'source_record_id': prior.source_record_id})
                seen.add((connection.id, kind, day))
                continue
            stored_ever = prior.derivation.get('contributor_identities_ever') if prior is not None and isinstance(prior.derivation, dict) else []
            ever = _merge_ever(stored_ever if isinstance(stored_ever, list) else [], contributors)
            if ever is None:
                results.append(_hold_prior(owner, connection, kind, prior, stable, 'invalid_source'))
                seen.add((connection.id, kind, day))
                continue
            if _legacy_blocks(owner, kind, day, contributors):
                status, reason, chosen = 'conflict', 'legacy_tombstone', None
            elif _derived_tombstone(owner, connection, kind, day) or _lineage_blocks(owner, connection, contributors, kind):
                status, reason, chosen = 'conflict', 'derived_tombstone', None
            else:
                chosen = eligible[0][1] if status == 'current' else None
            metadata = _metadata(connection, status, [_stored_contributor(item, include_version=True) for item in contributors] if status == 'current' else [], ever, reason)
            if chosen is not None:
                values = chosen
            elif prior is not None and prior.deleted_at is None and prior.entry_method == DERIVED and _identity_problem(prior) is None:
                values = prior.values
            else:
                values = None
            if not _metadata_shape(metadata, connection, kind):
                results.append(_hold_prior(owner, connection, kind, prior, stable, 'invalid_source'))
                seen.add((connection.id, kind, day))
                continue
            if values is None:
                results.append({'status': 'suppressed' if reason.endswith('tombstone') else status, 'reason': reason,
                                'source_record_id': stable})
                seen.add((connection.id, kind, day))
                continue
            results.append(_store(
                owner, connection, kind, day, stable, values, metadata,
                contributors if status == 'current' else []))
            seen.add((connection.id, kind, day))
        for record in SummaryRecord.objects.filter(
                owner=owner, entry_method=DERIVED, deleted_at__isnull=True,
                local_date__gte=start, local_date__lte=end).select_related('connection'):
            key = (record.connection_id, record.kind, record.local_date)
            if key in seen or record.connection_id is None:
                continue
            problem = _identity_problem(record)
            if problem:
                results.append({'status': 'invalid', 'reason': problem, 'record_id': str(record.id),
                                'source_record_id': record.source_record_id})
                continue
            ever = record.derivation.get('contributor_identities_ever') if isinstance(record.derivation, dict) else []
            metadata = _metadata(record.connection, 'stale', [], ever if isinstance(ever, list) else [], 'missing_input')
            results.append(_revise(owner, record, record.values, metadata))
        return results
