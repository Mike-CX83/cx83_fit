"""Explicit food-diary push. A pasted day is stored. Nothing is pulled from MyFitnessPal."""
import hashlib
from datetime import date
from decimal import Decimal, InvalidOperation

from tracking.models import DietEntry
from tracking.plan import plan_window

MEALS = {'breakfast', 'lunch', 'dinner', 'snack'}


def _optional(parts, index):
    if index >= len(parts) or parts[index] == '':
        return None
    try:
        number = Decimal(parts[index])
    except InvalidOperation:
        raise ValueError('Calories, protein, and fiber must be numbers when present.') from None
    if number < 0 or number > Decimal('99999'):
        raise ValueError('A diary number is outside the supported range.')
    return number.quantize(Decimal('0.1'))


def parse_diary_push(text, today=None):
    """Lines look like: 2026-11-07 breakfast eggs and toast | 420 | 32 | 4"""
    if not isinstance(text, str) or len(text) > 20000:
        raise ValueError('Paste at most 20,000 characters.')
    start, end = plan_window(today)
    rows = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if len(rows) >= 90:
            raise ValueError('Push at most 90 meals at a time.')
        pieces = [part.strip() for part in line.split('|')]
        head = pieces[0].split(None, 2)
        if len(head) < 3:
            raise ValueError(f'Line {number}: use the date, meal, and food, then optional calories, protein, and fiber.')
        try:
            day = date.fromisoformat(head[0])
        except ValueError:
            raise ValueError(f'Line {number}: use a YYYY-MM-DD date.') from None
        meal = head[1].lower()
        description = head[2].strip()
        if day < start or day > end:
            raise ValueError(f'Line {number}: that date is outside the current 90 day window.')
        if meal not in MEALS or not description or len(description) > 500:
            raise ValueError(f'Line {number}: use breakfast, lunch, dinner, or snack, and a short food description.')
        identity = hashlib.sha256(f'{day.isoformat()}|{meal}|{" ".join(description.lower().split())}'.encode()).hexdigest()[:32]
        rows.append({
            'local_date': day, 'meal': meal, 'description': description,
            'calories': _optional(pieces, 1), 'protein_g': _optional(pieces, 2), 'fiber_g': _optional(pieces, 3),
            'source_record_id': identity,
        })
    if not rows:
        raise ValueError('Paste at least one meal.')
    return rows


def store_diary_push(owner, rows):
    for row in rows:
        DietEntry.objects.update_or_create(
            owner=owner, source_system='myfitnesspal', source_record_id=row['source_record_id'],
            defaults={**row, 'deleted_at': None, 'synthetic': False},
        )
    return len(rows)
