"""Facts for a separate watch. This module does not score risk or infer a relapse."""
from datetime import date

from tracking.models import DietEntry, JournalEntry, JournalObservation, Measurement, SummaryRecord


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
    recovery = []
    for row in _scoped(SummaryRecord.objects.filter(
            owner=owner, kind='recovery', local_date=day, deleted_at__isnull=True), include_synthetic):
        values = row.values if isinstance(row.values, dict) else {}
        recovery.append({
            'source': row.source_system, 'sleep_minutes': _plain(values.get('sleep_minutes')),
            'hrv_ms': _plain(values.get('hrv_ms')), 'hrv_method': values.get('hrv_method'),
            'readiness': _plain(values.get('readiness')),
        })
    activity = []
    for row in _scoped(SummaryRecord.objects.filter(
            owner=owner, kind='activity', local_date=day, deleted_at__isnull=True), include_synthetic):
        values = row.values if isinstance(row.values, dict) else {}
        activity.append({'source': row.source_system, 'steps': _plain(values.get('steps'))})
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
        'weight': None if weight is None else {
            'value': _plain(weight.value), 'unit': weight.unit, 'local_date': weight.local_date.isoformat(),
            'source': weight.source_system,
        },
        'food': {'meal_count': meal_count, 'calories_known': calories_known},
        'checkin': _scoped(JournalEntry.objects.filter(
            owner=owner, deleted_at__isnull=True, local_date=day), include_synthetic).exists(),
        'sobriety': {'known': bool(sobriety), 'observations': sobriety},
    }
