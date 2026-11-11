"""Daily Today screen: calorie hero, compact chips, meals by type."""
from decimal import Decimal, InvalidOperation

from django.urls import reverse

from tracking.models import DietEntry, JournalEntry, Measurement, NutritionTargets, SummaryRecord
from tracking.summary_evidence import HISTORY_HREF, CALCULATION_NOTICE, resolve_metric

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


ALTERNATIVE_LIMIT = 8


def _alternative_view(decision, kind):
    """Show at most eight candidates. A longer list says how many remain and where history is."""
    full = list(decision.get('alternatives') or []) if decision.get('status') == 'selection_required' else []
    shown = full[:ALTERNATIVE_LIMIT]
    href = ''
    if len(full) > ALTERNATIVE_LIMIT:
        href = reverse('summary_list', args=[kind])
        if any(item.get('stored_synthetic') for item in full):
            href += '?synthetic=1'
    return {
        'alternatives': shown,
        'alternative_total': len(full),
        'alternative_shown': len(shown),
        'history_href': href,
        'history_label': 'Activity history' if kind == 'activity' else 'Nutrition history',
    }


def _history_exclusion(decisions):
    """Legacy and derived exclusions only. A null metric on an eligible row is not history."""
    unresolved, unavailable = set(), set()
    for decision in decisions:
        for item in decision.get('excluded') or []:
            if item.get('eligibility_reason') == 'unknown':
                continue
            summary_id = item.get('summary_id')
            if item.get('eligibility_status') == 'unresolved':
                unresolved.add(summary_id)
            elif item.get('eligibility_status') == 'unavailable':
                unavailable.add(summary_id)
    return len(unresolved), len(unavailable)


def _chip(key, label, unit, value, goal, *, protein=False, status='unavailable', view=None):
    width, attention, remaining = _progress(value, goal)
    limited = status == 'selection_required'
    chip = {
        'key': key,
        'label': label,
        'unit': unit,
        'value': None if limited else _format(value),
        'goal': _format(goal),
        'logged': value is not None and not limited,
        'bar': None if limited else width,
        'protein': protein,
        'attention': attention,
        'remaining': None if limited or remaining is None else _format(remaining),
        'status': status,
        'limitation': 'More than one record. This number stays unknown.' if limited else '',
    }
    chip.update(view or _alternative_view({'status': status}, 'activity'))
    return chip


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
    nutrition_rows = list(scoped(SummaryRecord.objects.filter(
        owner=owner, kind='nutrition', local_date=day, deleted_at__isnull=True,
    )).select_related('connection'))
    activity_rows = list(scoped(SummaryRecord.objects.filter(
        owner=owner, kind='activity', local_date=day, deleted_at__isnull=True,
    )).select_related('connection'))

    def fallback(current, key):
        if current is not None:
            return current, {'status': 'value', 'reason': 'meals', 'value': _format(current),
                             'alternatives': [], 'excluded': []}
        decision = resolve_metric(nutrition_rows, key)
        if decision['status'] == 'value':
            return _number(decision['value']), decision
        return None, decision

    calories, calorie_decision = fallback(calories, 'calories')
    protein, protein_decision = fallback(protein, 'protein')
    fiber, fiber_decision = fallback(fiber, 'fiber')
    steps_decision = resolve_metric(activity_rows, 'steps')
    steps = _number(steps_decision['value']) if steps_decision['status'] == 'value' else None
    weight = scoped(Measurement.objects.filter(
        owner=owner, metric='weight', deleted_at__isnull=True, local_date__lte=day,
    )).order_by('-local_date', '-created_at').first()

    calorie_status = calorie_decision['status']
    calorie_limited = calorie_status == 'selection_required'
    cal_bar, cal_attention, cal_remaining = _progress(None if calorie_limited else calories, goals['calories'])
    calories_hero = {
        'logged': calories is not None and not calorie_limited,
        'value': None if calorie_limited else _format(calories),
        'goal': _format(goals['calories']),
        'remaining': None if calorie_limited or cal_remaining is None else _format(cal_remaining),
        'remaining_positive': cal_remaining is not None and cal_remaining >= 0 and not calorie_limited,
        'bar': None if calorie_limited else cal_bar,
        'attention': False if calorie_limited else cal_attention,
        'near_goal': False if calorie_limited else cal_attention,
        'status': calorie_status,
        'limitation': 'More than one record. This number stays unknown.' if calorie_limited else '',
        **_alternative_view(calorie_decision, 'nutrition'),
    }
    chips = [
        _chip('protein', 'Protein', 'g', protein, goals['protein'], protein=True,
              status=protein_decision['status'], view=_alternative_view(protein_decision, 'nutrition')),
        _chip('fiber', 'Fiber', 'g', fiber, goals['fiber'], status=fiber_decision['status'],
              view=_alternative_view(fiber_decision, 'nutrition')),
        _chip('steps', 'Steps', '', steps, goals['steps'], status=steps_decision['status'],
              view=_alternative_view(steps_decision, 'activity')),
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
    unresolved_count, unavailable_count = _history_exclusion(
        (steps_decision, calorie_decision, protein_decision, fiber_decision))
    return {
        'day': day,
        'calories': calories_hero,
        'chips': chips,
        'cards': cards,
        'meal_sections': meal_sections,
        'meal_count': len(meal_rows),
        'checkin': scoped(JournalEntry.objects.filter(
            owner=owner, deleted_at__isnull=True, local_date=day)).exists(),
        'evidence': {
            'notice': CALCULATION_NOTICE,
            'history_href': HISTORY_HREF,
            'steps': steps_decision,
            'calories': calorie_decision,
            'protein': protein_decision,
            'fiber': fiber_decision,
            'selection_required': any(item['status'] == 'selection_required'
                                      for item in (steps_decision, calorie_decision, protein_decision, fiber_decision)),
            'unresolved_count': unresolved_count,
            'unavailable_count': unavailable_count,
        },
    }
