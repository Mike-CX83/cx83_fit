"""Disposable fixture server for one synthetic browser run.

The process binds nothing itself. The supervisor passes an already listening
socket. Dates, passwords, and the database exist only inside the run root.
"""
import os
import secrets
import socket
import sys
from pathlib import Path


LOOPBACK_NAMES = {'127.0.0.1', 'localhost', '::1'}


def _permitted(address, allowed):
    if not isinstance(address, tuple) or len(address) < 2:
        return False
    host, port = address[0], address[1]
    return (host, port) in allowed


def install_network_guard(allowed=(), originals=None):
    """Deny every outbound connection except an explicit owned endpoint.

    The returned snapshot is the real functions from before this call. Injected
    delegates are not that snapshot, so restore puts the real functions back.
    Denied calls do not reach the underlying connect. This is a language
    boundary in the fixture process, not an operating system sandbox.
    """
    snapshot = {
        'create_connection': socket.create_connection,
        'getaddrinfo': socket.getaddrinfo,
        'connect': socket.socket.connect,
        'connect_ex': socket.socket.connect_ex,
    }
    delegates = originals or snapshot
    allowed = set(allowed)

    def create_connection(address, *args, **kwargs):
        if not _permitted(address, allowed):
            raise OSError('synthetic browser app denied a network connection')
        return delegates['create_connection'](address, *args, **kwargs)

    def getaddrinfo(host, *args, **kwargs):
        if host not in LOOPBACK_NAMES:
            raise OSError('synthetic browser app denied external name resolution')
        return delegates['getaddrinfo'](host, *args, **kwargs)

    def connect(self, address):
        if not _permitted(address, allowed):
            raise OSError('synthetic browser app denied a network connection')
        return delegates['connect'](self, address)

    def connect_ex(self, address):
        if not _permitted(address, allowed):
            return 13
        return delegates['connect_ex'](self, address)

    socket.create_connection = create_connection
    socket.getaddrinfo = getaddrinfo
    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    return {'snapshot': snapshot, 'delegates': delegates}


def restore_network_guard(saved):
    source = saved['snapshot'] if isinstance(saved, dict) and 'snapshot' in saved else saved
    socket.create_connection = source['create_connection']
    socket.getaddrinfo = source['getaddrinfo']
    socket.socket.connect = source['connect']
    socket.socket.connect_ex = source['connect_ex']


CLOSED_VALUES = {
    'DASHBOARD_LOCAL_ONLY': '1',
    'SMS_ENABLED': '0',
    'SITE_EDITS_ENABLED': '0',
    'OURA_ENABLED': '0',
    'MCP_WRITES_ENABLED': '0',
    'MCP_AUTH_MODE': 'external',
}
CLOSED_ABSENT = (
    'OURA_CLIENT_ID', 'OURA_CLIENT_SECRET_FILE', 'OURA_TOKEN_KEY_FILE', 'OURA_REDIRECT_URI',
    'SMS_ACCOUNT_SID', 'SMS_FROM_NUMBER', 'SMS_AUTH_TOKEN_FILE',
    'MCP_PUBLIC_ORIGIN', 'MCP_ISSUER_URL', 'MCP_JWKS_URL', 'MCP_RESOURCE_URL', 'MCP_SUBJECT',
    'DASHBOARD_REPOSITORY_ROOT', 'DASHBOARD_TRUST_PROXY',
)


def assert_closed_environment(env, repo):
    """Reject provider, publish, and credential settings before Django imports."""
    for key, value in CLOSED_VALUES.items():
        if env.get(key) != value:
            raise SystemExit(f'fixture env {key} is not fail closed')
    for key in CLOSED_ABSENT:
        if env.get(key):
            raise SystemExit(f'fixture env {key} is present')
    if env.get('OWNER_USERNAME') != 'synthetic-browser-owner':
        raise SystemExit('fixture owner was not the synthetic owner')
    if not env.get('DJANGO_SECRET_KEY'):
        raise SystemExit('fixture secret is missing')
    private = Path(env['DASHBOARD_PRIVATE_ROOT'])
    static_root = Path(env['DASHBOARD_STATIC_ROOT'])
    if not _outside(private, repo) or not _outside(static_root, repo):
        raise SystemExit('fixture paths resolve inside the source checkout')


