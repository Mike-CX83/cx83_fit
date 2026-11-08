"""Memory, check-in questions, and optional personal scores.

Scores are exploratory summaries of confirmed ratings and selected practices.
A missing value does not become zero. No score is produced when coverage is too thin.
"""
import hashlib
import json
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from .domain import InvalidMeasurement, parse_day, request_uuid
from .journal_registry import DAILY_STATE_FORMULA, DOMAINS, ROUTINE_FORMULA, STATE_METRICS
from .models import (JournalEntry, JournalMemory, JournalObservation, JournalQuestion, JournalScore, WriteRequest)
from .services import Conflict, _owner, _replay

CHECKIN_VERSION = 'checkin-1'
OPENERS = {
    'morning': 'How are you feeling this morning, and what matters today?',
    'evening': 'What stood out today, and how are you feeling now?',
}
FOLLOWUP_BUDGET = 3
COOLDOWN = timedelta(days=7)


def _digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _memory_row(row):
    return {
        'id': str(row.id), 'kind': row.kind, 'status': row.status, 'domain_id': row.domain_id,
        'practice_key': row.practice_key, 'text': '' if row.deleted_at else row.text,
        'review_on': row.review_on.isoformat() if row.review_on else None,
        'source_entry_id': str(row.source_entry_id) if row.source_entry_id else None,
        'synthetic': row.synthetic, 'version': row.version,
        'deleted': row.deleted_at is not None,
    }


def save_memory(owner, kind, text, request_id, *, status='active', domain_id=None, practice_key='',
                review_on=None, source_entry_id=None, synthetic=False, memory_id=None, expected_version=None):
    _owner(owner)
    if kind not in dict(JournalMemory.KINDS) or status not in dict(JournalMemory.STATUSES) or status == 'deleted':
        raise InvalidMeasurement('Use a supported memory kind and status.')
    if not isinstance(text, str) or not text.strip() or len(text.strip()) > 2000:
        raise InvalidMeasurement('Memory text must be 1 to 2000 characters.')
    if domain_id is not None and domain_id not in DOMAINS:
        raise InvalidMeasurement('Use one of the journal domains.')
    if practice_key and (kind != 'commitment' or len(practice_key) > 40 or not practice_key.replace('_', '').isalnum()):
        raise InvalidMeasurement('A practice key belongs on a commitment.')
    if type(synthetic) is not bool:
        raise InvalidMeasurement('synthetic must be true or false.')
    request_id = request_uuid(request_id)
    day = None if review_on in (None, '') else parse_day(review_on)
    source_entry_id = None if not source_entry_id else request_uuid(source_entry_id)
    clean = text.strip()
    canonical = {'operation': 'save_memory', 'kind': kind, 'status': status, 'text': clean, 'domain_id': domain_id,
                 'practice_key': practice_key, 'review_on': None if day is None else day.isoformat(),
                 'source_entry_id': source_entry_id, 'synthetic': synthetic, 'memory_id': memory_id,
                 'expected_version': expected_version}
    digest = _digest(canonical)
    try:
        with transaction.atomic():
            prior = _replay(owner, request_id, digest)
            if prior is not None:
                if prior.get('deleted'):
                    raise Conflict('This memory was deleted. A retry cannot restore it.')
                return prior
            if source_entry_id and not JournalEntry.objects.filter(owner=owner, id=source_entry_id, synthetic=synthetic).exists():
                raise InvalidMeasurement('The source journal entry was not found.')
            receipt = WriteRequest.objects.create(owner=owner, request_id=request_id, payload_hash=digest)
            if memory_id is None:
                row = JournalMemory.objects.create(
                    owner=owner, request=receipt, kind=kind, status=status, domain_id=domain_id,
                    practice_key=practice_key, text=clean, review_on=day, source_entry_id=source_entry_id,
                    synthetic=synthetic)
            else:
                memory_id = request_uuid(memory_id)
                if type(expected_version) is not int or expected_version < 1:
                    raise InvalidMeasurement('A current memory version is required.')
                changed = JournalMemory.objects.filter(
                    owner=owner, id=memory_id, version=expected_version, deleted_at__isnull=True).update(
                    kind=kind, status=status, domain_id=domain_id, practice_key=practice_key, text=clean,
                    review_on=day, version=expected_version + 1, updated_at=timezone.now())
                if changed != 1:
                    raise Conflict('The memory changed. Read it again before correcting it.')
                row = JournalMemory.objects.get(owner=owner, id=memory_id)
            result = _memory_row(row)
            receipt.response = {'id': result['id'], 'version': result['version'], 'deleted': False}
            receipt.save(update_fields=['response'])
            return result
    except IntegrityError:
        prior = _replay(owner, request_id, digest)
        if prior is not None:
            return prior
        raise Conflict('A conflicting write occurred. Retry the same request_id.') from None
    except OperationalError:
        raise Conflict('Storage is temporarily busy. Retry the same request_id.') from None


