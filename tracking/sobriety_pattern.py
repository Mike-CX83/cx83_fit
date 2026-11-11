"""Multi-day sobriety pattern from records the dashboard already holds.

A blank day is unknown, not sober. A recorded use is a fact only when the owner
marked Used. Off-wrist is a connected ring or a previously logging watch that
was not worn. A sync that never arrived is source_stale, not off-wrist.
Nothing here diagnoses ADHD or quotes a published relapse probability.
"""
import json
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction

from .domain import InvalidMeasurement, parse_day
from .models import (JournalObservation, JournalScore, Measurement, OuraConnection, OuraRecord,
                     SobrietyDay, SummaryRecord)
from .summaries import SCHEMAS
from .summary_evidence import evidence_envelope, resolve_metric


FORMULA = SobrietyDay.FORMULA
EVIDENCE_GATE = 'h0-b2'
OFF_WRIST_SECONDS = 8 * 60 * 60
CRAVING_HIGH = 6
CONFIDENCE_LOW = 4
SLEEP_SHORT_MINUTES = Decimal('360')
RATING_DROP = 2
STRONG = frozenset({'off_wrist', 'craving', 'access', 'confidence', 'mood', 'sleep', 'routine'})
MEANING = {
    'off_wrist': 'A connected ring or previously logging watch was off. For this owner that marks being off schedule, running, or regulation slipping. It is not an ADHD diagnosis.',
    'source_stale': 'The device stopped sending days. That is a missed sync, not proof the device was off.',
    'not_connected': 'That device has no connection here.',
    'use_recorded': 'Used is true only when the owner recorded it. Silence is not abstinence.',
    'potential': 'lower, rising, high, or incomplete. This is a pattern read, not a percent and not a diagnosis.',
}


def read_pattern(owner, end, days=14, include_synthetic=False):
    """Recompute and store the pattern ending on this local date."""
    if type(days) is not int or isinstance(days, bool) or not 1 <= days <= 366:
        raise InvalidMeasurement('Use a pattern window of 1 to 366 days.')
    if type(include_synthetic) is not bool:
        raise InvalidMeasurement('synthetic must be true or false.')
    last = parse_day(end)
    first = last - timedelta(days=days - 1)
    loaded_start = first - timedelta(days=7)
    days_in_load = [loaded_start + timedelta(days=offset) for offset in range((last - loaded_start).days + 1)]
    built = _build(owner, days_in_load, include_synthetic)
    visible = [row for row in built if first <= row['local_date'] <= last]
    _runs(visible)
    stops = _stops(built, first, last)
    episodes = _episodes(visible, stops)
    stored = _store(owner, visible, include_synthetic)
    slices = {}
    for size in (3, 7, 14):
        if len(visible) >= size or size == days:
            chunk = visible[-size:]
            slices[str(size if len(visible) >= size else len(visible))] = _slice(chunk)
    return {
        'formula_version': FORMULA,
        'start': first.isoformat(),
        'end': last.isoformat(),
        'days': days,
        'meaning': MEANING,
        'slices': slices,
        'stops': stops,
        'episodes': episodes,
        'days_detail': [_public_day(row) for row in stored],
    }


def _synthetic_filter(query, include_synthetic, field='synthetic'):
    if include_synthetic:
        return query
    return query.filter(**{field: False})