def _outside(path, repo):
    resolved = Path(path).resolve()
    return resolved != repo and repo not in resolved.parents


def main():
    if os.environ.get('BROWSER_INJECT_FAILURE') == 'startup':
        sys.stderr.write('browser fixture startup injection\n')
        raise SystemExit(3)
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)
    sys.path.insert(0, str(root))
    private = Path(os.environ['DASHBOARD_PRIVATE_ROOT'])
    static_root = Path(os.environ['DASHBOARD_STATIC_ROOT'])
    evidence = Path(os.environ['BROWSER_EVIDENCE'])
    if not _outside(private, root) or not _outside(static_root, root) or not _outside(evidence, root):
        raise SystemExit('fixture paths resolve inside the source checkout')
    assert_closed_environment(os.environ, root)
    install_network_guard()
    generation = os.environ.get('BROWSER_APP_GENERATION', '1')
    if generation == '1':
        _prepare(evidence)
    _serve(evidence, generation)


def _prepare(evidence):
    import django

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
    django.setup()
    from django.conf import settings
    from django.core.management import call_command

    if settings.SMS_ENABLED or settings.SITE_EDITS_ENABLED or settings.OURA_ENABLED or settings.HEALTH_OAUTH_WRITES:
        raise SystemExit('fixture provider flags are not fail closed')
    if settings.OWNER_USERNAME != 'synthetic-browser-owner':
        raise SystemExit('fixture owner was not the synthetic owner')
    if Path(settings.DATABASES['default']['NAME']).resolve() != (Path(os.environ['DASHBOARD_PRIVATE_ROOT']) / 'dashboard.sqlite3').resolve():
        raise SystemExit('fixture database is not the isolated database')
    if Path(settings.STATIC_ROOT).resolve() != Path(os.environ['DASHBOARD_STATIC_ROOT']).resolve():
        raise SystemExit('fixture static root is not isolated')
    call_command('migrate', interactive=False, verbosity=0)
    call_command('collectstatic', interactive=False, verbosity=0, clear=True)
    _seed(evidence)
    _mark_prior_css(Path(settings.STATIC_ROOT), evidence)


def _password():
    return 'Aa1!' + secrets.token_urlsafe(18)


