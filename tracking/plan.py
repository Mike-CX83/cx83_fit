"""Rolling 90 day plan window.

Daily steps, sleep, workouts, device calories burned, and the diet diary are analyzed inside the window.
Current labs, medications and diagnoses stay available after that window.
Missing days stay unknown. Separate sources are never added together.
"""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from tracking.domain import METRICS, net_carbohydrates
from tracking.models import ClinicalItem, DietEntry, NutritionTargets, SummaryRecord
from tracking.summaries import SCHEMAS
from tracking.summary_evidence import partition_records, summary_series_token, unambiguous_points

PLAN_DAYS = 90
DAILY_FIELDS = {
    'activity': ('steps', 'workout_minutes', 'active_calories', 'total_calories'),
    'recovery': ('sleep_minutes',),
    'nutrition': ('calories', 'protein', 'fiber'),
}


def plan_window(today=None):
    end = today or timezone.localdate()
    return end - timedelta(days=PLAN_DAYS - 1), end


def _owned(owner, model, include_synthetic):
    query = model.objects.filter(owner=owner)
    if not include_synthetic:
        query = query.filter(synthetic=False)
    return query


def _number(value):
    if value is None or value == '':
        return None
    return Decimal(str(value))


def _average(points):
    if not points:
        return None
    days = {day for day, _ in points}
    total = sum((value for _, value in points), Decimal('0'))
    return {
        'observed_days': len(days),
        'average': format((total / len(days)).quantize(Decimal('0.1')), 'f'),
        'latest_date': max(days).isoformat(),
    }


def _identity(record):
    return (record.source_system, record.device, record.entry_method, record.synthetic is True)


def _series(records, field):
    grouped = {}
    for record in records:
        value = _number(record.values.get(field) if isinstance(record.values, dict) else None)
        if value is None:
            continue
        grouped.setdefault(_identity(record), []).append((record.local_date, value))
    result, ambiguous = [], 0
    for (source, device, method, synthetic), points in sorted(grouped.items()):
        clean, skipped = unambiguous_points(points)
        ambiguous += len(skipped)
        stats = _average(clean)
        if not stats:
            continue
        result.append({
            'source': source, 'device': device, 'entry_method': method, 'synthetic': synthetic,
            'class_label': 'test' if synthetic else 'personal', 'field': field,
            'series_id': summary_series_token((field, source, device, method, synthetic)),
            'ambiguous_days': len(skipped), **stats,
        })
    return result, ambiguous


def _net_carb_days(records):
    grouped = {}
    for record in records:
        values = record.values if isinstance(record.values, dict) else {}
        carbs = _number(values.get('total_carbohydrates'))
        fiber = _number(values.get('fiber'))
        if carbs is None or fiber is None:
            continue
        net = net_carbohydrates(carbs, fiber)
        if net.get('status') != 'calculated' or net.get('value') is None:
            continue
        grouped.setdefault(_identity(record), []).append((record.local_date, net['value']))
    result, ambiguous = [], 0
    for (source, device, method, synthetic), points in sorted(grouped.items()):
        clean, skipped = unambiguous_points(points)
        ambiguous += len(skipped)
        stats = _average(clean)
        if not stats:
            continue
        result.append({
            'source': source, 'device': device, 'entry_method': method, 'synthetic': synthetic,
            'class_label': 'test' if synthetic else 'personal', 'field': 'net_carbohydrates',
            'series_id': summary_series_token(('net_carbohydrates', source, device, method, synthetic)),
            'ambiguous_days': len(skipped), **stats,
        })
    return result, ambiguous


def _clinical(owner, include_synthetic):
    rows = _owned(owner, ClinicalItem, include_synthetic).filter(current=True)
    def item(row):
        return {'id': str(row.id), 'name': row.name, 'detail': row.detail,
                'recorded_on': row.recorded_on.isoformat()}
    return {
        'labs': [item(row) for row in rows.filter(kind='lab')],
        'medications': [item(row) for row in rows.filter(kind='medication')],
        'diagnoses': [item(row) for row in rows.filter(kind='diagnosis')],
    }


