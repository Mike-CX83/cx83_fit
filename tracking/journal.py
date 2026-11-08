"""Dashboard journal writes. Receipts identify rows and versions, not the text.

The conversational client can propose observations later. This module only
accepts values the owner already structured. It does not parse a story into
facts, and it does not score them.
"""
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from .domain import InvalidMeasurement, parse_day, request_uuid
from .governing import governing_status
from .journal_registry import PROTOCOL_VERSION, REGISTRY_VERSION, validate_observation
from .models import JournalCorrection, JournalEntry, JournalObservation, WriteRequest
from .services import Conflict, RecordNotFound, _owner, _replay


def _timezone(value):
    try:
        if not isinstance(value, str) or not value or len(value) > 64:
            raise ValueError
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise InvalidMeasurement('Use a valid IANA source timezone.') from None
    return value


def _occurred(value, local_date, source_timezone):
    if not value:
        return None, 'date'
    try:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ValueError
    except (ValueError, TypeError):
        raise InvalidMeasurement('A journal time must include a UTC offset.') from None
    if value.astimezone(ZoneInfo(source_timezone)).date() != local_date:
        raise InvalidMeasurement('Journal time and local date disagree in the source timezone.')
    return value, 'datetime'


def _body(value):
    if not isinstance(value, str):
        raise InvalidMeasurement('Journal text must be text.')
    body = value.strip()
    if not body or len(body) > 10000:
        raise InvalidMeasurement('Journal text must be 1 to 10000 characters.')
    return body


def _digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _receipt(entry, observation, operation):
    return {
        'id': str(entry.id), 'operation': operation, 'version': entry.version,
        'observation_id': None if observation is None else str(observation.id),
        'observation_version': None if observation is None else observation.version,
        'deleted': entry.deleted_at is not None, 'protocol_version': entry.protocol_version,
        'registry_version': None if observation is None else observation.registry_version,
    }


def _changed(before, after, names):
    return [name for name in names if before.get(name) != after.get(name)]


def _entry_snapshot(entry):
    return {'body': entry.body, 'local_date': entry.local_date.isoformat(),
            'source_timezone': entry.source_timezone,
            'occurred_at': entry.occurred_at.isoformat() if entry.occurred_at else None,
            'time_precision': entry.time_precision}


def _observation_snapshot(observation):
    if observation is None:
        return None
    return {'domain_id': observation.domain_id, 'metric_key': observation.metric_key,
            'value_state': observation.value_state, 'value_type': observation.value_type,
            'value_json': observation.value_json, 'narrative': observation.narrative,
            'local_date': observation.local_date.isoformat(), 'source_timezone': observation.source_timezone}


def _active_observation(entry):
    rows = list(entry.observations.filter(deleted_at__isnull=True))
    if len(rows) > 1:
        raise InvalidMeasurement('This entry has several observations. Edit one at a time once that flow exists.')
    return rows[0] if rows else None


def _scrub(entry):
    receipt_ids = [entry.request_id, *entry.corrections.values_list('request_id', flat=True)]
    WriteRequest.objects.filter(pk__in=receipt_ids).update(response={'id': str(entry.id), 'deleted': True})