def list_memories(owner, include_synthetic=False, status='active'):
    _owner(owner)
    query = JournalMemory.objects.filter(owner=owner, deleted_at__isnull=True)
    if status:
        query = query.filter(status=status)
    if not include_synthetic:
        query = query.filter(synthetic=False)
    return [_memory_row(row) for row in query[:100]]


def delete_memory(owner, memory_id, expected_version, request_id):
    _owner(owner)
    memory_id, request_id = request_uuid(memory_id), request_uuid(request_id)
    digest = _digest({'operation': 'delete_memory', 'memory_id': memory_id, 'expected_version': expected_version})
    try:
        with transaction.atomic():
            prior = _replay(owner, request_id, digest)
            if prior is not None:
                return prior
            changed = JournalMemory.objects.filter(
                owner=owner, id=memory_id, version=expected_version, deleted_at__isnull=True).update(
                text='', status='deleted', deleted_at=timezone.now(), version=expected_version + 1, updated_at=timezone.now())
            if changed != 1:
                raise Conflict('The memory changed. Review it before deleting.')
            receipt = WriteRequest.objects.create(owner=owner, request_id=request_id, payload_hash=digest,
                                                  response={'id': memory_id, 'deleted': True})
            row = JournalMemory.objects.get(owner=owner, id=memory_id)
            row.request.response = {'id': memory_id, 'deleted': True}
            row.request.save(update_fields=['response'])
            receipt.response = {'id': memory_id, 'deleted': True}
            receipt.save(update_fields=['response'])
            return {'id': memory_id, 'deleted': True}
    except (IntegrityError, OperationalError):
        raise Conflict('Storage is busy. Retry the same deletion request.') from None


def suggest_questions(owner, session, *, now=None, include_synthetic=False):
    """Return at most three follow-ups. This does not mark them asked."""
    _owner(owner)
    if session not in OPENERS:
        raise InvalidMeasurement('Choose a morning or evening check-in.')
    now = now or timezone.now()
    today = timezone.localdate()
    questions = []
    concerns = JournalMemory.objects.filter(owner=owner, kind='concern', status='active', deleted_at__isnull=True)
    if not include_synthetic:
        concerns = concerns.filter(synthetic=False)
    for concern in concerns.order_by('review_on', 'created_at')[:2]:
        if concern.review_on and concern.review_on > today:
            continue
        if JournalQuestion.objects.filter(owner=owner, topic=f'concern:{concern.id}', created_at__date=today).exists():
            continue
        questions.append({'topic': f'concern:{concern.id}', 'reason': 'open_concern', 'domain_id': concern.domain_id,
                          'prompt': 'Is this open concern still current?'})
        if len(questions) >= FOLLOWUP_BUDGET:
            break
    if len(questions) < FOLLOWUP_BUDGET:
        recent = timezone.now() - COOLDOWN
        asked = set(JournalQuestion.objects.filter(owner=owner, created_at__gte=recent).values_list('domain_id', flat=True))
        seen = set(JournalObservation.objects.filter(
            owner=owner, deleted_at__isnull=True, local_date__gte=today - timedelta(days=7)).values_list('domain_id', flat=True))
        if not include_synthetic:
            seen = set(JournalObservation.objects.filter(
                owner=owner, synthetic=False, deleted_at__isnull=True,
                local_date__gte=today - timedelta(days=7)).values_list('domain_id', flat=True))
        for domain_id, label in DOMAINS.items():
            if domain_id in asked or domain_id in seen:
                continue
            questions.append({'topic': f'domain:{domain_id}', 'reason': 'optional_domain', 'domain_id': domain_id,
                              'prompt': f'Anything you want to note for {label}?'})
            break
    return {'session': session, 'opener': OPENERS[session], 'checkin_version': CHECKIN_VERSION,
            'followups': questions[:FOLLOWUP_BUDGET], 'budget': FOLLOWUP_BUDGET}