def _build(owner, dates, include_synthetic):
    observations = list(_synthetic_filter(
        JournalObservation.objects.select_related('entry').filter(
            owner=owner, deleted_at__isnull=True, local_date__gte=dates[0], local_date__lte=dates[-1]),
        include_synthetic))
    summaries = list(_synthetic_filter(
        SummaryRecord.objects.select_related('connection').filter(
            owner=owner, deleted_at__isnull=True, local_date__gte=dates[0], local_date__lte=dates[-1]),
        include_synthetic))
    measurements = list(_synthetic_filter(
        Measurement.objects.filter(owner=owner, deleted_at__isnull=True, local_date__gte=dates[0], local_date__lte=dates[-1]),
        include_synthetic))
    scores = list(_synthetic_filter(
        JournalScore.objects.filter(owner=owner, local_date__gte=dates[0], local_date__lte=dates[-1]),
        include_synthetic))
    oura = _oura_days(owner, include_synthetic)
    by_date = {day: [] for day in dates}
    for observation in observations:
        by_date.setdefault(observation.local_date, []).append(observation)
    summary_by_date = {day: [] for day in dates}
    excluded_by_date = {day: [] for day in dates}
    for record in summaries:
        envelope = evidence_envelope(record)
        if envelope['eligibility_status'] == 'eligible':
            summary_by_date.setdefault(record.local_date, []).append(record)
        else:
            excluded_by_date.setdefault(record.local_date, []).append(envelope)
    watches = _watch_days([record for rows in summary_by_date.values() for record in rows])
    measure_by_date = {day: [] for day in dates}
    for record in measurements:
        measure_by_date.setdefault(record.local_date, []).append(record)
    score_by_date = {day: [] for day in dates}
    for score in scores:
        score_by_date.setdefault(score.local_date, []).append(score)
    rating_history = {key: [] for key in ('mood', 'energy', 'focus')}
    rows = []
    for day in dates:
        day_observations = by_date.get(day, [])
        ratings = {}
        earlier_ratings = {}
        for key in rating_history:
            latest, earlier = _rating(day_observations, key)
            ratings[key] = latest
            if earlier:
                earlier_ratings[key] = earlier
        flags = []
        for key, today in ratings.items():
            if today is None:
                continue
            prior = [value for value, seen in rating_history[key] if seen < day]
            if len(prior) >= 2 and today <= _median(prior) - RATING_DROP:
                flags.append(key)
            rating_history[key].append((today, day))
        devices, device_limits = _devices_for_day(day, oura, watches)
        if any(item['status'] == 'off_wrist' for item in devices):
            flags.append('off_wrist')
        day_rows = summary_by_date.get(day, [])
        recovery, recovery_alternatives = _qualified(day_rows, 'recovery')
        activity, activity_alternatives = _qualified(day_rows, 'activity')
        nutrition, nutrition_alternatives = _qualified(day_rows, 'nutrition')
        limits = list(device_limits)
        if excluded_by_date.get(day):
            limits.append('excluded_summary_not_used')
        if recovery_alternatives.get('sleep_minutes'):
            limits.append('sleep_selection_required')
        if activity_alternatives.get('steps'):
            limits.append('steps_selection_required')
        alternatives = {'sleep_minutes': [], 'steps': []}
        alternatives.update(recovery_alternatives)
        alternatives.update(activity_alternatives)
        alternatives.update(nutrition_alternatives)
        coverage = {
            'evidence_gate_version': EVIDENCE_GATE,
            'ratings': {key: value for key, value in ratings.items()},
            'earlier_ratings': earlier_ratings,
            'sobriety': _sobriety(day_observations),
            'devices': devices,
            'recovery': recovery,
            'activity': activity,
            'nutrition': nutrition,
            'measurements': [_measurement(record) for record in measure_by_date.get(day, [])],
            'scores': [_score(score) for score in score_by_date.get(day, [])],
            'limits': limits,
            'alternatives': alternatives,
        }
        sobriety = coverage['sobriety']
        if sobriety['craving'] is not None and sobriety['craving'] >= CRAVING_HIGH:
            flags.append('craving')
        if sobriety['access'] is True:
            flags.append('access')
        if sobriety['confidence'] is not None and sobriety['confidence'] <= CONFIDENCE_LOW:
            flags.append('confidence')
        if _sleep_short(coverage['recovery']):
            flags.append('sleep')
        if _series_gap(day, dates, summary_by_date, excluded_by_date, 'recovery', 'sleep_minutes', devices):
            flags.append('sleep')
        if _series_gap(day, dates, summary_by_date, excluded_by_date, 'activity', 'steps', devices):
            flags.append('activity')
        if _nutrition_gap(day, dates, summary_by_date, excluded_by_date):
            flags.append('nutrition')
        if _routine_missed(day_observations, coverage['scores']):
            flags.append('routine')
        if sobriety['craving'] is None:
            coverage['limits'].append('craving_not_recorded')
        if not sobriety['domain_present']:
            coverage['limits'].append('sobriety_domain_not_recorded')
        coverage['limits'] = list(dict.fromkeys(coverage['limits']))
        flags = list(dict.fromkeys(flags))
        rows.append({
            'local_date': day,
            'potential': _potential(flags, coverage),
            'use_recorded': sobriety['use'] is True,
            'wear': {'devices': devices},
            'drivers': flags,
            'coverage': coverage,
            'run_started': None,
            'days_in_run': None,
        })
    return rows


