"""B2 Headroom and sobriety input gates. Fabricated rows only."""
import json
from datetime import date, timedelta
from uuid import uuid4

from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from tracking.headroom import _food, headroom
from tracking.journal import save_journal
from tracking.models import DietEntry, NutritionTargets, OuraConnection, OuraRecord, SobrietyDay, SummaryRecord
from tracking.projection_identity import stable_source_id
from tracking.sobriety_pattern import FORMULA, read_pattern
from tracking.summaries import validate_values
from tracking.summary_evidence import CALCULATION_NOTICE, HISTORY_HREF


class HeadroomInputTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(settings.OWNER_USERNAME)
        self.other = get_user_model().objects.create_user('synthetic-b2-other')
        self.day = date(2026, 11, 5)
        self.client.force_login(self.owner)
        NutritionTargets.objects.create(owner=self.owner, values={'calories': '2000', 'steps': '10000'})

    def rate(self, metric, rating):
        domain = {'energy': 19, 'mood': 13, 'focus': 14}[metric]
        save_journal(self.owner, f'Synthetic {metric}.', self.day.isoformat(), str(uuid4()), {
            'domain_id': domain, 'metric_key': metric, 'value_state': 'observed', 'rating': rating,
        }, synthetic=True)

    def row(self, kind, source, values, **changes):
        fields = {
            'owner': self.owner, 'kind': kind, 'local_date': self.day, 'source_timezone': 'America/Chicago',
            'source_system': source, 'source_record_id': uuid4().hex, 'entry_method': 'manually_reported',
            'completeness': 'partial', 'values': values, 'synthetic': True,
        }
        fields.update(changes)
        return SummaryRecord.objects.create(**fields)

    def derived(self, status, steps):
        ring = OuraConnection.objects.create(
            owner=self.owner, account_key=f'fabricated-{uuid4().hex[:12]}',
            source_account_id='secret-external-id', synthetic=True,
            token_ciphertext='secret-token-value', state='disconnected')
        raw_id = str(uuid4())
        ever = [{'raw_id': raw_id, 'identity_key': 'ab' * 32, 'collection': 'daily_activity',
                 'source_record_id': 'fabricated-provider'}]
        current = [] if status != 'current' else [{**ever[0], 'version': 1}]
        stored = 'current' if status == 'invalid' else status
        return self.row('activity', 'oura', {'steps': steps}, entry_method='derived', synthetic=True,
                        source_record_id=stable_source_id(ring, 'activity', self.day), connection=ring,
                        derivation={
                            'schema_version': [] if status == 'invalid' else 2, 'recipe_version': 1,
                            'account_id': str(ring.id), 'timezone_status': 'unknown', 'status': stored,
                            'quality': stored, 'current_contributors': current, 'contributor_identities_ever': ever,
                            'conflict_reason': '',
                        })

    def test_one_known_value_keeps_the_existing_formula(self):
        self.rate('mood', 8)
        self.rate('energy', 8)
        self.row('activity', 'manual', {'steps': '0'})
        self.row('recovery', 'manual', {'sleep_minutes': '300'})
        card = headroom(self.owner, self.day, include_synthetic=True)
        self.assertEqual(card['score'], '80.00')
        self.assertEqual(card['formula'], 'daily-state-1')
        self.assertIn('steps from manual are under half the goal', [item.lower() for item in card['factors']])
        self.assertIn('short sleep from manual is 5 hours', card['summary'].lower())

    def test_equal_records_and_excluded_history_are_not_selected(self):
        self.rate('mood', 8)
        self.rate('energy', 8)
        self.row('activity', 'manual', {'steps': '1000'})
        self.row('activity', 'csv:oura', {'steps': '1000'})
        self.row('activity', 'oura', {'steps': '50'}, entry_method='imported', synthetic=False)
        self.row('recovery', 'oura', {'sleep_minutes': '10'}, entry_method='imported', synthetic=True)
        for status in ('current', 'stale', 'conflict', 'invalid'):
            self.derived(status, '50')
        self.row('activity', 'manual', {'steps': '9000'}, owner=self.other)
        before = list(SummaryRecord.objects.order_by('id').values_list('id', 'values', 'version', 'deleted_at'))
        card = headroom(self.owner, self.day, include_synthetic=True)
        self.assertEqual(card['score'], '80.00')
        self.assertNotIn('steps', card['missing'])
        self.assertFalse(any('steps' in item.lower() for item in card['factors']))
        shown = ' '.join(card['limitations'])
        self.assertIn('More than one record. This number stays unknown.', shown)
        self.assertIn(CALCULATION_NOTICE, shown)
        self.assertEqual(card['history_href'], HISTORY_HREF)
        self.assertNotIn('secret-external-id', json.dumps(card))
        self.assertNotIn('secret-token-value', json.dumps(card))
        self.assertEqual(before, list(SummaryRecord.objects.order_by('id').values_list('id', 'values', 'version', 'deleted_at')))
        page = self.client.get(f'/?day={self.day.isoformat()}&synthetic=1')
        self.assertContains(page, 'More than one record. This number stays unknown.')
        self.assertContains(page, 'Unresolved history')
        self.assertContains(page, HISTORY_HREF)

    def test_null_is_unknown_and_a_test_class_cannot_cancel_a_personal_value(self):
        self.row('activity', 'csv:oura', {'steps': None})
        card = headroom(self.owner, self.day, include_synthetic=True)
        self.assertIn('steps', card['missing'])
        self.assertFalse(card['factors'])
        self.row('activity', 'manual', {'steps': '1000'}, synthetic=False, source_record_id='personal-low')
        personal = headroom(self.owner, self.day, include_synthetic=False)
        self.assertIn('under half the goal', ' '.join(personal['factors']).lower())
        self.row('activity', 'watch', {'steps': '20000'}, synthetic=True)
        pooled = headroom(self.owner, self.day, include_synthetic=True)
        self.assertFalse(any('steps' in item.lower() for item in pooled['factors']))
        self.assertIn('More than one record. This number stays unknown.', pooled['limitations'])

    def test_a_meal_stays_ahead_of_summary_calories(self):
        self.rate('mood', 7)
        self.rate('energy', 7)
        DietEntry.objects.create(owner=self.owner, local_date=self.day, meal='lunch', description='Synthetic bowl',
                                 calories='400', synthetic=True)
        self.row('nutrition', 'manual', {'calories': '50'})
        self.row('nutrition', 'csv:oura', {'calories': '9000'})
        self.row('nutrition', 'oura', {'calories': '9000'}, entry_method='imported')
        card = headroom(self.owner, self.day, include_synthetic=True)
        self.assertEqual(card['score'], '70.00')
        self.assertIn('food is under half the calorie goal', card['summary'].lower())
        self.assertNotIn('9000', card['summary'])

    def test_null_calories_stay_unknown_and_zero_stays_known(self):
        self.rate('mood', 2)
        self.rate('energy', 2)
        self.row('nutrition', 'manual', {'calories': None, 'protein_g': '40'})
        unknown = headroom(self.owner, self.day, include_synthetic=True)
        self.assertIn('food calories', unknown['missing'])
        self.assertNotIn('no meal is logged', unknown['summary'].lower())
        self.assertNotEqual(unknown['action']['label'], 'Get something to eat')
        direct = _food(self.owner, self.day, True, 'running_low', None)
        self.assertIsNone(direct['drain'])
        self.assertEqual(direct['missing'], 'food calories')
        steady = _food(self.owner, self.day, True, 'steady', None)
        self.assertEqual(steady['missing'], 'food calories')
        self.assertIsNone(steady['drain'])
        DietEntry.objects.create(owner=self.owner, local_date=self.day, meal='snack', description='Unmeasured',
                                 calories=None, synthetic=True)
        SummaryRecord.objects.filter(owner=self.owner, kind='nutrition').delete()
        meal_only = _food(self.owner, self.day, True, 'running_low', None)
        self.assertEqual(meal_only['missing'], 'food calories')
        DietEntry.objects.filter(owner=self.owner).delete()
        absent = _food(self.owner, self.day, True, 'running_low', None)
        self.assertEqual(absent['drain']['text'], 'no meal is logged')
        self.row('nutrition', 'manual', {'calories': '0'})
        zero = headroom(self.owner, self.day, include_synthetic=True)
        self.assertIn('under half the calorie goal', zero['summary'].lower())


class SobrietyInputTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(settings.OWNER_USERNAME)
        self.end = date(2026, 11, 5)

    def day(self, offset):
        return self.end - timedelta(days=offset)

    def ring(self, connection, day, non_wear, marker):
        OuraRecord.objects.create(
            connection=connection, collection='daily_activity', identity_key=f'{marker}-{day.isoformat()}'.ljust(64, '0'),
            source_record_id=f'{marker}-{day.isoformat()}', identity_kind='provider_id',
            raw_json=json.dumps({'day': day.isoformat(), 'non_wear_time': non_wear}))

    def test_accounts_and_raw_duplicates_stay_separate(self):
        personal = OuraConnection.objects.create(
            owner=self.owner, account_key='secret-account-key', source_account_id='secret-external-id',
            token_ciphertext='secret-token-value', synthetic=False, state='disconnected')
        test = OuraConnection.objects.create(
            owner=self.owner, account_key='secret-test-key', synthetic=True, state='authorized')
        self.ring(personal, self.end, 0, 'personal-end')
        self.ring(personal, self.day(2), 0, 'personal-start')
        self.ring(test, self.day(2), 9 * 60 * 60, 'test-conflict')
        self.ring(test, self.day(2), 0, 'test-only')
        SummaryRecord.objects.create(
            owner=self.owner, kind='activity', local_date=self.day(2), source_timezone='America/Chicago',
            source_system='oura', source_record_id='manual-oura', entry_method='manually_reported',
            completeness='partial', values={'steps': '1000'}, synthetic=True)
        before = list(OuraRecord.objects.order_by('id').values_list('id', 'raw_json', 'version'))
        pattern = read_pattern(self.owner, self.end.isoformat(), days=3, include_synthetic=True)
        encoded = json.dumps(pattern)
        self.assertNotIn('secret-account-key', encoded)
        self.assertNotIn('secret-external-id', encoded)
        self.assertNotIn('secret-token-value', encoded)
        self.assertEqual(pattern['formula_version'], FORMULA)
        first = {item['connection_id']: item['status'] for item in pattern['days_detail'][0]['wear']['devices']}
        middle = {item['connection_id']: item['status'] for item in pattern['days_detail'][1]['wear']['devices']}
        self.assertEqual(first[str(personal.id)], 'worn')
        self.assertEqual(first[str(test.id)], 'wear_unknown')
        self.assertEqual(middle[str(personal.id)], 'off_wrist')
        self.assertEqual(middle[str(test.id)], 'source_stale')
        self.assertEqual(len([item for item in pattern['days_detail'][0]['wear']['devices'] if item.get('connection_id') == str(test.id)]), 1)
        self.assertIn('raw_oura_day_unresolved', pattern['days_detail'][0]['limits'])
        self.assertIn('activity', pattern['days_detail'][1]['drivers'])
        self.assertEqual(before, list(OuraRecord.objects.order_by('id').values_list('id', 'raw_json', 'version')))

    def test_excluded_summaries_do_not_enter_rebuilt_coverage_or_old_cache(self):
        SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=self.end, source_timezone='America/Chicago',
            source_system='oura', source_record_id='legacy-sleep-id', entry_method='imported',
            completeness='partial', values={'sleep_minutes': '10'}, synthetic=True)
        SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=self.end, source_timezone='America/Chicago',
            source_system='manual', source_record_id='known-sleep', entry_method='manually_reported',
            completeness='partial', values={'sleep_minutes': '300'}, synthetic=True)
        outside = self.end - timedelta(days=5)
        seeded = {'activity': [{'values': {'steps': '999'}}], 'unsafe': 'legacy-row-id'}
        SobrietyDay.objects.create(
            owner=self.owner, local_date=outside, formula_version=FORMULA, synthetic=True,
            potential='high', use_recorded=False, wear={'devices': []}, drivers=['sleep'], coverage=seeded)
        inside = SobrietyDay.objects.create(
            owner=self.owner, local_date=self.end - timedelta(days=1), formula_version=FORMULA, synthetic=True,
            potential='high', use_recorded=False, wear={'devices': []}, drivers=['sleep'], coverage=seeded)
        with CaptureQueriesContext(connection) as captured:
            pattern = read_pattern(self.owner, self.end.isoformat(), days=3, include_synthetic=True)
        text = json.dumps(pattern)
        self.assertNotIn('legacy-sleep-id', text)
        self.assertNotIn('999', text)
        self.assertIn('sleep', pattern['days_detail'][-1]['drivers'])
        self.assertEqual(pattern['days_detail'][-1]['coverage']['evidence_gate_version'], 'h0-b2')
        self.assertIn('excluded_summary_not_used', pattern['days_detail'][-1]['limits'])
        kept = SobrietyDay.objects.get(owner=self.owner, local_date=outside, synthetic=True)
        self.assertEqual(kept.coverage, seeded)
        self.assertNotEqual(kept.id, inside.id)
        refreshed = SobrietyDay.objects.get(owner=self.owner, local_date=self.end - timedelta(days=1), synthetic=True)
        self.assertEqual(refreshed.coverage['evidence_gate_version'], 'h0-b2')
        self.assertNotIn('legacy-row-id', json.dumps(refreshed.coverage))
        written = ' '.join(query['sql'].lower() for query in captured.captured_queries)
        for table in ('tracking_summaryrecord', 'tracking_summarycorrection', 'tracking_writerequest',
                      'tracking_ouraconnection', 'tracking_ourarecord'):
            self.assertNotIn(f'update {table}', written)
            self.assertNotIn(f'insert into {table}', written)
            self.assertNotIn(f'delete from {table}', written)

    def test_metric_coverage_keeps_independent_values_and_identity(self):
        hrv = SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=self.end, source_timezone='America/Chicago',
            source_system='oura', source_record_id='hrv-only', entry_method='manually_reported',
            completeness='partial', values={'sleep_minutes': None, 'hrv_ms': '50', 'hrv_method': 'rmssd',
                                            'readiness_score': '80'}, synthetic=True)
        pattern = read_pattern(self.owner, self.end.isoformat(), days=1, include_synthetic=True)
        recovery = pattern['days_detail'][0]['coverage']['recovery']
        self.assertTrue(recovery)
        self.assertEqual(recovery[0]['summary_id'], str(hrv.id))
        self.assertEqual(recovery[0]['entry_method'], 'manually_reported')
        self.assertIs(recovery[0]['synthetic'], True)
        self.assertEqual(recovery[0]['values']['hrv_ms'], '50')
        self.assertEqual(pattern['days_detail'][0]['potential'], 'lower')
        SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=self.end, source_timezone='America/Chicago',
            source_system='manual', source_record_id='sleep-hrv', entry_method='manually_reported',
            completeness='partial', values={'sleep_minutes': '480', 'hrv_ms': '25', 'hrv_method': 'rmssd'},
            synthetic=False)
        SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=self.end, source_timezone='America/Chicago',
            source_system='csv:oura', source_record_id='hrv-other', entry_method='manually_reported',
            completeness='partial', values={'sleep_minutes': None, 'hrv_ms': '75', 'hrv_method': 'sdnn'},
            synthetic=False)
        mixed = read_pattern(self.owner, self.end.isoformat(), days=1, include_synthetic=True)
        rows = mixed['days_detail'][0]['coverage']['recovery']
        self.assertFalse(any((row['values'] or {}).get('hrv_ms') == '25' for row in rows))
        self.assertGreaterEqual(len(mixed['days_detail'][0]['coverage']['alternatives']['hrv_ms']), 2)
        stored = SobrietyDay.objects.get(owner=self.owner, local_date=self.end, synthetic=True)
        self.assertEqual(stored.coverage['recovery'][0]['summary_id'], rows[0]['summary_id'])
        self.assertIn('stored_class', stored.coverage['recovery'][0]['identity'])

    def test_unavailable_days_do_not_become_gap_anchors(self):
        SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=self.day(1), source_timezone='America/Chicago',
            source_system='oura', source_record_id='manual-prior', entry_method='manually_reported',
            completeness='partial', values={'sleep_minutes': '480'}, synthetic=True)
        SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=self.end, source_timezone='America/Chicago',
            source_system='oura', source_record_id='legacy-today', entry_method='imported',
            completeness='partial', values={'sleep_minutes': '480'}, synthetic=True)
        exact = read_pattern(self.owner, self.end.isoformat(), days=3, include_synthetic=True)
        self.assertNotIn('sleep', exact['days_detail'][-1]['drivers'])
        stored = SobrietyDay.objects.get(owner=self.owner, local_date=self.end, synthetic=True)
        self.assertNotIn('sleep', stored.drivers)
        for offset in (0, 2):
            for name in ('watch-A', 'watch-B'):
                SummaryRecord.objects.create(
                    owner=self.owner, kind='recovery', local_date=self.day(offset), source_timezone='America/Chicago',
                    source_system=name, source_record_id=f'{name}-{offset}', entry_method='manually_reported',
                    completeness='partial', values={'sleep_minutes': '300'}, synthetic=True)
        watches = read_pattern(self.owner, self.end.isoformat(), days=3, include_synthetic=True)
        self.assertNotIn('off_wrist', watches['days_detail'][1]['drivers'])
        connection = OuraConnection.objects.create(
            owner=self.owner, account_key='secret-boundary', synthetic=False, state='disconnected')
        for offset in (0, 2):
            for marker in ('one', 'two'):
                OuraRecord.objects.create(
                    connection=connection, collection='daily_activity',
                    identity_key=f'{offset}-{marker}'.ljust(64, '0'), identity_kind='provider_id',
                    source_record_id=f'{offset}-{marker}',
                    raw_json=json.dumps({'day': self.day(offset).isoformat(), 'non_wear_time': 0}))
        raw = read_pattern(self.owner, self.end.isoformat(), days=3, include_synthetic=True)
        self.assertNotIn('off_wrist', raw['days_detail'][1]['drivers'])
        self.assertTrue(raw['days_detail'][0]['wear']['devices'][0]['synthetic'] is False)
        self.assertEqual(raw['days_detail'][0]['wear']['devices'][0]['connection_id'], str(connection.id))
        self.assertNotIn('secret-boundary', json.dumps(raw))
        SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=self.end - timedelta(days=8),
            source_timezone='America/Chicago', source_system='oura', source_record_id='lookback-manual',
            entry_method='manually_reported', completeness='partial', values={'sleep_minutes': '480'}, synthetic=True)
        SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=self.day(2), source_timezone='America/Chicago',
            source_system='oura', source_record_id='lookback-legacy', entry_method='imported',
            completeness='partial', values={'sleep_minutes': '480'}, synthetic=True)
        looked = read_pattern(self.owner, self.end.isoformat(), days=3, include_synthetic=True)
        self.assertNotIn('sleep', looked['days_detail'][0]['drivers'])
        self.assertEqual(looked['days_detail'][0]['coverage']['evidence_gate_version'], 'h0-b2')

    def test_headroom_copy_wraps_without_hiding_overflow(self):
        css = Path(settings.BASE_DIR, 'tracking/static/tracking/app.css').read_text()
        rule = css.split('.headroom .headroom-copy{', 1)[1].split('}', 1)[0]
        self.assertIn('overflow-wrap:anywhere', rule)
        self.assertNotIn('overflow:hidden', rule)
        self.client.force_login(self.owner)
        page = self.client.get(f'/?day={self.end.isoformat()}&synthetic=1')
        self.assertContains(page, 'headroom-copy')

    def recovery(self, source, day, values, device='', synthetic=False, method='manually_reported'):
        stored = validate_values('recovery', values, device)
        return SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=day, source_timezone='America/Chicago',
            source_system=source, source_record_id=uuid4().hex, entry_method=method, device=device,
            completeness='partial', values=stored, synthetic=synthetic)

    def test_contested_middle_day_is_unavailable_and_other_sources_remain(self):
        for offset, minutes in ((2, '480'), (0, '480')):
            self.recovery('watch-a', self.day(offset), {'sleep_minutes': minutes, 'hrv_method': ''})
        self.recovery('watch-b', self.day(1), {'sleep_minutes': '300', 'hrv_method': ''})
        self.recovery('watch-a', self.day(1), {'sleep_minutes': '480', 'hrv_method': ''})
        SummaryRecord.objects.create(
            owner=self.owner, kind='activity', local_date=self.day(1), source_timezone='America/Chicago',
            source_system='watch-a', source_record_id='steps-middle', entry_method='manually_reported',
            device='desk', completeness='partial',
            values=validate_values('activity', {'steps': '8000'}), synthetic=False)
        pattern = read_pattern(self.owner, self.end.isoformat(), days=3, include_synthetic=True)
        middle = pattern['days_detail'][1]
        statuses = {item['name']: item['status'] for item in middle['wear']['devices']}
        self.assertEqual(statuses['watch-a'], 'wear_unknown')
        self.assertEqual(statuses['watch-b'], 'wear_unknown')
        self.assertEqual(statuses['desk'], 'worn')
        self.assertNotIn('off_wrist', middle['drivers'])
        self.assertNotEqual(middle['potential'], 'rising')
        stored = SobrietyDay.objects.get(owner=self.owner, local_date=self.day(1), synthetic=True)
        self.assertNotIn('off_wrist', stored.drivers)
        self.recovery('watch-c', self.day(1), {'sleep_minutes': '480', 'hrv_method': ''})
        self.recovery('watch-d', self.day(1), {'sleep_minutes': '480', 'hrv_method': ''})
        equal = read_pattern(self.owner, self.end.isoformat(), days=3, include_synthetic=True)
        self.assertNotIn('off_wrist', equal['days_detail'][1]['drivers'])
        self.recovery('watch-look', self.end - timedelta(days=4), {'sleep_minutes': '480', 'hrv_method': ''})
        self.recovery('watch-look', self.end, {'sleep_minutes': '480', 'hrv_method': ''})
        self.recovery('watch-other', self.day(2), {'sleep_minutes': '300', 'hrv_method': ''})
        self.recovery('watch-look', self.day(2), {'sleep_minutes': '480', 'hrv_method': ''})
        looked = read_pattern(self.owner, self.end.isoformat(), days=3, include_synthetic=True)
        first = looked['days_detail'][0]
        self.assertEqual({item['name']: item['status'] for item in first['wear']['devices']}['watch-look'], 'wear_unknown')
        self.assertNotIn('off_wrist', first['drivers'])
        saved = SobrietyDay.objects.get(owner=self.owner, local_date=self.day(2), synthetic=True)
        self.assertNotIn('off_wrist', saved.drivers)

    def test_a_real_watch_hole_stays_a_hole_beside_excluded_oura(self):
        self.recovery('watch-a', self.day(2), {'sleep_minutes': '480', 'hrv_method': ''})
        self.recovery('watch-a', self.end, {'sleep_minutes': '480', 'hrv_method': ''})
        self.recovery('oura', self.day(1), {'sleep_minutes': '480', 'hrv_method': ''}, method='imported')
        pattern = read_pattern(self.owner, self.end.isoformat(), days=3, include_synthetic=True)
        statuses = {item['name']: item['status'] for item in pattern['days_detail'][1]['wear']['devices']}
        self.assertEqual(statuses['watch-a'], 'off_wrist')
        self.assertIn('off_wrist', pattern['days_detail'][1]['drivers'])

    def test_metadata_only_coverage_does_not_count_as_known(self):
        blank = read_pattern(self.owner, self.end.isoformat(), days=1, include_synthetic=True)
        self.assertEqual(blank['days_detail'][0]['potential'], 'incomplete')
        SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=self.end, source_timezone='America/Chicago',
            source_system='manual', source_record_id='metadata-only', entry_method='manually_reported',
            completeness='partial', values={'sleep_minutes': None, 'hrv_ms': None, 'resting_hr_bpm': None,
                                            'readiness': None, 'hrv_method': ''}, synthetic=False)
        metadata = read_pattern(self.owner, self.end.isoformat(), days=1, include_synthetic=True)
        self.assertEqual(metadata['days_detail'][0]['potential'], 'incomplete')
        self.assertFalse(metadata['days_detail'][0]['coverage']['recovery'])
        self.recovery('oura', self.end, {'sleep_minutes': '480', 'hrv_method': ''})
        self.recovery('csv:oura', self.end, {'sleep_minutes': '480', 'hrv_method': ''})
        contested = read_pattern(self.owner, self.end.isoformat(), days=1, include_synthetic=True)
        self.assertEqual(contested['days_detail'][0]['potential'], 'incomplete')
        self.assertFalse(contested['days_detail'][0]['coverage']['recovery'])

    def test_schema_units_and_hrv_alternatives_keep_their_identity(self):
        nutrition = validate_values('nutrition', {
            'calories': '0', 'protein': '10', 'total_carbohydrates': '20', 'fat': '5', 'fiber': '3'})
        SummaryRecord.objects.create(
            owner=self.owner, kind='nutrition', local_date=self.end, source_timezone='America/Chicago',
            source_system='manual', source_record_id='nutrition-units', entry_method='manually_reported',
            completeness='complete', values=nutrition, synthetic=False)
        readiness = self.recovery('manual', self.end, {'readiness': '80', 'hrv_method': ''}, device='band')
        pattern = read_pattern(self.owner, self.end.isoformat(), days=1, include_synthetic=True)
        units = {item['name']: item['unit'] for item in pattern['days_detail'][0]['coverage']['nutrition'][0]['identity']['metrics']}
        self.assertEqual(units['protein'], 'g')
        self.assertEqual(units['total_carbohydrates'], 'g')
        self.assertEqual(units['fat'], 'g')
        self.assertEqual(units['fiber'], 'g')
        self.assertEqual(units['calories'], 'kcal')
        recovery_units = {item['name']: item['unit'] for item in pattern['days_detail'][0]['coverage']['recovery'][0]['identity']['metrics']}
        self.assertEqual(recovery_units['readiness'], '/100')
        self.assertEqual(pattern['days_detail'][0]['coverage']['recovery'][0]['summary_id'], str(readiness.id))
        first = self.recovery('csv:oura', self.end, {'hrv_ms': '25', 'hrv_method': 'SDNN'}, device='band-b', synthetic=True)
        second = self.recovery('desk', self.end, {'hrv_ms': '25', 'hrv_method': 'RMSSD'}, device='band-a', synthetic=False)
        SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=self.end, source_timezone='America/Chicago',
            source_system='watch', source_record_id='hrv-blank', entry_method='manually_reported', device='band-c',
            completeness='partial', values={'sleep_minutes': None, 'hrv_ms': '25', 'resting_hr_bpm': None,
                                            'readiness': None, 'hrv_method': ''}, synthetic=False)
        mixed = read_pattern(self.owner, self.end.isoformat(), days=1, include_synthetic=True)
        alternatives = mixed['days_detail'][0]['coverage']['alternatives']['hrv_ms']
        methods = {item['summary_id']: item for item in alternatives}
        self.assertEqual(methods[str(first.id)]['hrv_method'], 'SDNN')
        self.assertEqual(methods[str(second.id)]['hrv_method'], 'RMSSD')
        self.assertIsNone(methods[str(SummaryRecord.objects.get(source_record_id='hrv-blank').id)]['hrv_method'])
        self.assertTrue(all(item['unit'] == 'ms' and item['metric'] == 'hrv_ms' for item in alternatives))
        self.assertEqual(methods[str(first.id)]['stored_class'], 'test')
        self.assertEqual(methods[str(second.id)]['stored_class'], 'personal')
        stored = SobrietyDay.objects.get(owner=self.owner, local_date=self.end, synthetic=True)
        self.assertEqual(stored.coverage['alternatives']['hrv_ms'], alternatives)