def fitness_plan(owner, today=None, include_synthetic=False):
    start, end = plan_window(today)
    summaries = _owned(owner, SummaryRecord, include_synthetic).filter(
        deleted_at__isnull=True, local_date__gte=start, local_date__lte=end,
        kind__in=DAILY_FIELDS).select_related('connection')
    diary = _owned(owner, DietEntry, include_synthetic).filter(
        deleted_at__isnull=True, local_date__gte=start, local_date__lte=end)
    eligible, evidence = partition_records(summaries)
    by_kind = {kind: [row for row in eligible if row.kind == kind] for kind in DAILY_FIELDS}
    analysis, ambiguous = {}, 0
    for kind, fields in DAILY_FIELDS.items():
        for field in fields:
            series, skipped = _series(by_kind[kind], field)
            analysis[field] = series
            ambiguous += skipped
    nets, skipped = _net_carb_days(by_kind['nutrition'])
    analysis['net_carbohydrates'] = nets
    evidence['ambiguous_days'] = ambiguous + skipped
    goals = saved_goals(owner)
    protein_target = next((goal['value'] for goal in goals if goal['key'] == 'protein'), None)
    return {
        'window_days': PLAN_DAYS,
        'start': start.isoformat(),
        'end': end.isoformat(),
        'analysis': analysis,
        'goals': goals,
        'protein_target_g': protein_target,
        'common_meals': common_meals(diary),
        'trends': trend_lines(owner, start, end, include_synthetic),
        'diary': [{'local_date': row.local_date.isoformat(), 'meal': row.meal,
                   'description': row.description, 'source': row.source_system,
                   'calories': None if row.calories is None else format(row.calories, 'f'),
                   'protein_g': None if row.protein_g is None else format(row.protein_g, 'f'),
                   'fiber_g': None if row.fiber_g is None else format(row.fiber_g, 'f')}
                  for row in diary],
        'clinical': _clinical(owner, include_synthetic),
        'evidence': evidence,
        'projection': {
            'writes': False,
            'status': 'unavailable',
            'detail': 'This read does not refresh stored device sources.',
        },
        'rules': [
            'The plan uses the latest 90 local days.',
            'Days without a record are unknown, not zero.',
            'Steps, sleep and workouts from different sources and personal or test classes stay separate.',
            'Unresolved imported Oura activity and recovery, and every derived row, stay out of these averages.',
            'More than one eligible value on the same day and series stays unknown.',
            'Food calories stay separate from active and total calories burned. Burned calories are the device number, kept by source.',
            'Diet analysis uses food calories, protein, fiber and net carbs when both carbohydrate inputs exist.',
            'The diary keeps the meals. Current labs, medications and diagnoses remain when they are older than 90 days.',
        ],
    }


def common_meals(entries):
    grouped = {}
    for row in entries:
        key = ' '.join(row.description.lower().split())
        if len(key) < 2:
            continue
        tidy = ' '.join(row.description.split())
        bucket = grouped.setdefault(key, {'description': tidy, 'times': 0, 'last_date': row.local_date})
        bucket['times'] += 1
        if row.local_date >= bucket['last_date']:
            bucket['last_date'] = row.local_date
            bucket['description'] = tidy
    ranked = [item for item in grouped.values() if item['times'] >= 2]
    ranked.sort(key=lambda item: (-item['times'], item['description'].lower()))
    return [{'description': item['description'], 'times': item['times'], 'last_date': item['last_date'].isoformat()}
            for item in ranked[:8]]


def saved_goals(owner):
    target = NutritionTargets.objects.filter(owner=owner).first()
    values = target.values if target and isinstance(target.values, dict) else {}
    labels = [(key, label, unit) for key, label, unit in SCHEMAS['nutrition']]
    labels += [('steps', 'Steps', 'steps'), ('sleep_hours', 'Sleep', 'hours')]
    goals = []
    for key, label, unit in labels:
        raw = values.get(key)
        if raw in (None, ''):
            continue
        goals.append({'key': key, 'label': label, 'value': str(raw), 'unit': unit})
    return goals


def trend_lines(owner, start, end, include_synthetic):
    from tracking.trends import observations
    chosen = [('measurements:' + metric, metric.title()) for metric in METRICS]
    chosen += [('recovery:sleep_minutes', 'Sleep'), ('recovery:hrv_ms', 'HRV'),
               ('recovery:resting_hr_bpm', 'Resting heart rate'), ('recovery:readiness', 'Readiness')]
    lines = []
    for metric, title in chosen:
        result = observations(owner, metric, start, end, include_synthetic)
        grouped = {}
        for row in result['rows']:
            grouped.setdefault(row.get('series_id') or row['source'], []).append(row)
        series = []
        for series_id, rows in grouped.items():
            first, last = rows[0], rows[-1]
            change = None
            if len(rows) >= 2:
                change = format(Decimal(str(last['value'])) - Decimal(str(first['value'])), 'f')
            series.append({
                'source': first['source'], 'series_id': series_id,
                'observed': len(rows), 'unit': last['unit'] or '',
                'first_date': first['date'].isoformat(), 'first': str(first['value']),
                'last_date': last['date'].isoformat(), 'last': str(last['value']),
                'change': change,
            })
        lines.append({'metric': metric, 'title': title, 'series': series,
                      'truncated': result['truncated'], 'evidence': result.get('evidence') or {},
                      'href': f'/trends/?metric={metric}&start={start.isoformat()}&end={end.isoformat()}'})
    return lines


def replace_current_lab(owner, name, synthetic):
    ClinicalItem.objects.filter(owner=owner, kind='lab', current=True, synthetic=synthetic, name__iexact=name.strip()).update(current=False)