def _oura_days(owner, include_synthetic):
    connections = list(_synthetic_filter(OuraConnection.objects.filter(owner=owner), include_synthetic))
    if not connections:
        return {'connected': False, 'accounts': {}}
    records = OuraRecord.objects.filter(connection__in=connections, collection='daily_activity')
    accounts = {connection.id: {
        'connection_id': str(connection.id), 'synthetic': connection.synthetic is True, 'by_day': {},
    } for connection in connections}
    for record in records:
        payload = _json(record.raw_json)
        if payload is None:
            continue
        try:
            day = parse_day(payload.get('day'))
        except InvalidMeasurement:
            continue
        account = accounts[record.connection_id]
        account['by_day'].setdefault(day, []).append(_seconds(payload.get('non_wear_time')))
    for account in accounts.values():
        account['days'] = {day for day, rows in account['by_day'].items() if len(rows) == 1}
    return {'connected': True, 'accounts': accounts}


def _watch_days(summaries):
    grouped = {}
    contested = _contested_fields(summaries)
    for record in summaries:
        if record.source_system == 'oura' or record.kind not in ('activity', 'recovery'):
            continue
        numbers = _schema_numbers(record)
        if not numbers:
            continue
        key = _record_key(record)
        item = grouped.setdefault(key, {
            'name': record.device or record.source_system, 'known_days': set(),
            'unavailable_days': set(), 'identity': key,
        })
        blocked = contested.get((record.local_date, record.kind), set())
        if any(field not in blocked for field in numbers):
            item['known_days'].add(record.local_date)
            item['unavailable_days'].discard(record.local_date)
        elif record.local_date not in item['known_days']:
            item['unavailable_days'].add(record.local_date)
    by_name = {}
    for item in grouped.values():
        by_name.setdefault(item['name'], []).append(item)
    for items in by_name.values():
        if len(items) > 1:
            for item in items:
                item['name'] = f"{item['name']} · {'test' if item['identity'][3] else 'personal'}"
    return grouped


def _devices_for_day(day, oura, watches):
    devices = []
    limits = []
    if not oura['connected']:
        devices.append({'name': 'Oura', 'status': 'not_connected', 'non_wear_seconds': None})
    else:
        several = len(oura['accounts']) > 1
        for account in oura['accounts'].values():
            name = f"Oura {account['connection_id']}" if several else 'Oura'
            rows = account['by_day'].get(day)
            if not rows:
                devices.append({'name': name, 'status': _gap_status(day, account['days']), 'non_wear_seconds': None,
                                'connection_id': account['connection_id'], 'synthetic': account['synthetic']})
            elif len(rows) != 1:
                devices.append({'name': name, 'status': 'wear_unknown', 'non_wear_seconds': None,
                                'connection_id': account['connection_id'], 'synthetic': account['synthetic']})
                limits.append('raw_oura_day_unresolved')
            else:
                seconds = rows[0]
                if seconds is None:
                    status = 'wear_unknown'
                elif seconds >= OFF_WRIST_SECONDS:
                    status = 'off_wrist'
                else:
                    status = 'worn'
                devices.append({'name': name, 'status': status, 'non_wear_seconds': seconds,
                                'connection_id': account['connection_id'], 'synthetic': account['synthetic']})
    for item in watches.values():
        if day in item['known_days']:
            status = 'worn'
        elif day in item['unavailable_days']:
            status = 'wear_unknown'
            limits.append('wear_unavailable')
        else:
            status = _gap_status(day, item['known_days'])
        devices.append({'name': item['name'], 'status': status, 'non_wear_seconds': None, 'identity': list(item['identity'])})
    return devices, limits


def _gap_status(day, present):
    if not present:
        return 'source_stale'
    earliest, latest = min(present), max(present)
    if earliest < day < latest:
        return 'off_wrist'
    if day < earliest:
        return 'not_connected'
    return 'source_stale'


def _ordered(observations, key, domain=None):
    matched = []
    for observation in observations:
        if observation.metric_key != key or observation.value_state != 'observed':
            continue
        if domain is not None and observation.domain_id != domain:
            continue
        matched.append(observation)
    matched.sort(key=lambda item: (item.entry.captured_at, str(item.id)))
    return matched


def _rating(observations, key):
    found = []
    for observation in _ordered(observations, key):
        rating = (observation.value_json or {}).get('rating')
        if type(rating) is int and not isinstance(rating, bool) and 0 <= rating <= 10:
            found.append(rating)
    if not found:
        return None, []
    return found[-1], found[:-1]


