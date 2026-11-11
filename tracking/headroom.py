"""Your Headroom is a display of Daily State, not a second score.

daily-state-1 stays the number: the mean of confirmed mood, energy, and focus
ratings, times 10, and only when at least two of those three exist. Higher means
more capacity. Bands, factors, and the next action explain that number. They do
not change it. A missing record stays missing. Anger, loneliness, and stress are
not collected, so they are never inferred from mood.
"""
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from .domain import parse_day
from .journal_continuity import score_day
from .journal_registry import DAILY_STATE_FORMULA, STATE_METRICS
from .models import DietEntry, JournalObservation, JournalScore, NutritionTargets, SummaryRecord
from .sobriety_pattern import SLEEP_SHORT_MINUTES
from .summary_evidence import CALCULATION_NOTICE, HISTORY_HREF, evidence_envelope, resolve_metric

DISPLAY = 'headroom-display-1'
CHANGE_POINTS = Decimal('5')
LOW_RATING = 3
HALF = Decimal('0.5')


def headroom(owner, day, *, include_synthetic=False):
    """Return the Headroom card for one local date. The score is Daily State."""
    day = parse_day(day)
    state = score_day(owner, day.isoformat(), include_synthetic=include_synthetic)['daily_state']
    result = None if state['result'] is None else Decimal(state['result'])
    status, status_label = _status(result)
    row = JournalScore.objects.get(pk=state['id'])
    ratings = _ratings(owner, day, include_synthetic)
    goals = _goals(owner)
    drains = []
    missing = [name for name in STATE_METRICS if name not in ratings]
    sleep = _sleep(owner, day, include_synthetic)
    food = _food(owner, day, include_synthetic, status, goals.get('calories'))
    steps = _steps(owner, day, include_synthetic, goals.get('steps'))
    limitations = []
    for item in (sleep, food, steps):
        if item['drain']:
            drains.append(item['drain'])
        elif item['missing']:
            missing.append(item['missing'])
        if item['limitation'] and item['limitation'] not in limitations:
            limitations.append(item['limitation'])
    for metric in STATE_METRICS:
        rating = ratings.get(metric)
        if rating is not None and rating <= LOW_RATING:
            drains.append({'key': 'rating', 'text': f'{metric} is {rating} out of 10'})
    action, alternatives = _actions(status, drains, len(ratings), day)
    return {
        'display': DISPLAY,
        'formula': DAILY_STATE_FORMULA,
        'score': None if result is None else format(result.quantize(Decimal('0.01')), 'f'),
        'bar': None if result is None else float(min(Decimal('100'), max(Decimal('0'), result))),
        'scale': '0 to 100. Higher means more capacity. This is the Daily State check-in from confirmed mood, energy, and focus. It is not a prediction or a verdict.',
        'status': status,
        'status_label': status_label,
        'summary': _summary(result, drains),
        'action': action,
        'alternatives': alternatives,
        'factors': [item['text'] for item in drains],
        'missing': missing,
        'limitations': limitations,
        'history_href': HISTORY_HREF if any(item['history'] for item in (sleep, food, steps)) else '',
        'uncollected': 'Anger, loneliness, and stress are not collected.',
        'change': _change(owner, day, result, include_synthetic),
        'updated': date_format(timezone.localtime(row.computed_at), 'g:i A T'),
        'coverage': state['coverage'],
    }


def _status(result):
    if result is None:
        return 'unknown', 'Not enough to score'
    if result >= Decimal('70'):
        return 'steady', 'Steady'
    if result >= Decimal('40'):
        return 'stretched', 'Stretched'
    return 'running_low', 'Running low'


def _summary(result, drains):
    if drains:
        text = _join(item['text'] for item in drains)
        return f'{text[0].upper()}{text[1:]}. That may be adding up.'
    if result is None:
        return 'At least two of mood, energy, and focus are needed. A missing rating stays missing.'
    return 'No separate drain is on file for sleep, food, or steps.'


def _join(parts):
    parts = list(parts)
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f'{parts[0]} and {parts[1]}'
    return f'{", ".join(parts[:-1])}, and {parts[-1]}'


def _scoped(query, include_synthetic):
    if include_synthetic:
        return query
    return query.filter(synthetic=False)


def _ratings(owner, day, include_synthetic):
    rows = _scoped(JournalObservation.objects.filter(
        owner=owner, local_date=day, deleted_at__isnull=True, metric_key__in=STATE_METRICS,
    ), include_synthetic)
    found = {}
    for row in rows:
        value = (row.value_json or {}).get('rating')
        if row.value_state == 'observed' and type(value) is int and not isinstance(value, bool):
            found[row.metric_key] = min(found.get(row.metric_key, value), value)
    return found


def _goals(owner):
    target = NutritionTargets.objects.filter(owner=owner).first()
    values = target.values if target and isinstance(target.values, dict) else {}
    return {'calories': _decimal(values.get('calories')), 'steps': _decimal(values.get('steps'))}


def _decimal(raw):
    if raw in (None, ''):
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _records(owner, day, kind, include_synthetic):
    return list(_scoped(SummaryRecord.objects.filter(
        owner=owner, kind=kind, local_date=day, deleted_at__isnull=True,
    ), include_synthetic).select_related('connection'))


def _history(decision):
    return any(item.get('eligibility_reason') != 'unknown' for item in decision.get('excluded') or [])