def save_journal(owner, body, local_date, request_id, observation=None, *, source_timezone='America/Chicago',
                 occurred_at=None, synthetic=False, record_id=None, expected_version=None,
                 expected_observation_version=None, channel='dashboard'):
    """Create or correct one owned entry. The same request id and payload replays."""
    _owner(owner)
    if channel not in {'dashboard', 'mcp'}:
        raise PermissionError('Journal saving is enabled for the dashboard and the authorized ChatGPT connection.')
    if type(synthetic) is not bool:
        raise InvalidMeasurement('synthetic must be true or false.')
    request_id = request_uuid(request_id)
    clean_body = _body(body)
    day = parse_day(local_date)
    zone = _timezone(source_timezone)
    moment, precision = _occurred(occurred_at, day, zone)
    clean_observation = None if observation is None else validate_observation(observation)
    if record_id is not None:
        record_id = request_uuid(record_id)
        if type(expected_version) is not int or expected_version < 1:
            raise InvalidMeasurement('A positive expected_version is required for corrections.')
    elif expected_version is not None or expected_observation_version is not None:
        raise InvalidMeasurement('expected_version is only valid for corrections.')
    canonical = {'operation': 'save_journal', 'body': clean_body, 'local_date': day.isoformat(),
                 'source_timezone': zone, 'occurred_at': moment.isoformat() if moment else None,
                 'synthetic': synthetic, 'observation': clean_observation, 'record_id': record_id,
                 'expected_version': expected_version, 'expected_observation_version': expected_observation_version,
                 'channel': channel}
    digest = _digest(canonical)
    try:
        with transaction.atomic():
            prior = _replay(owner, request_id, digest)
            if prior is not None:
                if prior.get('deleted'):
                    raise Conflict('This journal entry was deleted. A retry cannot restore it.')
                return prior
            receipt = WriteRequest.objects.create(owner=owner, request_id=request_id, payload_hash=digest)
            if record_id is None:
                entry = JournalEntry.objects.create(
                    owner=owner, request=receipt, channel=channel, local_date=day, occurred_at=moment,
                    time_precision=precision, source_timezone=zone, body=clean_body,
                    body_sha256=hashlib.sha256(clean_body.encode()).hexdigest(), processing_state='stored',
                    protocol_version=PROTOCOL_VERSION, synthetic=synthetic)
                stored = None
                if clean_observation is not None:
                    stored = JournalObservation.objects.create(
                        owner=owner, entry=entry, local_date=day, source_timezone=zone, synthetic=synthetic,
                        confirmation_status='confirmed', **clean_observation)
                changed = ['body'] if stored is None else ['body', 'observation']
                JournalCorrection.objects.create(
                    entry=entry, observation=stored, request=receipt, operation='create', before_version=None,
                    after_version=entry.version, observation_before_version=None,
                    observation_after_version=None if stored is None else stored.version, changed_fields=changed)
                result = _receipt(entry, stored, 'create')
            else:
                entry = JournalEntry.objects.filter(owner=owner, id=record_id, deleted_at__isnull=True).first()
                if entry is None:
                    raise RecordNotFound('Journal entry not found.')
                if entry.synthetic != synthetic:
                    raise InvalidMeasurement('Synthetic journal entries stay synthetic.')
                current = _active_observation(entry)
                if current is not None and (type(expected_observation_version) is not int or expected_observation_version < 1):
                    raise InvalidMeasurement('A positive observation version is required for this correction.')
                if entry.version != expected_version:
                    raise Conflict('The journal entry changed. Read its current version before correcting it.')
                if current is not None and current.version != expected_observation_version:
                    raise Conflict('The observation changed. Read its current version before correcting it.')
                before_entry = _entry_snapshot(entry)
                after_entry = {'body': clean_body, 'local_date': day.isoformat(), 'source_timezone': zone,
                               'occurred_at': moment.isoformat() if moment else None, 'time_precision': precision}
                after_observation = None if clean_observation is None else {
                    'domain_id': clean_observation['domain_id'], 'metric_key': clean_observation['metric_key'],
                    'value_state': clean_observation['value_state'], 'value_type': clean_observation['value_type'],
                    'value_json': clean_observation['value_json'], 'narrative': clean_observation['narrative'],
                    'local_date': day.isoformat(), 'source_timezone': zone}
                names = _changed(before_entry, after_entry, ('body', 'local_date', 'source_timezone', 'occurred_at', 'time_precision'))
                if _observation_snapshot(current) != after_observation:
                    names.append('observation')
                if names:
                    changed = JournalEntry.objects.filter(
                        owner=owner, id=entry.id, version=expected_version, deleted_at__isnull=True).update(
                        body=clean_body, body_sha256=hashlib.sha256(clean_body.encode()).hexdigest(),
                        local_date=day, source_timezone=zone, occurred_at=moment, time_precision=precision,
                        version=expected_version + 1, updated_at=timezone.now())
                    if changed != 1:
                        raise Conflict('The journal entry changed. Read its current version before correcting it.')
                    entry.refresh_from_db()
                    if 'observation' in names:
                        if current is None and clean_observation is not None:
                            current = JournalObservation.objects.create(
                                owner=owner, entry=entry, local_date=day, source_timezone=zone, synthetic=entry.synthetic,
                                confirmation_status='confirmed', **clean_observation)
                        elif current is not None and clean_observation is not None:
                            observation_changed = JournalObservation.objects.filter(
                                owner=owner, id=current.id, version=expected_observation_version, deleted_at__isnull=True).update(
                                local_date=day, source_timezone=zone, version=expected_observation_version + 1, **clean_observation)
                            if observation_changed != 1:
                                raise Conflict('The observation changed. Read its current version before correcting it.')
                            current.refresh_from_db()
                        elif current is not None and clean_observation is None:
                            raise InvalidMeasurement('This correction would drop the saved observation.')
                result = _receipt(entry, current, 'update')
                JournalCorrection.objects.create(
                    entry=entry, observation=current, request=receipt, operation='update',
                    before_version=expected_version, after_version=entry.version,
                    observation_before_version=None if current is None else expected_observation_version,
                    observation_after_version=None if current is None else current.version, changed_fields=names)
            receipt.response = result
            receipt.save(update_fields=['response'])
            return result
    except IntegrityError:
        prior = _replay(owner, request_id, digest)
        if prior is not None:
            if prior.get('deleted'):
                raise Conflict('This journal entry was deleted. A retry cannot restore it.')
            return prior
        raise Conflict('A conflicting write occurred. Retry the same request_id.') from None
    except OperationalError:
        raise Conflict('Storage is temporarily busy. Retry the same request_id.') from None


