"""Read-only eligibility and provenance. This module does not refresh, write, or classify by stored flag alone."""
from django.db.models import Q

from tracking.models import SummaryRecord

LEGACY_KINDS = ('activity', 'recovery')
DERIVED_STATUSES = ('current', 'stale', 'conflict', 'invalid')


def legacy_candidate(record):
    """Imported exact-oura activity or recovery with no derived identity. Not a corruption mark."""
    return (
        record.source_system == 'oura'
        and record.kind in LEGACY_KINDS
        and record.entry_method == 'imported'
        and record.connection_id is None
        and record.derivation is None
    )


def _provenance_status(record):
    from tracking.projection_identity import provenance_status
    return provenance_status(record)


def evidence_envelope(record):
    """Classification beside a record. It does not copy account keys, external ids, or credentials."""
    status = _provenance_status(record)
    derived = record.entry_method == 'derived'
    verified = derived and status in {'current', 'stale', 'conflict'}
    if status == 'legacy_unresolved':
        eligibility, reason, calculation = 'unresolved', 'legacy_unresolved', 'unavailable'
    elif derived:
        eligibility, calculation = 'unavailable', 'unavailable'
        reason = status if status in DERIVED_STATUSES else 'invalid'
    elif record.deleted_at is not None:
        eligibility, reason, calculation = 'unavailable', 'deleted', 'unavailable'
    else:
        eligibility, reason, calculation = 'eligible', 'eligible', 'available'
    return {
        'summary_id': str(record.id),
        'provenance_status': status,
        'eligibility_status': eligibility,
        'eligibility_reason': reason,
        'calculation': calculation,
        'stored_synthetic': record.synthetic is True,
        'stored_class_verified': verified,
        'connection_id': str(record.connection_id) if verified and record.connection_id is not None else None,
        'derived_class': record.synthetic if verified and (record.synthetic is True or record.synthetic is False) else None,
        'derived_status': status if derived else None,
        'source_system': record.source_system,
        'device': record.device,
        'entry_method': record.entry_method,
        'kind': record.kind,
    }


def resolve_metric(records, key):
    """One eligible value, including zero. Competing records stay unresolved. Null stays unknown."""
    eligible, excluded = [], []
    for record in records:
        envelope = evidence_envelope(record)
        if envelope['eligibility_status'] != 'eligible':
            excluded.append({'summary_id': envelope['summary_id'], 'eligibility_status': envelope['eligibility_status'],
                             'eligibility_reason': envelope['eligibility_reason']})
            continue
        value = record.values.get(key) if isinstance(record.values, dict) else None
        if value is None:
            excluded.append({'summary_id': envelope['summary_id'], 'eligibility_status': 'unavailable',
                             'eligibility_reason': 'unknown'})
            continue
        eligible.append({'summary_id': envelope['summary_id'], 'value': value, 'source_system': record.source_system,
                         'device': record.device, 'stored_synthetic': record.synthetic is True,
                         'entry_method': record.entry_method, 'kind': record.kind})
    if not eligible:
        return {'status': 'unavailable', 'reason': 'no_eligible_value', 'value': None,
                'alternatives': [], 'excluded': excluded}
    if len(eligible) == 1:
        return {'status': 'value', 'reason': 'single_eligible', 'value': eligible[0]['value'],
                'alternatives': eligible, 'excluded': excluded}
    return {'status': 'selection_required', 'reason': 'competing_eligible_records', 'value': None,
            'alternatives': eligible, 'excluded': excluded}


def evidence_counts(records):
    """Separate coverage from stored history. The newest stored row does not make evidence fresh."""
    eligible = unresolved = unavailable = 0
    eligible_latest = historical_latest = None
    for record in records.select_related('connection').iterator():
        if historical_latest is None or record.local_date > historical_latest:
            historical_latest = record.local_date
        status = evidence_envelope(record)['eligibility_status']
        if status == 'eligible':
            eligible += 1
            if eligible_latest is None or record.local_date > eligible_latest:
                eligible_latest = record.local_date
        elif status == 'unresolved':
            unresolved += 1
        else:
            unavailable += 1
    return {
        'eligible_count': eligible,
        'unresolved_count': unresolved,
        'unavailable_count': unavailable,
        'eligible_latest_date': None if eligible_latest is None else eligible_latest.isoformat(),
        'historical_latest_date': None if historical_latest is None else historical_latest.isoformat(),
    }


def unresolved_history(owner):
    """Both stored flags and tombstones. This is not a personal-attribution filter."""
    legacy = Q(source_system='oura', kind__in=LEGACY_KINDS, entry_method='imported',
               connection__isnull=True, derivation__isnull=True)
    return (SummaryRecord.objects.filter(owner=owner).filter(legacy | Q(entry_method='derived'))
            .select_related('connection').order_by('-local_date', 'kind', 'id'))