def _input(decision, missing):
    """One eligible value can explain the score. A conflict or exclusion does not become zero."""
    history = _history(decision)
    if decision['status'] == 'selection_required':
        notes = ['More than one record. This number stays unknown.']
        if history:
            notes.append(CALCULATION_NOTICE)
        return {'drain': None, 'missing': None, 'history': history, 'limitation': ' '.join(notes)}
    if decision['status'] != 'value':
        if history:
            return {'drain': None, 'missing': None, 'history': True, 'limitation': CALCULATION_NOTICE}
        return {'drain': None, 'missing': missing, 'history': False, 'limitation': None}
    return None


def _kept(result, decision):
    if _history(decision):
        result['history'] = True
        result['limitation'] = CALCULATION_NOTICE
    return result


def _sleep(owner, day, include_synthetic):
    decision = resolve_metric(_records(owner, day, 'recovery', include_synthetic), 'sleep_minutes')
    blocked = _input(decision, 'sleep')
    if blocked:
        return blocked
    minutes = _decimal(decision['value'])
    if minutes is not None and minutes < SLEEP_SHORT_MINUTES:
        return _kept({'drain': {'key': 'sleep', 'text': f'short sleep from {_label(decision["alternatives"][0])} is {_hours(minutes)}'},
                      'missing': None, 'history': False, 'limitation': None}, decision)
    return _kept({'drain': None, 'missing': None, 'history': False, 'limitation': None}, decision)


def _food(owner, day, include_synthetic, status, goal):
    meals = list(_scoped(DietEntry.objects.filter(
        owner=owner, local_date=day, deleted_at__isnull=True,
    ), include_synthetic))
    total = None
    for meal in meals:
        if meal.calories is not None:
            total = (total or Decimal('0')) + meal.calories
    records = _records(owner, day, 'nutrition', include_synthetic)
    decision = resolve_metric(records, 'calories')
    present = any(evidence_envelope(record)['eligibility_status'] == 'eligible' for record in records)
    if total is None and decision['status'] == 'value':
        total = _decimal(decision['value'])
    if total is None and decision['status'] == 'selection_required':
        return _input(decision, None)
    if total is None and present:
        return _kept({'drain': None, 'missing': 'food calories', 'history': False, 'limitation': None}, decision)
    if total is None and _history(decision):
        return _input(decision, None)
    return _food_result(total, meals, status, goal, decision if decision['status'] == 'value' else None)


def _food_result(total, meals, status, goal, decision):
    result = {'drain': None, 'missing': None, 'history': False, 'limitation': None}
    if total is None and not meals:
        if status in {'stretched', 'running_low'}:
            result['drain'] = {'key': 'food', 'text': 'no meal is logged'}
        else:
            result['missing'] = 'food'
    elif total is None:
        result['missing'] = 'food calories'
    elif goal is not None and goal > 0 and total < goal * HALF:
        result['drain'] = {'key': 'food', 'text': 'food is under half the calorie goal'}
    if decision is not None:
        return _kept(result, decision)
    return result


def _steps(owner, day, include_synthetic, goal):
    decision = resolve_metric(_records(owner, day, 'activity', include_synthetic), 'steps')
    blocked = _input(decision, 'steps')
    if blocked:
        return blocked
    steps = _decimal(decision['value'])
    if steps is None or goal is None or goal <= 0 or steps >= goal * HALF:
        return _kept({'drain': None, 'missing': None, 'history': False, 'limitation': None}, decision)
    return _kept({'drain': {'key': 'steps', 'text': f'steps from {_label(decision["alternatives"][0])} are under half the goal'},
                  'missing': None, 'history': False, 'limitation': None}, decision)


def _label(alternative):
    if alternative.get('device'):
        return f"{alternative['source_system']} · {alternative['device']}"
    return alternative['source_system']


def _hours(minutes):
    hours = (minutes / Decimal('60')).quantize(Decimal('0.1'))
    text = format(hours, 'f')
    if text.endswith('.0'):
        text = text[:-2]
    unit = 'hour' if text == '1' else 'hours'
    return f'{text} {unit}'


def _actions(status, drains, observed_count, day):
    keys = {item['key'] for item in drains}
    diary = f"{reverse('diary')}?local_date={day.isoformat()}"
    journal = reverse('journal')
    options = []

    def add(key, label, href=None):
        if any(item['key'] == key for item in options):
            return
        options.append({'key': key, 'label': label, 'href': href})

    if 'food' in keys:
        add('eat', 'Get something to eat', diary)
    if 'sleep' in keys:
        add('rest', 'Rest')
    if 'rating' in keys:
        add('break', 'Take a short break')
    if 'steps' in keys and 'sleep' not in keys:
        add('walk', 'Take a short walk')
    if status == 'running_low':
        add('connect', 'Reach out to someone')
    if 'sleep' in keys and 'food' not in keys:
        add('pause', 'Pause a demanding task')
    if status == 'unknown' and observed_count < 2:
        add('rate', 'Add mood, energy, or focus', journal)
    if not options:
        add('hold', 'Nothing to change from what is on file')
    return options[0], options[1:3]


def _change(owner, day, result, include_synthetic):
    if result is None:
        return None
    earlier = _scoped(JournalScore.objects.filter(
        owner=owner, kind='daily_state', formula_version=DAILY_STATE_FORMULA,
        result__isnull=False, local_date__lt=day, local_date__gte=day - timedelta(days=13),
    ), include_synthetic).order_by('-local_date').first()
    if earlier is None or earlier.result is None:
        return None
    delta = result - earlier.result
    shown = format(earlier.result.quantize(Decimal('0.01')), 'f')
    when = date_format(earlier.local_date, 'M j')
    if delta >= CHANGE_POINTS:
        direction = 'Up'
    elif delta <= -CHANGE_POINTS:
        direction = 'Down'
    else:
        direction = 'About the same'
    return f'{direction} from {shown} on {when}.'