def _boolean(observations, key):
    found = []
    for observation in _ordered(observations, key, 12):
        value = (observation.value_json or {}).get('boolean')
        if type(value) is bool:
            found.append(value)
    if not found:
        return None
    return found[-1]


def _sobriety(observations):
    domain = [item for item in observations if item.domain_id == 12]
    craving, _earlier_craving = _rating(domain, 'craving')
    confidence, _earlier_confidence = _rating(domain, 'confidence')
    return {
        'domain_present': bool(domain),
        'craving': craving,
        'confidence': confidence,
        'access': _boolean(domain, 'access'),
        'use': _boolean(domain, 'use'),
        'substance_keys': sorted({
            (item.value_json or {}).get('practice_key')
            for item in domain
            if item.metric_key == 'use' and item.value_state == 'observed' and (item.value_json or {}).get('practice_key')
        }),
    }


def _summaries(records, kind):
    rows = []
    for record in records:
        if record.kind != kind:
            continue
        rows.append({
            'source_system': record.source_system,
            'device': record.device,
            'completeness': record.completeness,
            'values': record.values,
        })
    return rows


def _measurement(record):
    return {
        'metric': record.metric, 'value': format(record.value, 'f'), 'unit': record.unit,
        'side': record.side, 'source_system': record.source_system,
    }


def _score(score):
    return {
        'kind': score.kind,
        'result': None if score.result is None else format(score.result, 'f'),
        'formula_version': score.formula_version,
    }


def _sleep_short(recovery_rows):
    for row in recovery_rows:
        minutes = _decimal((row['values'] or {}).get('sleep_minutes'))
        if minutes is not None and minutes < SLEEP_SHORT_MINUTES:
            return True
    return False


def _record_key(record):
    return (record.source_system, record.device or '', record.entry_method, record.synthetic is True)


def _number_known(value):
    if value is None or isinstance(value, bool) or value == '':
        return False
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return False
    return number.is_finite()


def _schema_numbers(record):
    values = record.values if isinstance(record.values, dict) else {}
    return [field for field, _, _ in SCHEMAS.get(record.kind, ()) if _number_known(values.get(field))]


def _schema_unit(kind, field):
    for name, _, unit in SCHEMAS.get(kind, ()):
        if name == field:
            return unit
    return None


def _contested_fields(summaries):
    grouped = {}
    for record in summaries:
        if record.kind in ('activity', 'recovery'):
            grouped.setdefault((record.local_date, record.kind), []).append(record)
    contested = {}
    for key, rows in grouped.items():
        blocked = set()
        for field, _, _ in SCHEMAS[key[1]]:
            if resolve_metric(rows, field)['status'] == 'selection_required':
                blocked.add(field)
        contested[key] = blocked
    return contested


def _alternative_view(record, field):
    method = (record.values or {}).get('hrv_method') if field == 'hrv_ms' else None
    if method == '':
        method = None
    return {
        'summary_id': str(record.id),
        'value': (record.values or {}).get(field),
        'source_system': record.source_system,
        'device': record.device,
        'stored_synthetic': record.synthetic is True,
        'stored_class': 'test' if record.synthetic else 'personal',
        'entry_method': record.entry_method,
        'kind': record.kind,
        'metric': field,
        'unit': _schema_unit(record.kind, field),
        'hrv_method': method,
    }


def _coverage_row(record, values, metrics):
    method = (record.values or {}).get('hrv_method') if isinstance(record.values, dict) else None
    if method == '':
        method = None
    return {
        'source_system': record.source_system,
        'device': record.device,
        'completeness': record.completeness,
        'values': values,
        'summary_id': str(record.id),
        'entry_method': record.entry_method,
        'synthetic': record.synthetic is True,
        'identity': {
            'summary_id': str(record.id),
            'entry_method': record.entry_method,
            'stored_class': 'test' if record.synthetic else 'personal',
            'metrics': [{'name': name, 'unit': _schema_unit(record.kind, name)} for name in metrics],
            'hrv_method': method if method and 'hrv_ms' in metrics else None,
        },
    }