def record_question(owner, topic, prompt, reason, status, request_id, *, domain_id=None, synthetic=False):
    _owner(owner)
    if status not in dict(JournalQuestion.STATUSES):
        raise InvalidMeasurement('Use a supported question status.')
    if not isinstance(topic, str) or not topic.strip() or len(topic) > 80:
        raise InvalidMeasurement('A question topic is required.')
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 500:
        raise InvalidMeasurement('A question prompt is required.')
    request_id = request_uuid(request_id)
    now = timezone.now()
    next_eligible = now + COOLDOWN if status in {'skipped', 'deferred'} else None
    if status == 'suppressed':
        next_eligible = now + timedelta(days=365)
    digest = _digest({'operation': 'record_question', 'topic': topic, 'status': status, 'prompt': prompt,
                      'reason': reason, 'domain_id': domain_id, 'synthetic': synthetic})
    try:
        with transaction.atomic():
            prior = _replay(owner, request_id, digest)
            if prior is not None:
                return prior
            receipt = WriteRequest.objects.create(owner=owner, request_id=request_id, payload_hash=digest)
            row = JournalQuestion.objects.create(
                owner=owner, topic=topic.strip(), prompt=prompt.strip(), reason=(reason or 'followup')[:40],
                status=status, domain_id=domain_id, asked_at=now, next_eligible=next_eligible, synthetic=synthetic)
            result = {'id': str(row.id), 'topic': row.topic, 'status': row.status,
                      'next_eligible': row.next_eligible.isoformat() if row.next_eligible else None}
            receipt.response = result
            receipt.save(update_fields=['response'])
            return result
    except IntegrityError:
        prior = _replay(owner, request_id, digest)
        if prior is not None:
            return prior
        raise Conflict('A conflicting write occurred. Retry the same request_id.') from None


def _rating(observation):
    value = observation.value_json or {}
    rating = value.get('rating')
    if observation.value_state != 'observed' or type(rating) is not int:
        return None
    return rating


def score_day(owner, local_date, *, include_synthetic=False):
    """Persist today's optional scores. Missing coverage stores a null result, never zero."""
    _owner(owner)
    day = parse_day(local_date)
    observations = JournalObservation.objects.filter(owner=owner, local_date=day, deleted_at__isnull=True)
    if not include_synthetic:
        observations = observations.filter(synthetic=False)
    observations = list(observations)
    present = []
    for observation in observations:
        if observation.metric_key in STATE_METRICS:
            rating = _rating(observation)
            if rating is not None:
                present.append((observation, rating))
    coverage = {'planned': len(STATE_METRICS), 'observed': len(present),
                'metrics': [item[0].metric_key for item in present]}
    result = None
    if len(present) >= 2 and len(present) * 5 >= len(STATE_METRICS) * 3:
        result = (sum(item[1] for item in present) * Decimal(10) / Decimal(len(present))).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)
    state_row = _store_score(owner, 'daily_state', day, DAILY_STATE_FORMULA, result, coverage,
                             [str(item[0].id) for item in present], include_synthetic)
    commitments = JournalMemory.objects.filter(
        owner=owner, kind='commitment', status='active', deleted_at__isnull=True)
    if not include_synthetic:
        commitments = commitments.filter(synthetic=False)
    commitments = list(commitments)
    known = {}
    for observation in observations:
        value = observation.value_json or {}
        key = value.get('practice_key')
        if key and observation.value_state == 'observed' and type(value.get('boolean')) is bool:
            known[key] = value['boolean']
    completed = missed = unknown = 0
    for commitment in commitments:
        if not commitment.practice_key:
            continue
        if commitment.practice_key not in known:
            unknown += 1
        elif known[commitment.practice_key]:
            completed += 1
        else:
            missed += 1
    applicable = completed + missed + unknown
    routine_coverage = {'applicable': applicable, 'completed': completed, 'not_completed': missed, 'unknown': unknown}
    routine_result = None
    if applicable and unknown == 0:
        routine_result = (Decimal(100) * Decimal(completed) / Decimal(applicable)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)
    routine_row = _store_score(owner, 'routine_alignment', day, ROUTINE_FORMULA, routine_result, routine_coverage,
                               [str(item.id) for item in commitments], include_synthetic)
    return {'daily_state': _score_row(state_row), 'routine_alignment': _score_row(routine_row)}


def _store_score(owner, kind, day, formula, result, coverage, input_ids, synthetic):
    row, _created = JournalScore.objects.update_or_create(
        owner=owner, kind=kind, local_date=day, formula_version=formula, synthetic=synthetic,
        defaults={'result': result, 'coverage': coverage, 'input_ids': input_ids})
    return row


def _score_row(row):
    return {'id': str(row.id), 'kind': row.kind, 'local_date': row.local_date.isoformat(),
            'formula_version': row.formula_version, 'result': None if row.result is None else format(row.result, 'f'),
            'coverage': row.coverage, 'synthetic': row.synthetic,
            'label': 'provisional personal summary' if row.result is not None else 'no score'}


def journal_context(owner, session, *, include_synthetic=False):
    from .governing import governing_status
    day = timezone.localdate()
    return {
        'checkin': suggest_questions(owner, session, include_synthetic=include_synthetic),
        'memories': list_memories(owner, include_synthetic, 'active'),
        'scores': score_day(owner, day.isoformat(), include_synthetic=include_synthetic),
        'governing': governing_status(),
        'local_date': day.isoformat(),
    }
