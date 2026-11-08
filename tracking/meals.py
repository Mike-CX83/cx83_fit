"""One meal row. The diary page and ChatGPT use this same save."""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from tracking.models import DietEntry
from tracking.plan import plan_window


def _decimal(raw, label):
    if raw in (None, ''):
        return None
    try:
        number = Decimal(str(raw).strip())
    except (InvalidOperation, AttributeError):
        raise ValueError(f'{label} must be a number.') from None
    if number < 0 or number > Decimal('99999'):
        raise ValueError(f'{label} is outside the supported range.')
    return number.quantize(Decimal('0.1'))


def _day(raw):
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError):
        raise ValueError('Use a YYYY-MM-DD date.') from None


def save_meal(owner, local_date, meal, description, *, calories=None, protein_g=None, fiber_g=None,
              source_system='manual', source_record_id='', synthetic=False):
    start, end = plan_window(timezone.localdate())
    day = _day(local_date)
    if day < start or day > end:
        raise ValueError('Diet notes belong in the current 90 day window.')
    if meal not in dict(DietEntry.MEALS):
        raise ValueError('Choose breakfast, lunch, dinner, or a snack.')
    text = (description or '').strip()
    if not text or len(text) > 500:
        raise ValueError('Describe the meal in 500 characters or less.')
    if source_system not in {'manual', 'mcp', 'myfitnesspal'}:
        raise ValueError('Use a supported meal source.')
    if type(synthetic) is not bool:
        raise ValueError('synthetic must be true or false.')
    fields = {
        'local_date': day, 'meal': meal, 'description': text,
        'calories': _decimal(calories, 'Calories'), 'protein_g': _decimal(protein_g, 'Protein'),
        'fiber_g': _decimal(fiber_g, 'Fiber'), 'synthetic': synthetic, 'deleted_at': None,
    }
    if source_record_id:
        row, _created = DietEntry.objects.update_or_create(
            owner=owner, source_system=source_system, source_record_id=str(source_record_id), defaults=fields)
    else:
        row = DietEntry.objects.create(owner=owner, source_system=source_system, source_record_id='', **fields)
    return {
        'id': str(row.id), 'local_date': row.local_date.isoformat(), 'meal': row.meal,
        'description': row.description, 'calories': None if row.calories is None else format(row.calories, 'f'),
        'protein_g': None if row.protein_g is None else format(row.protein_g, 'f'),
        'fiber_g': None if row.fiber_g is None else format(row.fiber_g, 'f'),
        'source_system': row.source_system, 'synthetic': row.synthetic,
    }