def _qualified(records, kind):
    rows = [record for record in records if record.kind == kind]
    fields = [field for field, _, _ in SCHEMAS.get(kind, ())]
    contested = {}
    for field in fields:
        if any(_number_known((record.values or {}).get(field)) for record in rows):
            if resolve_metric(rows, field)['status'] == 'selection_required':
                contested[field] = [_alternative_view(record, field) for record in rows
                                    if _number_known((record.values or {}).get(field))]
    qualified = []
    for record in rows:
        values = dict(record.values or {})
        for field in contested:
            values.pop(field, None)
        if 'hrv_ms' in contested:
            values.pop('hrv_method', None)
        if not any(_number_known(values.get(field)) for field in fields):
            continue
        metrics = [field for field in fields if _number_known(values.get(field))]
        qualified.append(_coverage_row(record, values, metrics))
    return qualified, contested


def _kind_rows(summary_by_date, day, kind):
    return [record for record in summary_by_date.get(day, []) if record.kind == kind]


def _excluded_kind(excluded_by_date, day, kind):
    return any(item.get('kind') == kind for item in excluded_by_date.get(day, []))


def _source_silenced(devices, key):
    return any(item.get('identity') == list(key) and item['status'] in ('off_wrist', 'source_stale', 'not_connected') for item in devices)


def _series_gap(day, dates, summary_by_date, excluded_by_date, kind, field, devices):
    today_rows = _kind_rows(summary_by_date, day, kind)
    if not today_rows and _excluded_kind(excluded_by_date, day, kind):
        return False
    if today_rows and resolve_metric(today_rows, field)['status'] != 'value':
        return False
    anchors = {}
    for seen in dates:
        if seen >= day:
            break
        rows = _kind_rows(summary_by_date, seen, kind)
        decision = resolve_metric(rows, field) if rows else None
        if decision is None or decision['status'] != 'value':
            continue
        alternative = decision['alternatives'][0]
        key = (alternative['source_system'], alternative['device'] or '', alternative['entry_method'], alternative['stored_synthetic'])
        anchors[key] = True
    today = {_record_key(record) for record in today_rows}
    for key in anchors:
        if key in today or _source_silenced(devices, key):
            continue
        return True
    return False


def _nutrition_gap(day, dates, summary_by_date, excluded_by_date):
    def usable(seen):
        return [record for record in _kind_rows(summary_by_date, seen, 'nutrition') if record.source_system != 'oura']

    today_rows = usable(day)
    if not today_rows and _excluded_kind(excluded_by_date, day, 'nutrition'):
        return False
    if today_rows and resolve_metric(today_rows, 'calories')['status'] == 'selection_required':
        return False
    earlier = {}
    for seen in dates:
        if seen >= day:
            break
        rows = usable(seen)
        if rows and resolve_metric(rows, 'calories')['status'] == 'selection_required':
            continue
        for record in rows:
            earlier[_record_key(record)] = record.completeness
    if not earlier:
        return False
    today = {_record_key(record): record.completeness for record in today_rows}
    for key, completeness in earlier.items():
        current = today.get(key)
        if current is None or (completeness == 'complete' and current != 'complete'):
            return True
    return False


def _routine_missed(observations, scores):
    for score in scores:
        result = _decimal(score['result']) if score['kind'] == 'routine_alignment' else None
        if result is not None and result < Decimal('100'):
            return True
    for observation in observations:
        value = observation.value_json or {}
        if observation.value_state == 'observed' and value.get('practice_key') and value.get('boolean') is False:
            return True
    return False


def _potential(flags, coverage):
    names = set(flags)
    known = bool(coverage['ratings']['mood'] is not None or coverage['recovery'] or coverage['sobriety']['domain_present']
                 or any(item['status'] == 'worn' for item in coverage['devices']))
    if 'craving' in names and names & {'access', 'off_wrist', 'mood'}:
        return 'high'
    if len(names) >= 4:
        return 'high'
    if len(names) >= 2 or names & STRONG:
        return 'rising'
    if names or known:
        return 'lower'
    return 'incomplete'


def _runs(rows):
    started = None
    length = 0
    for row in rows:
        if row['potential'] in ('rising', 'high'):
            if started is None:
                started = row['local_date']
                length = 1
            else:
                length += 1
            row['run_started'] = started
            row['days_in_run'] = length
        else:
            started = None
            length = 0