def delete_journal(owner, record_id, expected_version, request_id, expected_observation_version=None):
    """Clear active text and leave a tombstone. The receipt does not keep the text."""
    _owner(owner)
    record_id, request_id = request_uuid(record_id), request_uuid(request_id)
    if type(expected_version) is not int or expected_version < 1:
        raise InvalidMeasurement('A current version is required for deletion.')
    digest = _digest({'operation': 'delete_journal', 'record_id': record_id, 'expected_version': expected_version,
                      'expected_observation_version': expected_observation_version})
    try:
        with transaction.atomic():
            prior = _replay(owner, request_id, digest)
            if prior is not None:
                return prior
            entry = JournalEntry.objects.filter(owner=owner, id=record_id, deleted_at__isnull=True).first()
            if entry is None:
                raise RecordNotFound('Journal entry not found.')
            current = _active_observation(entry)
            if current is not None and current.version != expected_observation_version:
                raise Conflict('The observation changed. Review the entry before deleting it.')
            changed = JournalEntry.objects.filter(
                owner=owner, id=entry.id, version=expected_version, deleted_at__isnull=True).update(
                body='', body_sha256='', deleted_at=timezone.now(), version=expected_version + 1, updated_at=timezone.now())
            if changed != 1:
                raise Conflict('The journal entry changed. Review it before deleting.')
            entry.refresh_from_db()
            if current is not None:
                JournalObservation.objects.filter(owner=owner, id=current.id, deleted_at__isnull=True).update(
                    narrative='', value_json=None, deleted_at=entry.deleted_at, version=current.version + 1)
                current.refresh_from_db()
            receipt = WriteRequest.objects.create(owner=owner, request_id=request_id, payload_hash=digest, response={})
            JournalCorrection.objects.create(
                entry=entry, observation=current, request=receipt, operation='delete',
                before_version=expected_version, after_version=entry.version,
                observation_before_version=None if current is None else expected_observation_version,
                observation_after_version=None if current is None else current.version,
                changed_fields=['body', 'narrative', 'value_json'])
            _scrub(entry)
            return {'id': str(entry.id), 'deleted': True}
    except (IntegrityError, OperationalError):
        raise Conflict('Storage is busy. Retry the same deletion request.') from None


_PROPOSAL_FIELDS = {'domain_id', 'metric_key', 'value_state', 'narrative', 'boolean', 'subject', 'support_span', 'temporal_scope'}
_TEMPORAL = {'completed', 'intention', 'unspecified'}


def _proposal_result(index, status, reason, proposal, observation=None):
    item = {'index': index, 'status': status, 'reason': reason, 'subject': proposal.get('subject', 'self')}
    if observation is not None:
        item.update(observation)
    span = proposal.get('support_span')
    if isinstance(span, str):
        item['support_span'] = span.strip()
    temporal = proposal.get('temporal_scope', 'unspecified')
    if isinstance(temporal, str):
        item['temporal_scope'] = temporal
    return item


def _review_proposal(body, proposal, index):
    """Check one client proposal. This does not infer a fact from the wording."""
    if not isinstance(proposal, dict):
        return _proposal_result(index, 'rejected', 'A proposal must be an object.', {'subject': 'self'})
    if set(proposal) - _PROPOSAL_FIELDS:
        return _proposal_result(index, 'rejected', 'Unsupported proposal fields.', proposal)
    subject = proposal.get('subject', 'self')
    if subject != 'self':
        return _proposal_result(index, 'rejected', 'This proposal is about someone else, so it was not saved as your observation.', proposal)
    span = proposal.get('support_span', '')
    if not isinstance(span, str) or len(span) > 500:
        return _proposal_result(index, 'rejected', 'The supporting words must be text of at most 500 characters.', proposal)
    span = span.strip()
    if not span:
        return _proposal_result(index, 'ambiguity', 'A proposal needs the exact words it relies on.', proposal)
    if span not in body:
        return _proposal_result(index, 'rejected', 'Those words are not in the entry.', proposal)
    temporal = proposal.get('temporal_scope', 'unspecified')
    if temporal not in _TEMPORAL:
        return _proposal_result(index, 'rejected', 'Use completed, intention, or unspecified for the timing.', proposal)
    state = proposal.get('value_state')
    if temporal == 'intention' and state == 'observed':
        return _proposal_result(index, 'rejected', 'An intention is not a completed yes or no.', proposal)
    if temporal == 'completed' and state == 'intention':
        return _proposal_result(index, 'rejected', 'A completed choice cannot be stored as only an intention.', proposal)
    if state == 'intention' and temporal == 'unspecified':
        return _proposal_result(index, 'ambiguity', 'Say whether this is a plan or a completed choice.', proposal)
    try:
        fields = {key: proposal[key] for key in ('domain_id', 'metric_key', 'value_state', 'narrative', 'boolean') if key in proposal}
        if 'subject' in proposal:
            fields['subject'] = proposal['subject']
        observation = validate_observation(fields)
    except InvalidMeasurement as exc:
        return _proposal_result(index, 'rejected', str(exc), proposal)
    if observation['narrative'] and observation['narrative'] not in body:
        return _proposal_result(index, 'rejected', 'The note uses words that are not in the entry.', proposal)
    return _proposal_result(index, 'accepted', '', proposal, observation)


