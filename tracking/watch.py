"""Facts for a separate watch. This module does not score risk or infer a relapse."""
from datetime import date

from tracking.models import DietEntry, JournalEntry, JournalObservation, Measurement, SummaryRecord
from tracking.summary_evidence import partition_records, resolve_metric


def _day(raw):
    if isinstance(raw, date):
        return raw
    return date.fromisoformat(raw)


def _scoped(query, include_synthetic):
    return query if include_synthetic else query.filter(synthetic=False)


def _plain(value):
    if value is None:
        return None
    return format(value, 'f') if hasattr(value, 'as_tuple') else value


def watch_signals(owner, local_date, *, include_synthetic=False):
    """Return known facts for one date. Missing facts stay null or an empty list."""
    day = _day(local_date)
    def facts(kind, fields):
        rows = _scoped(SummaryRecord.objects.filter(
            owner=owner, kind=kind, local_date=day, deleted_at__isnull=True), include_synthetic
        ).select_related('connection')
        rows = list(rows)
        _eligible, evidence = partition_records(rows)
        by_id = {str(row.id): row for row in rows}
        metric_fields = tuple(field for field in fields if field != 'hrv_method')
        decisions = {field: resolve_metric(rows, field) for field in metric_fields}
        statuses = [item['status'] for item in decisions.values()]
        if 'selection_required' in statuses:
            status = 'selection_required'
        elif 'value' in statuses:
            status = 'value'
        else:
            status = 'unavailable'
        chosen = []
        if status == 'value':
            for decision in decisions.values():
                if decision['status'] == 'value' and decision['alternatives']:
                    chosen.append(decision['alternatives'][0]['summary_id'])
        visible = []
        seen = set()
        for summary_id in chosen:
            if summary_id in seen:
                continue
            seen.add(summary_id)
            row = by_id[summary_id]
            values = row.values if isinstance(row.values, dict) else {}
            item = {
                'summary_id': summary_id, 'source': row.source_system, 'device': row.device,
                'entry_method': row.entry_method, 'stored_synthetic': row.synthetic is True,
                'class_label': 'test' if row.synthetic else 'personal', 'status': 'eligible',
            }
            item.update({field: _plain(values.get(field)) for field in fields})
            visible.append(item)
        alternatives = []
        if status == 'selection_required':
            seen_alt = set()
            for decision in decisions.values():
                if decision['status'] != 'selection_required':
                    continue
                for alt in decision['alternatives']:
                    if alt['summary_id'] in seen_alt:
                        continue
                    seen_alt.add(alt['summary_id'])
                    alternatives.append(alt)
        evidence.update({'status': status, 'alternatives': alternatives, 'metrics': decisions})
        return visible, evidence

    recovery, recovery_evidence = facts('recovery', ('sleep_minutes', 'hrv_ms', 'hrv_method', 'readiness'))
    activity, activity_evidence = facts('activity', ('steps',))
    weight = _scoped(Measurement.objects.filter(
        owner=owner, metric='weight', deleted_at__isnull=True, local_date__lte=day), include_synthetic
    ).order_by('-local_date', '-created_at').first()
    meals = _scoped(DietEntry.objects.filter(
        owner=owner, deleted_at__isnull=True, local_date=day), include_synthetic)
    meal_count = meals.count()
    calories_known = meals.filter(calories__isnull=False).exists()
    sobriety = []
    for row in _scoped(JournalObservation.objects.filter(
            owner=owner, domain_id=12, local_date=day, deleted_at__isnull=True), include_synthetic):
        sobriety.append({
            'metric_key': row.metric_key, 'value_state': row.value_state, 'value_json': row.value_json,
            'narrative': row.narrative,
        })
    return {
        'local_date': day.isoformat(),
        'recovery': recovery,
        'activity': activity,
        'recovery_evidence': recovery_evidence,
        'activity_evidence': activity_evidence,
        'weight': None if weight is None else {
            'value': _plain(weight.value), 'unit': weight.unit, 'local_date': weight.local_date.isoformat(),
            'source': weight.source_system,
        },
        'food': {'meal_count': meal_count, 'calories_known': calories_known},
        'checkin': _scoped(JournalEntry.objects.filter(
            owner=owner, deleted_at__isnull=True, local_date=day), include_synthetic).exists(),
        'sobriety': {'known': bool(sobriety), 'observations': sobriety},
    }
