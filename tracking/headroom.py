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
    if sleep['drain']:
        drains.append(sleep['drain'])
    elif sleep['missing']:
        missing.append(sleep['missing'])
    food = _food(owner, day, include_synthetic, status, goals.get('calories'))
    if food['drain']:
        drains.append(food['drain'])
    elif food['missing']:
        missing.append(food['missing'])
    steps = _steps(owner, day, include_synthetic, goals.get('steps'))
    if steps['drain']:
        drains.append(steps['drain'])
    elif steps['missing']:
        missing.append(steps['missing'])
    for metric in STATE_METRICS:
        rating = ratings.get(metric)
        if rating is not None and rating <= LOW_RATING:
            drains.append({'key': 'rating', 'text': f'{metric} is {rating} out of 10'})
    action, alternatives = _actions(status, drains, len(ratings), day)
    return {
        'display': DISPLAY,
        'formula': DAILY_STATE_FORMULA,
        'score': None if result is None else format(result.quantize(Decimal('0.01')), 'f'),
        'scale': '0 to 100. Higher means more capacity. This is the Daily State check-in from confirmed mood, energy, and focus. It is not a prediction or a verdict.',
        'status': status,
        'status_label': status_label,
        'summary': _summary(result, drains),
        'action': action,
        'alternatives': alternatives,
        'factors': [item['text'] for item in drains],
        'missing': missing,
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


def _sleep(owner, day, include_synthetic):
    rows = _scoped(SummaryRecord.objects.filter(
        owner=owner, kind='recovery', local_date=day, deleted_at__isnull=True,
    ), include_synthetic)
    short = []
    known = False
    for row in rows:
        minutes = _decimal((row.values or {}).get('sleep_minutes'))
        if minutes is None:
            continue
        known = True
        if minutes < SLEEP_SHORT_MINUTES:
            short.append(f'{_source(row)} is {_hours(minutes)}')
    if short:
        return {'drain': {'key': 'sleep', 'text': f'short sleep from {_join(short)}'}, 'missing': None}
    if not known:
        return {'drain': None, 'missing': 'sleep'}
    return {'drain': None, 'missing': None}


def _food(owner, day, include_synthetic, status, goal):
    meals = list(_scoped(DietEntry.objects.filter(
        owner=owner, local_date=day, deleted_at__isnull=True,
    ), include_synthetic))
    total = None
    for meal in meals:
        if meal.calories is not None:
            total = (total or Decimal('0')) + meal.calories
    nutrition = _scoped(SummaryRecord.objects.filter(
        owner=owner, kind='nutrition', local_date=day, deleted_at__isnull=True,
    ), include_synthetic)
    summary = nutrition.first()
    summary_calories = _decimal((summary.values or {}).get('calories')) if summary else None
    if total is None:
        total = summary_calories
    if total is None and not meals and summary is None:
        if status in {'stretched', 'running_low'}:
            return {'drain': {'key': 'food', 'text': 'no meal is logged'}, 'missing': None}
        return {'drain': None, 'missing': 'food'}
    if total is None:
        return {'drain': None, 'missing': 'food calories'}
    if goal is not None and goal > 0 and total < goal * HALF:
        return {'drain': {'key': 'food', 'text': 'food is under half the calorie goal'}, 'missing': None}
    return {'drain': None, 'missing': None}


def _steps(owner, day, include_synthetic, goal):
    rows = list(_scoped(SummaryRecord.objects.filter(
        owner=owner, kind='activity', local_date=day, deleted_at__isnull=True,
    ), include_synthetic))
    known = []
    for row in rows:
        steps = _decimal((row.values or {}).get('steps'))
        if steps is not None:
            known.append((row, steps))
    if not known:
        return {'drain': None, 'missing': 'steps'}
    if goal is None or goal <= 0 or any(steps >= goal * HALF for _, steps in known):
        return {'drain': None, 'missing': None}
    names = _join(_source(row) for row, _steps in known)
    return {'drain': {'key': 'steps', 'text': f'steps from {names} are under half the goal'}, 'missing': None}


def _source(row):
    if row.device:
        return f'{row.source_system} · {row.device}'
    return row.source_system


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
