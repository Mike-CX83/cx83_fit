"""Copy stored device days into the daily log.

This reads records the dashboard already holds. It does not contact a device,
fill a missing number with zero, or add one device to another.
"""
import json
from datetime import date
from decimal import Decimal

from django.utils import timezone

from tracking.models import OuraRecord, SummaryRecord
from tracking.plan import plan_window
from tracking.summaries import validate_values


def _whole(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = Decimal(str(value))
    if number < 0 or number != number.to_integral_value():
        return None
    return format(number.quantize(Decimal('1')), 'f')


def _minutes(seconds):
    whole = _whole(seconds)
    if whole is None:
        return None
    return format((Decimal(whole) / Decimal(60)).quantize(Decimal('0.001')), 'f')


def _day(value, start, end):
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    if parsed < start or parsed > end:
        return None
    return parsed


def _row(raw):
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _save(owner, kind, day, source_id, values, device, synthetic):
    clean = validate_values(kind, values, device)
    existing = SummaryRecord.objects.filter(
        owner=owner, kind=kind, source_system='oura', local_date=day,
    ).first()
    if existing is not None and existing.deleted_at is not None:
        return
    if existing and existing.entry_method != 'imported':
        return
    if existing:
        if existing.values == clean and existing.synthetic == synthetic:
            return
        SummaryRecord.objects.filter(
            pk=existing.pk, version=existing.version, deleted_at__isnull=True,
        ).update(
            values=clean, device=device, synthetic=synthetic, completeness='partial',
            version=existing.version + 1, updated_at=timezone.now(),
        )
        return
    SummaryRecord.objects.create(
        owner=owner, kind=kind, local_date=day, source_timezone='America/Chicago',
        source_system='oura', source_record_id=source_id[:120], entry_method='imported',
        device=device, completeness='partial', values=clean, synthetic=synthetic,
    )


def project_stored_devices(owner, today=None):
    """Log Oura days already stored: steps, calories burned, and sleep duration."""
    start, end = plan_window(today)
    activity = {}
    sleep_seconds = {}
    rows = OuraRecord.objects.select_related('connection').filter(
        connection__owner=owner, collection__in=('daily_activity', 'sleep'))
    for record in rows:
        payload = _row(record.raw_json)
        if payload is None:
            continue
        day = _day(payload.get('day'), start, end)
        if day is None:
            continue
        synthetic = record.connection.synthetic
        if record.collection == 'daily_activity':
            values = {
                'steps': _whole(payload.get('steps')),
                'active_calories': _whole(payload.get('active_calories')),
                'total_calories': _whole(payload.get('total_calories')),
            }
            if any(values.values()):
                activity[(day, synthetic)] = (record.source_record_id or record.identity_key, values)
        elif payload.get('total_sleep_duration') is not None and _whole(payload.get('total_sleep_duration')) is not None:
            sleep_seconds.setdefault((day, synthetic), [record.source_record_id or record.identity_key, 0])
            sleep_seconds[(day, synthetic)][1] += int(_whole(payload.get('total_sleep_duration')))
    for (day, synthetic), (source_id, values) in activity.items():
        _save(owner, 'activity', day, source_id or day.isoformat(), {
            'steps': values['steps'], 'workout_minutes': None,
            'active_calories': values['active_calories'], 'total_calories': values['total_calories'],
            'workout_summary': '',
        }, 'Oura', synthetic)
    for (day, synthetic), (source_id, seconds) in sleep_seconds.items():
        _save(owner, 'recovery', day, source_id or day.isoformat(), {
            'sleep_minutes': _minutes(seconds), 'hrv_ms': None, 'resting_hr_bpm': None,
            'readiness': None, 'hrv_method': '',
        }, 'Oura', synthetic)