def _write_secret(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(value, encoding='utf-8')
    os.chmod(path, 0o600)


def _manual(owner, kind, day, source, values, notes='', device='', synthetic=True):
    from uuid import uuid4
    from tracking.summaries import put_summary

    payload = {
        'kind': kind, 'local_date': day.isoformat(), 'source_timezone': 'America/Chicago',
        'source_system': source, 'device': device, 'completeness': 'partial',
        'values': values, 'notes': notes, 'synthetic': synthetic,
    }
    return put_summary(owner, payload, str(uuid4())), payload


def _rate(owner, day, metric, rating):
    from uuid import uuid4
    from tracking.journal import save_journal

    domain = {'energy': 19, 'mood': 13, 'focus': 14}[metric]
    save_journal(owner, f'Synthetic {metric} {rating}.', day.isoformat(), str(uuid4()), {
        'domain_id': domain, 'metric_key': metric, 'value_state': 'observed', 'rating': rating,
    }, synthetic=True)


def _legacy(owner, day):
    from tracking.models import SummaryRecord
    from tracking.summaries import validate_values

    values = validate_values('activity', {'steps': '50'})
    return SummaryRecord.objects.create(
        owner=owner, kind='activity', local_date=day, source_timezone='', source_system='oura',
        source_record_id='legacy-browser-activity', entry_method='imported', completeness='partial',
        values=values, synthetic=False, notes='LEGACY-ACTIVITY')


def _excluded(owner, day):
    """Valid stale and conflict rows, plus one malformed derived row that stays invalid.

    The malformed row is an identity negative. It is not an import or projection route.
    """
    from uuid import uuid4
    from tracking.models import OuraConnection, SummaryRecord
    from tracking.projection_identity import stable_source_id
    from tracking.summaries import validate_values

    created = []
    for status, steps, coherent in (
        ('stale', '77771', True), ('conflict', '77772', True), ('stale', '77773', False),
    ):
        connection = OuraConnection.objects.create(
            owner=owner, account_key=f'fabricated-{status}-{steps}', synthetic=True,
            state='disconnected', token_ciphertext='')
        raw_id = str(uuid4())
        derivation = {
            'schema_version': 2, 'recipe_version': 1, 'account_id': str(connection.id),
            'timezone_status': 'unknown', 'status': status, 'quality': status,
            'current_contributors': [],
            'contributor_identities_ever': [{
                'raw_id': raw_id, 'identity_key': 'a' * 64, 'collection': 'daily_activity',
                'source_record_id': 'historical-browser-activity',
            }],
            'conflict_reason': '',
        }
        source_id = stable_source_id(connection, 'activity', day) if coherent else f'browser-invalid-{steps}'
        created.append(SummaryRecord.objects.create(
            owner=owner, connection=connection, kind='activity', local_date=day,
            source_timezone='America/Chicago', source_system='oura', source_record_id=source_id,
            entry_method='derived', completeness='partial', synthetic=True, device='',
            values=validate_values('activity', {'steps': steps}), notes='', derivation=derivation))
    return created


def _excluded_low_step(owner, day):
    """One coherent stale derived row. Its low step count must not become the explanation."""
    from uuid import uuid4
    from tracking.models import OuraConnection, SummaryRecord
    from tracking.projection_identity import stable_source_id
    from tracking.summaries import validate_values

    connection = OuraConnection.objects.create(
        owner=owner, account_key='fabricated-stale-low-step', synthetic=True,
        state='disconnected', token_ciphertext='')
    raw_id = str(uuid4())
    return SummaryRecord.objects.create(
        owner=owner, connection=connection, kind='activity', local_date=day,
        source_timezone='America/Chicago', source_system='oura',
        source_record_id=stable_source_id(connection, 'activity', day),
        entry_method='derived', completeness='partial', synthetic=True, device='',
        values=validate_values('activity', {'steps': '100'}), notes='',
        derivation={
            'schema_version': 2, 'recipe_version': 1, 'account_id': str(connection.id),
            'timezone_status': 'unknown', 'status': 'stale', 'quality': 'stale',
            'current_contributors': [],
            'contributor_identities_ever': [{
                'raw_id': raw_id, 'identity_key': 'a' * 64, 'collection': 'daily_activity',
                'source_record_id': 'historical-browser-low-step',
            }],
            'conflict_reason': '',
        })


def _derived(owner, day):
    from uuid import uuid4
    from tracking.models import OuraConnection, SummaryRecord
    from tracking.projection_identity import stable_source_id
    from tracking.summaries import validate_values

    ring = OuraConnection.objects.create(
        owner=owner, account_key='fabricated-derived-account-key', synthetic=True,
        token_ciphertext='SENTINEL-DERIVED-TOKEN', state='disconnected')
    raw_id = str(uuid4())
    ever = [{'raw_id': raw_id, 'identity_key': 'ab' * 32, 'collection': 'daily_activity',
             'source_record_id': 'fabricated-provider'}]
    SummaryRecord.objects.create(
        owner=owner, kind='activity', local_date=day, source_timezone='America/Chicago',
        source_system='oura', source_record_id=stable_source_id(ring, 'activity', day),
        entry_method='derived', completeness='partial', synthetic=True, connection=ring,
        values=validate_values('activity', {'steps': '99999'}), notes='DERIVED-ACTIVITY',
        derivation={
            'schema_version': 2, 'recipe_version': 1, 'account_id': str(ring.id),
            'timezone_status': 'unknown', 'status': 'current', 'quality': 'current',
            'current_contributors': [{**ever[0], 'version': 1}],
            'contributor_identities_ever': ever, 'conflict_reason': '',
        })


def _seed(evidence):
    import json
    from datetime import timedelta
    from uuid import uuid4
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from django.utils.formats import date_format
    from tracking.headroom import headroom
    from tracking.holding import add_partner
    from tracking.meals import save_meal
    from tracking.models import NutritionTargets, OuraConnection
    from tracking.summaries import put_summary
    from tracking.today import day_metrics

    from datetime import date
    anchor = date.fromisoformat(os.environ['BROWSER_ANCHOR'])
    today = timezone.localdate()
    if anchor > today or today - anchor > timedelta(days=200):
        raise SystemExit('anchor date is outside the overview window')

    owner_password = _password()
    other_password = _password()
    secret_dir = evidence.parent / 'secrets'
    owner_file = secret_dir / 'owner-password'
    other_file = secret_dir / 'other-password'
    _write_secret(owner_file, owner_password)
    _write_secret(other_file, other_password)
    User = get_user_model()
    from django.conf import settings
    owner = User.objects.create_user(settings.OWNER_USERNAME, password=owner_password)
    other = User.objects.create_user('synthetic-browser-other', password=other_password)
    NutritionTargets.objects.create(owner=owner, values={
        'calories': '2000', 'protein': '200', 'fiber': '30', 'steps': '10000'})
    OuraConnection.objects.create(
        owner=owner, account_key='fabricated-browser-account-key', synthetic=False,
        token_ciphertext='SENTINEL-TOKEN-NOT-RENDERED', state='disconnected')

    positive = anchor
    unknown = anchor - timedelta(days=1)
    no_meal = anchor - timedelta(days=2)
    null_food = anchor - timedelta(days=3)
    meal_day = anchor - timedelta(days=4)
    zero = anchor - timedelta(days=5)
    null_steps = anchor - timedelta(days=6)
    ambiguous = anchor - timedelta(days=7)
    sleep_day = anchor - timedelta(days=8)
    personal_day = anchor - timedelta(days=20)
    correction_day = anchor - timedelta(days=10)

    _rate(owner, positive, 'mood', 7)
    _rate(owner, positive, 'energy', 7)
    save_meal(owner, positive, 'lunch', 'Synthetic bowl', calories='1500', synthetic=True)
    _manual(owner, 'nutrition', positive, 'manual', {
        'calories': None, 'protein': '100', 'total_carbohydrates': None, 'fat': None, 'fiber': '15'})
    _manual(owner, 'activity', positive, 'manual', {'steps': '8000'})

    _rate(owner, no_meal, 'mood', 1)
    _rate(owner, no_meal, 'energy', 1)
    _excluded_low_step(owner, no_meal)
    _rate(owner, null_food, 'mood', 1)
    _rate(owner, null_food, 'energy', 1)
    _manual(owner, 'nutrition', null_food, 'manual', {
        'calories': None, 'protein': '10', 'total_carbohydrates': None, 'fat': None, 'fiber': None})
    _rate(owner, meal_day, 'mood', 7)
    _rate(owner, meal_day, 'energy', 7)
    save_meal(owner, meal_day, 'dinner', 'Synthetic plate', calories='1800', synthetic=True)
    _manual(owner, 'nutrition', meal_day, 'manual', {
        'calories': '100', 'protein': None, 'total_carbohydrates': None, 'fat': None, 'fiber': None})

    _manual(owner, 'activity', zero, 'manual', {'steps': '0'})
    _manual(owner, 'nutrition', zero, 'manual', {
        'calories': '0', 'protein': None, 'total_carbohydrates': None, 'fat': None, 'fiber': None})
    _manual(owner, 'activity', null_steps, 'manual', {'steps': None, 'workout_minutes': '1'})
    sleep_personal, _payload = _manual(owner, 'recovery', sleep_day, 'desk', {'sleep_minutes': '300'}, synthetic=False)
    _manual(owner, 'recovery', sleep_day, 'watch', {'sleep_minutes': '480'})
    unique_sleep = anchor - timedelta(days=9)
    hrv_day = anchor - timedelta(days=11)
    controls = anchor - timedelta(days=12)
    unique_row, _payload = _manual(owner, 'recovery', unique_sleep, 'desk', {'sleep_minutes': '420'}, device='desk')
    _manual(owner, 'recovery', anchor - timedelta(days=13), 'desk', {'sleep_minutes': '300'}, device='H' * 80)
    hrv_row, _payload = _manual(owner, 'recovery', hrv_day, 'desk', {
        'sleep_minutes': None, 'hrv_ms': '45', 'resting_hr_bpm': None, 'readiness': None,
        'hrv_method': 'RMSSD',
    }, device='desk')
    hrv_alt, _payload = _manual(owner, 'recovery', hrv_day, 'band', {
        'sleep_minutes': None, 'hrv_ms': '30', 'resting_hr_bpm': None, 'readiness': None,
        'hrv_method': 'SDNN',
    }, device='band')
    mixed = anchor - timedelta(days=12)
    mixed_personal, _payload = _manual(owner, 'activity', mixed, 'manual', {'steps': '1000'}, synthetic=False)
    _manual(owner, 'activity', mixed, 'browser-test', {'steps': '2000'}, device='band')
    _excluded(owner, controls)

    long_source = 'b' + ('a' * 31)
    long_device = 'D&<>"\'' + ('x' * 114)
    long_row, _payload = _manual(
        owner, 'activity', ambiguous, long_source, {'steps': '1000'}, device=long_device, notes='LONG-DEVICE')
    step_ids = [long_row['id']]
    for index in range(2, 11):
        row, _payload = _manual(
            owner, 'activity', ambiguous, f'src{index:02d}', {'steps': '1000'},
            notes='OMITTED-ALT' if index == 10 else '')
        step_ids.append(row['id'])
    legacy = _legacy(owner, ambiguous)
    _derived(owner, ambiguous)

    created, payload = _manual(owner, 'activity', correction_day, 'manual', {'steps': '10'}, notes='correction-01')
    for version in range(1, 21):
        payload = {**payload, 'notes': f'correction-{version + 1:02d}'}
        created = put_summary(owner, payload, str(uuid4()), created['id'], version)
    oldest = anchor - timedelta(days=70)
    synthetic_hidden_id = None
    for offset in range(40, 71):
        day = anchor - timedelta(days=offset)
        note = 'PAGE2-NUTRITION' if day == oldest else ('SYNTHETIC-MARKER' if offset == 40 else '')
        row, _payload = _manual(owner, 'nutrition', day, 'browser-page', {
            'calories': '1', 'protein': None, 'total_carbohydrates': None, 'fat': None, 'fiber': None,
        }, notes=note)
        if offset == 40:
            synthetic_hidden_id = row['id']
    personal, _payload = _manual(owner, 'nutrition', personal_day, 'manual', {
        'calories': '1', 'protein': None, 'total_carbohydrates': None, 'fat': None, 'fiber': None,
    }, notes='PERSONAL-MARKER', synthetic=False)
    _manual(other, 'nutrition', personal_day, 'manual', {
        'calories': '1', 'protein': None, 'total_carbohydrates': None, 'fat': None, 'fiber': None,
    }, notes='OTHER-OWNER-MARKER', synthetic=False)
    add_partner(owner, 'Synthetic Partner', '5555550199')
    from uuid import uuid4
    from tracking.models import JournalScore, OuraPage, OuraRecord, OuraRevision, SobrietyDay
    from tracking.summary_imports import confirm_summaries
    csv_day = anchor - timedelta(days=15)
    confirmed = confirm_summaries(owner, 'browser-csv', [{
        'source_record_id': 'browsercsv1',
        'summary': {
            'kind': 'nutrition', 'local_date': csv_day.isoformat(), 'source_timezone': 'America/Chicago',
            'completeness': 'partial', 'synthetic': True,
            'values': {'calories': '1', 'protein': None, 'total_carbohydrates': None, 'fat': None, 'fiber': None},
            'device': '', 'notes': 'CSV-ELIGIBLE',
        },
    }], str(uuid4()))
    sentinel = anchor - timedelta(days=180)
    JournalScore.objects.create(
        owner=owner, kind='daily_state', local_date=sentinel, formula_version='journal-score-1',
        result=None, synthetic=True)
    SobrietyDay.objects.create(owner=owner, local_date=sentinel, potential='incomplete', synthetic=True)
    raw_page = OuraPage.objects.create(
        connection=OuraConnection.objects.get(owner=owner, account_key='fabricated-browser-account-key'),
        collection='sleep', sha256='b' * 64, raw_json='{"synthetic":true}')
    raw_record = OuraRecord.objects.create(
        connection=raw_page.connection, collection='sleep', identity_key='c' * 64,
        source_record_id='browser-raw', identity_kind='provider_id', raw_json='{"synthetic":true}', version=1)
    OuraRevision.objects.create(record=raw_record, version=1, raw_json='{"synthetic":true}', page=raw_page, page_index=0)

    positive_card = headroom(owner, positive, include_synthetic=True)
    no_meal_card = headroom(owner, no_meal, include_synthetic=True)
    null_card = headroom(owner, null_food, include_synthetic=True)
    meal_metrics = day_metrics(owner, meal_day, include_synthetic=True)
    zero_metrics = day_metrics(owner, zero, include_synthetic=True)
    null_steps_metrics = day_metrics(owner, null_steps, include_synthetic=True)
    ambiguous_metrics = day_metrics(owner, ambiguous, include_synthetic=True)
    sleep_card = headroom(owner, sleep_day, include_synthetic=True)
    if positive_card['score'] != '70.00' or positive_card['status_label'] != 'Steady':
        raise SystemExit('positive fixture did not keep the 70 steady score')
    if headroom(owner, unknown, include_synthetic=True)['score'] is not None:
        raise SystemExit('unknown fixture received a score')
    if not any('no meal is logged' in item.lower() for item in no_meal_card['factors']):
        raise SystemExit('missing meal was not stated')
    if 'Unresolved Oura history is not used. Missing or ambiguous evidence stays unknown.' not in no_meal_card['limitations']:
        raise SystemExit('excluded low step did not remain historical')
    if any('under half' in item.lower() or 'short sleep' in item.lower() for item in no_meal_card['factors']):
        raise SystemExit('excluded low step became an explanation')
    if 'food calories' not in null_card['missing'] or any('no meal is logged' in item.lower() for item in null_card['factors']):
        raise SystemExit('null calories became a missing meal')
    if meal_metrics['calories']['value'] != '1800':
        raise SystemExit('meal calories did not stay ahead of the summary')
    steps = next(item for item in zero_metrics['chips'] if item['key'] == 'steps')
    if steps['value'] != '0':
        raise SystemExit('known zero steps were not preserved')
    null_chip = next(item for item in null_steps_metrics['chips'] if item['key'] == 'steps')
    if null_chip['value'] == '0' or null_chip['logged']:
        raise SystemExit('null steps became zero')
    ambiguous_steps = next(item for item in ambiguous_metrics['chips'] if item['key'] == 'steps')
    if ambiguous_steps['alternative_shown'] != 8 or ambiguous_steps['alternative_total'] != 10:
        raise SystemExit('alternative disclosure was not 8 of 10')
    if '5 hours' in sleep_card['summary'].lower():
        raise SystemExit('competing sleep was reduced to one duration')
    cases = {
        'anchor': anchor.isoformat(),
        'timezone': 'America/Chicago',
        'origin': 'http://127.0.0.1:' + os.environ['APP_PORT'],
        'owner': settings.OWNER_USERNAME,
        'other_user': 'synthetic-browser-other',
        'owner_password_file': str(owner_file),
        'other_password_file': str(other_file),
        'dates': {
            'positive': positive.isoformat(), 'unknown': unknown.isoformat(),
            'no_meal': no_meal.isoformat(), 'null_food': null_food.isoformat(),
            'meal': meal_day.isoformat(), 'zero': zero.isoformat(),
            'null_steps': null_steps.isoformat(), 'ambiguous': ambiguous.isoformat(),
            'sleep': sleep_day.isoformat(), 'unique_sleep': unique_sleep.isoformat(),
            'hrv': hrv_day.isoformat(), 'controls': controls.isoformat(),
            'personal': personal_day.isoformat(), 'page2': oldest.isoformat(),
            'synthetic_hidden': (anchor - timedelta(days=40)).isoformat(),
            'csv': csv_day.isoformat(), 'short_sleep': (anchor - timedelta(days=13)).isoformat(),
            'mixed': mixed.isoformat(),
        },
        'journal_score_dates': [
            positive.isoformat(), unknown.isoformat(), no_meal.isoformat(), null_food.isoformat(),
            meal_day.isoformat(), zero.isoformat(), null_steps.isoformat(), ambiguous.isoformat(),
            sleep_day.isoformat(), controls.isoformat(), (anchor - timedelta(days=13)).isoformat(),
            csv_day.isoformat(), mixed.isoformat(),
        ],
        'sobriety_dates': [(anchor - timedelta(days=offset)).isoformat() for offset in range(13, -1, -1)],
        'cache_dates': [
            positive.isoformat(), unknown.isoformat(), no_meal.isoformat(), null_food.isoformat(),
            meal_day.isoformat(), zero.isoformat(), null_steps.isoformat(), ambiguous.isoformat(),
            sleep_day.isoformat(), controls.isoformat(), (anchor - timedelta(days=13)).isoformat(),
        ],
        'cache_sentinel': sentinel.isoformat(),
        'owner_id': owner.id,
        'step_ids': step_ids,
        'hrv_id': hrv_row['id'],
        'hrv_alt_id': hrv_alt['id'],
        'unique_sleep_id': unique_row['id'],
        'root_score_date': __import__('datetime').datetime.now(__import__('zoneinfo').ZoneInfo('America/Chicago')).date().isoformat(),
        'mixed_personal_id': mixed_personal['id'],
        'sleep_personal_id': sleep_personal['id'],
        'export_summary_ids': [sleep_personal['id'], mixed_personal['id'], str(legacy.id), personal['id']],
        'fixture_limits': {
            'source_alphabet': 'lowercase letters, digits, dots, underscores, hyphens',
            'escaped_maximum_label': 'device',
            'historical_negative_rows': 'stale, conflict, and invalid derived rows are ORM fixtures, not import or projection proof',
            'synthetic_form_field': 'the new journal form has no synthetic checkbox; the runner adds the supported synthetic=on field and discloses it',
        },
        'page2_label': date_format(oldest, 'M j, Y'),
        'correction_id': created['id'],
        'long_id': long_row['id'],
        'long_source': long_source,
        'long_device': long_device,
        'legacy_id': str(legacy.id),
        'personal_marker': 'PERSONAL-MARKER',
        'personal_id': personal['id'],
        'synthetic_hidden_id': synthetic_hidden_id,
        'csv_id': confirmed['record_ids'][0],
        'long_headroom': 'H' * 80,
        'synthetic_marker': 'SYNTHETIC-MARKER',
        'other_marker': 'OTHER-OWNER-MARKER',
        'token_sentinel': 'SENTINEL-TOKEN-NOT-RENDERED',
        'derived_token_sentinel': 'SENTINEL-DERIVED-TOKEN',
        'account_key_sentinel': 'fabricated-browser-account-key',
        'derived_account_key_sentinel': 'fabricated-derived-account-key',
        'css_discovery': 'link[rel=stylesheet][href*="app.css"]',
        'expected_style': 'rgb(255, 255, 255)',
        'prior_style': 'rgb(1, 2, 3)',
        'write_adds': {
            'tracking_journalentry': 4,
            'tracking_journalobservation': 4,
            'tracking_journalcorrection': 8,
            'tracking_holdingmessage': 2,
            'tracking_writerequest': 10,
        },
    }
    (evidence / 'fixture-cases.json').write_text(json.dumps(cases, indent=2), encoding='utf-8')


def _mark_prior_css(static_root, evidence):
    css = static_root / 'tracking' / 'app.css'
    current = css.read_bytes()
    (evidence / 'css-current.bin').write_bytes(current)
    prior = current + b'\n.headroom-status{color:rgb(1, 2, 3)!important}\n'
    css.write_bytes(prior)
    os.utime(css, (1600000000, 1600000000))
    for extra in (css.with_suffix('.css.gz'), Path(str(css) + '.gz')):
        if extra.exists():
            extra.unlink()


def _serve(evidence, generation):
    import asyncio
    import json
    import django
    import uvicorn

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
    django.setup()
    config = uvicorn.Config(
        'dashboard.asgi:application', fd=int(os.environ['APP_LISTEN_FD']),
        log_level='warning', access_log=False, proxy_headers=False,
        forwarded_allow_ips='', server_header=False, lifespan='off')
    server = uvicorn.Server(config)

    async def run():
        task = asyncio.create_task(server.serve())
        for _ in range(400):
            if server.started:
                break
            await asyncio.sleep(0.05)
        else:
            raise RuntimeError('fixture server did not start')
        (evidence / 'ready.json').write_text(json.dumps({
            'pid': os.getpid(), 'generation': generation,
        }), encoding='utf-8')
        while not server.should_exit:
            await asyncio.sleep(0.2)
        await task

    asyncio.run(run())


if __name__ == '__main__':
    main()