def preview_journal_extraction(body, proposals):
    """Validate proposed observations. The database is not changed."""
    clean = _body(body)
    if not isinstance(proposals, list) or len(proposals) > 14:
        raise InvalidMeasurement('Send at most 14 observation proposals.')
    accepted, ambiguities, rejected = [], [], []
    for index, proposal in enumerate(proposals):
        item = _review_proposal(clean, proposal, index)
        {'accepted': accepted, 'ambiguity': ambiguities, 'rejected': rejected}[item.pop('status')].append(item)
    grouped = {}
    for item in accepted:
        grouped.setdefault((item['domain_id'], item['metric_key']), []).append(item)
    conflicted = []
    for items in grouped.values():
        signatures = {(item['value_state'], json.dumps(item.get('value_json'), sort_keys=True), item.get('narrative', '')) for item in items}
        if len(signatures) > 1:
            conflicted.extend(items)
    if conflicted:
        conflict_ids = {item['index'] for item in conflicted}
        accepted = [item for item in accepted if item['index'] not in conflict_ids]
        for item in conflicted:
            ambiguities.append({**item, 'reason': 'These proposals disagree. None was chosen.'})
    return {
        'persisted': False, 'protocol_version': PROTOCOL_VERSION, 'registry_version': REGISTRY_VERSION,
        'body_sha256': hashlib.sha256(clean.encode()).hexdigest(), 'accepted': accepted,
        'ambiguities': ambiguities, 'rejected': rejected, 'silence_is_unknown': not proposals,
    }


def list_journal(owner, start, end, include_synthetic=False, limit=20, offset=0):
    """Return owned journal text for an authorized client. Deleted text is absent."""
    from .domain import bounded_range
    _owner(owner)
    first, last = bounded_range(start, end)
    if type(include_synthetic) is not bool:
        raise InvalidMeasurement('include_synthetic must be true or false.')
    if type(limit) is not int or not 1 <= limit <= 50 or type(offset) is not int or not 0 <= offset <= 100000:
        raise InvalidMeasurement('Use limit 1 to 50 and offset 0 to 100000.')
    query = JournalEntry.objects.filter(owner=owner, deleted_at__isnull=True, local_date__range=(first, last))
    if not include_synthetic:
        query = query.filter(synthetic=False)
    count = query.count()
    items = []
    rows = query.prefetch_related('observations').order_by('-local_date', '-captured_at', 'id')[offset:offset + limit]
    for entry in rows:
        observations = [{
            'id': str(obs.id), 'domain_id': obs.domain_id, 'metric_key': obs.metric_key,
            'value_state': obs.value_state, 'value_type': obs.value_type, 'value_json': obs.value_json,
            'narrative': obs.narrative, 'subject': obs.subject, 'version': obs.version,
        } for obs in entry.observations.all() if obs.deleted_at is None]
        items.append({
            'id': str(entry.id), 'local_date': entry.local_date.isoformat(),
            'occurred_at': entry.occurred_at.isoformat() if entry.occurred_at else None,
            'time_precision': entry.time_precision, 'source_timezone': entry.source_timezone,
            'captured_at': entry.captured_at.isoformat(), 'body': entry.body, 'channel': entry.channel,
            'synthetic': entry.synthetic, 'version': entry.version, 'observations': observations,
        })
    return {'items': items, 'count': count, 'returned': len(items),
            'next_offset': offset + limit if offset + limit < count else None,
            'includes_synthetic': include_synthetic}


def governing_line():
    status = governing_status()
    if not status['available']:
        return 'Private governing document: not mounted for this app.'
    return f"Private governing document version {status['version']} is mounted. Its text stays outside the journal."
