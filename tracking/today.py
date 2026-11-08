"""Daily Today screen: calorie hero, compact chips, meals by type."""
from decimal import Decimal, InvalidOperation

from tracking.models import DietEntry, JournalEntry, Measurement, NutritionTargets, SummaryRecord

MEAL_ORDER = ('breakfast', 'lunch', 'dinner', 'snack')
MEAL_LABELS = dict(DietEntry.MEALS)


def _number(raw):
    if raw in (None, ''):
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _format(value, *, places=None):
    if value is None:
        return None
    if places is not None:
        return format(value.quantize(Decimal(10) ** -places), 'f')
    text = format(value.normalize(), 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text or '0'


def _goal_map(owner):
    target = NutritionTargets.objects.filter(owner=owner).first()
    values = target.values if target and isinstance(target.values, dict) else {}
    return {
        'calories': _number(values.get('calories')),
        'protein': _number(values.get('protein')),
        'fiber': _number(values.get('fiber')),
        'steps': _number(values.get('steps')),
    }


def _progress(value, goal):
    if value is None or goal in (None, 0) or goal <= 0:
        return None, False, None
    percent = float((value / goal) * 100)
    width = min(100, max(0, percent))
    attention = 85 <= percent < 100 or percent > 105
    remaining = goal - value
    return width, attention, remaining


def _chip(key, label, unit, value, goal, *, protein=False):
    width, attention, remaining = _progress(value, goal)
    return {
        'key': key,
        'label': label,
        'unit': unit,
        'value': _format(value),
        'goal': _format(goal),
        'logged': value is not None,
        'bar': width,
        'protein': protein,
        'attention': attention,
        'remaining': _format(remaining) if remaining is not None else None,
    }


def day_metrics(owner, day, *, include_synthetic=False):
    goals = _goal_map(owner)

    def scoped(query):
        return query if include_synthetic else query.filter(synthetic=False)

    meal_rows = list(scoped(
        DietEntry.objects.filter(owner=owner, deleted_at__isnull=True, local_date=day)
    ).order_by('meal', 'created_at'))
    calories = protein = fiber = None
    for meal in meal_rows:
        if meal.calories is not None:
            calories = (calories or Decimal('0')) + meal.calories
        if meal.protein_g is not None:
            protein = (protein or Decimal('0')) + meal.protein_g
        if meal.fiber_g is not None:
            fiber = (fiber or Decimal('0')) + meal.fiber_g
    nutrition = scoped(SummaryRecord.objects.filter(
        owner=owner, kind='nutrition', local_date=day, deleted_at__isnull=True,
    )).first()
    if nutrition and isinstance(nutrition.values, dict):
        if calories is None:
            calories = _number(nutrition.values.get('calories'))
        if protein is None:
            protein = _number(nutrition.values.get('protein'))
        if fiber is None:
            fiber = _number(nutrition.values.get('fiber'))
    activity = scoped(SummaryRecord.objects.filter(
        owner=owner, kind='activity', local_date=day, deleted_at__isnull=True,
    )).first()
    steps = _number(activity.values.get('steps')) if activity and isinstance(activity.values, dict) else None
    weight = scoped(Measurement.objects.filter(
        owner=owner, metric='weight', deleted_at__isnull=True, local_date__lte=day,
    )).order_by('-local_date', '-created_at').first()

    cal_bar, cal_attention, cal_remaining = _progress(calories, goals['calories'])
    calories_hero = {
        'logged': calories is not None,
        'value': _format(calories),
        'goal': _format(goals['calories']),
        'remaining': _format(cal_remaining) if cal_remaining is not None else None,
        'remaining_positive': cal_remaining is not None and cal_remaining >= 0,
        'bar': cal_bar,
        'attention': cal_attention,
        'near_goal': cal_attention,
    }
    chips = [
        _chip('protein', 'Protein', 'g', protein, goals['protein'], protein=True),
        _chip('fiber', 'Fiber', 'g', fiber, goals['fiber']),
        _chip('steps', 'Steps', '', steps, goals['steps']),
        {
            'key': 'weight',
            'label': 'Weight',
            'unit': weight.unit if weight else 'kg',
            'value': _format(_number(weight.value), places=3) if weight else None,
            'goal': None,
            'logged': weight is not None,
            'bar': None,
            'protein': False,
            'attention': False,
            'remaining': None,
            'sub': weight.local_date.isoformat() if weight else None,
        },
    ]
    # Keep a cards list for older callers / tests that look for weight value text.
    cards = [
        {
            'key': 'calories', 'label': 'Calories', 'unit': 'kcal',
            'value': calories_hero['value'], 'goal': calories_hero['goal'],
            'logged': calories_hero['logged'], 'bar': calories_hero['bar'],
            'protein': False, 'attention': bool(calories_hero['attention']),
        },
        *chips,
    ]
    by_meal = {key: [] for key in MEAL_ORDER}
    for meal in meal_rows:
        by_meal.setdefault(meal.meal, []).append(meal)
    meal_sections = [
        {'key': key, 'label': MEAL_LABELS.get(key, key.title()), 'items': by_meal.get(key, [])}
        for key in MEAL_ORDER
    ]
    return {
        'day': day,
        'calories': calories_hero,
        'chips': chips,
        'cards': cards,
        'meal_sections': meal_sections,
        'meal_count': len(meal_rows),
        'checkin': scoped(JournalEntry.objects.filter(
            owner=owner, deleted_at__isnull=True, local_date=day)).exists(),
    }