def _stops(rows, first, last):
    stops = []
    previous = None
    for row in rows:
        current = {item['name']: item['status'] for item in row['wear']['devices']}
        if previous is not None:
            for name, status in current.items():
                before = previous['statuses'].get(name)
                if status in ('off_wrist', 'source_stale') and before not in (status, None) and before in ('worn', 'wear_unknown'):
                    if first <= row['local_date'] <= last:
                        stops.append({'signal': name, 'kind': status, 'started': row['local_date'].isoformat(),
                                      'days_until_use': None, 'days_until_high': None})
            for driver in row['drivers']:
                if driver in ('off_wrist',) or driver in previous['drivers']:
                    continue
                if first <= row['local_date'] <= last and driver not in previous['drivers']:
                    stops.append({'signal': driver, 'kind': 'started', 'started': row['local_date'].isoformat(),
                                  'days_until_use': None, 'days_until_high': None})
        previous = {'statuses': current, 'drivers': set(row['drivers'])}
    indexed = {row['local_date'].isoformat(): row for row in rows}
    ordered = [row['local_date'] for row in rows]
    for stop in stops:
        started = parse_day(stop['started'])
        for day in ordered:
            if day < started:
                continue
            item = indexed[day.isoformat()]
            if stop['days_until_use'] is None and item['use_recorded']:
                stop['days_until_use'] = (day - started).days
            if stop['days_until_high'] is None and item['potential'] == 'high':
                stop['days_until_high'] = (day - started).days
    return stops


def _episodes(rows, stops):
    uses = [row for row in rows if row['use_recorded']]
    episodes = []
    for row in uses:
        intact = [item for item in rows if item['local_date'] < row['local_date'] and item['potential'] == 'lower'
                  and not any(device['status'] == 'off_wrist' for device in item['wear']['devices'])]
        last_intact = None if not intact else intact[-1]['local_date']
        related = []
        for stop in stops:
            started = parse_day(stop['started'])
            if started <= row['local_date'] and (last_intact is None or started > last_intact):
                related.append(stop)
        episodes.append({
            'use_date': row['local_date'].isoformat(),
            'last_intact': None if last_intact is None else last_intact.isoformat(),
            'days_from_intact_to_use': None if last_intact is None else (row['local_date'] - last_intact).days,
            'stops': related,
        })
    if rows and rows[-1]['potential'] in ('rising', 'high'):
        episodes.append({
            'open_run_started': None if rows[-1]['run_started'] is None else rows[-1]['run_started'].isoformat(),
            'days_in_run': rows[-1]['days_in_run'],
            'potential': rows[-1]['potential'],
            'use_recorded': rows[-1]['use_recorded'],
        })
    return episodes


def _slice(rows):
    return {
        'start': rows[0]['local_date'].isoformat(),
        'end': rows[-1]['local_date'].isoformat(),
        'potential_by_date': {row['local_date'].isoformat(): row['potential'] for row in rows},
        'use_dates': [row['local_date'].isoformat() for row in rows if row['use_recorded']],
        'off_wrist_dates': [row['local_date'].isoformat() for row in rows
                            if any(device['status'] == 'off_wrist' for device in row['wear']['devices'])],
        'drivers_by_date': {row['local_date'].isoformat(): row['drivers'] for row in rows},
    }


def _store(owner, rows, include_synthetic):
    if not rows:
        return []
    with transaction.atomic():
        SobrietyDay.objects.filter(
            owner=owner, formula_version=FORMULA, synthetic=include_synthetic,
            local_date__gte=rows[0]['local_date'], local_date__lte=rows[-1]['local_date']).delete()
        created = [SobrietyDay.objects.create(
            owner=owner, local_date=row['local_date'], formula_version=FORMULA, synthetic=include_synthetic,
            potential=row['potential'], use_recorded=row['use_recorded'], wear=row['wear'], drivers=row['drivers'],
            coverage=row['coverage'], run_started=row['run_started'], days_in_run=row['days_in_run']) for row in rows]
    return created


def _public_day(row):
    return {
        'local_date': row.local_date.isoformat(),
        'potential': row.potential,
        'use_recorded': row.use_recorded,
        'wear': row.wear,
        'drivers': row.drivers,
        'coverage': row.coverage,
        'run_started': None if row.run_started is None else row.run_started.isoformat(),
        'days_in_run': row.days_in_run,
        'limits': row.coverage.get('limits', []),
    }


def _json(raw):
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _seconds(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if number < 0 or number != number.to_integral_value():
        return None
    return int(number)


def _decimal(value):
    if value is None or value == '':
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not number.is_finite():
        return None
    return number


def _median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2
