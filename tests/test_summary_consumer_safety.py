"""B1 calculation gates. Fabricated rows only. History stays readable and calculations do not write."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID, uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from tracking.models import DietEntry, NutritionTargets, OuraConnection, SummaryRecord
from tracking.plan import fitness_plan
from tracking.projection_identity import stable_source_id
from tracking.summary_evidence import summary_series_token
from tracking.summary_views import weekly_averages
from tracking.today import day_metrics
from tracking.trends import observations
from tracking.watch import watch_signals


class SummaryConsumerSafetyTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(settings.OWNER_USERNAME)
        self.other = get_user_model().objects.create_user('synthetic-consumer-other')
        self.day = timezone.localdate()

    def activity(self, owner, day, source, steps, **changes):
        values = {'steps': steps, 'workout_minutes': None, 'active_calories': '1', 'total_calories': '1'}
        fields = {
            'owner': owner, 'kind': 'activity', 'local_date': day, 'source_timezone': 'America/Chicago',
            'source_system': source, 'source_record_id': uuid4().hex, 'entry_method': 'imported',
            'device': 'Oura', 'completeness': 'complete', 'values': values, 'synthetic': False,
        }
        fields.update(changes)
        return SummaryRecord.objects.create(**fields)

    def derived(self, status, synthetic, day, steps):
        ring = OuraConnection.objects.create(
            owner=self.owner, account_key=f'fabricated-{uuid4().hex[:12]}',
            source_account_id='fabricated-external-account', synthetic=synthetic,
            token_ciphertext='fabricated-token-value', state='disconnected')
        raw_id = str(uuid4())
        ever = [{'raw_id': raw_id, 'identity_key': 'ab' * 32, 'collection': 'daily_activity',
                 'source_record_id': 'fabricated-provider'}]
        current = [] if status != 'current' else [{**ever[0], 'version': 1}]
        stored_status = 'current' if status == 'invalid' else status
        return SummaryRecord.objects.create(
            owner=self.owner, kind='activity', local_date=day, source_timezone='', source_system='oura',
            source_record_id=stable_source_id(ring, 'activity', day), entry_method='derived', device='Oura',
            completeness='partial', values={'steps': steps, 'active_calories': '1', 'total_calories': '1'},
            synthetic=synthetic, connection=ring,
            derivation={
                'schema_version': [] if status == 'invalid' else 2, 'recipe_version': 1,
                'account_id': str(ring.id), 'timezone_status': 'unknown', 'status': stored_status,
                'quality': stored_status, 'current_contributors': current, 'contributor_identities_ever': ever,
                'conflict_reason': '',
            })

    def test_legacy_and_derived_history_is_not_calculation_evidence(self):
        manual = self.activity(self.owner, self.day, 'manual', '0', entry_method='manually_reported', device='Desk')
        self.activity(self.owner, self.day - timedelta(days=1), 'oura', '99', synthetic=False)
        self.activity(self.owner, self.day - timedelta(days=2), 'oura', '88', synthetic=True)
        for index, status in enumerate(('current', 'stale', 'conflict', 'invalid')):
            self.derived(status, index % 2 == 1, self.day - timedelta(days=3 + index), str(100 + index))
        self.activity(self.other, self.day, 'manual', '500', entry_method='manually_reported')
        self.activity(self.owner, self.day - timedelta(days=8), 'manual', None,
                      entry_method='manually_reported', values={'steps': None, 'active_calories': '1',
                      'total_calories': '1', 'workout_minutes': None})
        SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=self.day - timedelta(days=9),
            source_timezone='America/Chicago', source_system='oura', source_record_id='legacy-sleep',
            entry_method='imported', completeness='partial', values={'sleep_minutes': '10'})
        SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=self.day - timedelta(days=10),
            source_timezone='America/Chicago', source_system='manual', source_record_id='manual-sleep',
            entry_method='manually_reported', completeness='complete', values={'sleep_minutes': '400'})
        NutritionTargets.objects.create(owner=self.owner, values={'steps': '10000'})
        before = list(SummaryRecord.objects.order_by('id').values_list(
            'id', 'values', 'version', 'synthetic', 'deleted_at', 'source_record_id'))
        with patch('tracking.projection_identity.refresh_stored_sources', side_effect=AssertionError('refresh called')):
            with CaptureQueriesContext(connection) as captured:
                plan = fitness_plan(self.owner, self.day, include_synthetic=True)
                plotted = observations(self.owner, 'activity:steps', self.day - timedelta(days=12), self.day, True)
                sleep = observations(self.owner, 'recovery:sleep_minutes', self.day - timedelta(days=12), self.day, True)
                metrics = day_metrics(self.owner, self.day, include_synthetic=True)
                signals = watch_signals(self.owner, self.day, include_synthetic=True)
        self.assertEqual(plan['analysis']['steps'][0]['average'], '0.0')
        self.assertEqual(plan['analysis']['steps'][0]['observed_days'], 1)
        self.assertEqual(plan['analysis']['steps'][0]['series_id'],
                         summary_series_token(('steps', 'manual', 'Desk', 'manually_reported', False)))
        self.assertFalse(plan['analysis']['steps'][0]['synthetic'])
        self.assertGreaterEqual(plan['evidence']['unresolved_count'], 2)
        self.assertGreaterEqual(plan['evidence']['unavailable_count'], 4)
        self.assertNotIn('99', [row['average'] for row in plan['analysis']['steps']])
        self.assertNotIn('500', [row['average'] for row in plan['analysis']['steps']])
        sleep_line = next(line for line in plan['trends'] if line['metric'] == 'recovery:sleep_minutes')
        self.assertEqual(sleep_line['series'][0]['last'], '400')
        self.assertNotIn('10', [row['value'] for row in sleep['rows']])
        self.assertNotIn('99', [row['value'] for row in plotted['rows']])
        self.assertIn('0', [row['value'] for row in plotted['rows']])
        self.assertEqual(metrics['chips'][2]['value'], '0')
        self.assertTrue(metrics['chips'][2]['logged'])
        self.assertEqual(metrics['chips'][2]['bar'], 0)
        self.assertEqual(signals['activity'][0]['summary_id'], str(manual.id))
        self.assertEqual(signals['activity'][0]['steps'], '0')
        self.assertEqual(signals['activity_evidence']['status'], 'value')
        self.assertNotIn('fabricated-token-value', str(plan) + str(signals))
        self.assertNotIn('fabricated-external-account', str(plan) + str(signals))
        self.assertEqual(list(SummaryRecord.objects.order_by('id').values_list(
            'id', 'values', 'version', 'synthetic', 'deleted_at', 'source_record_id')), before)
        watched = ('tracking_summary', 'tracking_summarycorrection', 'tracking_writerequest', 'tracking_ouraconnection', 'tracking_ourarecord')
        self.assertFalse(any(item['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'REPLACE'))
                             and any(table in item['sql'].lower() for table in watched) for item in captured))

    def test_competing_sources_and_classes_stay_unselected(self):
        day = self.day - timedelta(days=10)
        later = self.day - timedelta(days=11)
        self.activity(self.owner, day, 'manual', '5', entry_method='manually_reported', device='Desk')
        self.activity(self.owner, day, 'csv:oura', '5', entry_method='imported', device='CSV')
        self.activity(self.owner, later, 'csv:oura', '7', entry_method='imported', device='CSV')
        self.activity(self.owner, later, 'manual', '7', entry_method='manually_reported', device='Desk')
        self.activity(self.owner, self.day - timedelta(days=12), 'manual', '10',
                      entry_method='manually_reported', device='Desk', synthetic=False)
        self.activity(self.owner, self.day - timedelta(days=13), 'manual', '4',
                      entry_method='manually_reported', device='Desk', synthetic=True)
        plan = fitness_plan(self.owner, self.day, include_synthetic=True)
        series = {row['series_id']: row for row in plan['analysis']['steps']}
        self.assertEqual(len(series), 3)
        personal = next(row for row in series.values() if row['source'] == 'manual' and row['synthetic'] is False)
        tested = next(row for row in series.values() if row['synthetic'] is True)
        imported = next(row for row in series.values() if row['source'] == 'csv:oura')
        self.assertEqual(tested['average'], '4.0')
        self.assertEqual(tested['observed_days'], 1)
        self.assertNotEqual(personal['average'], '4.0')
        self.assertEqual(imported['observed_days'], 2)
        self.assertNotEqual(imported['average'], '5')
        forward = day_metrics(self.owner, day)
        reverse = day_metrics(self.owner, later)
        self.assertEqual(forward['evidence']['steps']['status'], 'selection_required')
        self.assertIsNone(forward['evidence']['steps']['value'])
        self.assertEqual([item['value'] for item in forward['evidence']['steps']['alternatives']], ['5', '5'])
        self.assertEqual(reverse['evidence']['steps']['status'], 'selection_required')
        self.assertEqual(sorted(item['source_system'] for item in reverse['evidence']['steps']['alternatives']),
                         ['csv:oura', 'manual'])
        self.assertFalse(forward['chips'][2]['logged'])
        self.assertIsNone(forward['chips'][2]['bar'])
        signals = watch_signals(self.owner, day)
        self.assertEqual(signals['activity'], [])
        self.assertEqual(signals['activity_evidence']['status'], 'selection_required')
        self.assertEqual(len(signals['activity_evidence']['alternatives']), 2)
        self.assertEqual(sorted(item['entry_method'] for item in signals['activity_evidence']['alternatives']),
                         ['imported', 'manually_reported'])
        self.client.force_login(self.owner)
        page = self.client.get(f'/?day={day.isoformat()}')
        self.assertContains(page, 'More than one record')
        self.assertNotContains(page, 'aria-label="Steps"')

    def test_weekly_history_keeps_rows_and_refuses_same_day_duplicates(self):
        rows = [self.activity(self.owner, self.day - timedelta(days=offset), 'oura', '12') for offset in range(31)]
        left = SummaryRecord(owner=self.owner, kind='nutrition', local_date=self.day, source_system='manual',
                             device='', synthetic=False, entry_method='manually_reported', completeness='complete',
                             values={'calories': '8', 'protein': '1', 'total_carbohydrates': None, 'fat': None, 'fiber': None})
        right = SummaryRecord(owner=self.owner, kind='nutrition', local_date=self.day, source_system='manual',
                              device='', synthetic=False, entry_method='manually_reported', completeness='complete',
                              values={'calories': '8', 'protein': '1', 'total_carbohydrates': None, 'fat': None, 'fiber': None})
        group = weekly_averages([left, right], 'nutrition')[0]
        # Unsaved on purpose: unique_daily_summary_source forbids this stored duplicate.
        self.assertEqual((group['observed'], group['observed_days'], group['ambiguous_days']), (2, 1, 1))
        self.assertEqual((group['complete'], group['complete_days']), (2, 0))
        self.assertIsNone(group['averages'][0]['value'])
        self.assertEqual(group['averages'][0]['count'], 0)
        from django.template.loader import render_to_string
        from django.test import RequestFactory
        request = RequestFactory().get('/summaries/nutrition/')
        request.user = self.owner
        request.resolver_match = type('Match', (), {'url_name': 'summary_list'})()
        rendered = render_to_string('tracking/summaries.html', {
            'title': 'Nutrition', 'kind': 'nutrition', 'week_start': self.day, 'week_end': self.day,
            'weekly': [group], 'week_evidence': {'unresolved_count': 0, 'unavailable_count': 0},
            'unresolved_history_count': 0, 'entries': [], 'synthetic': False, 'target_values': None,
            'page': type('Page', (), {'has_previous': False, 'has_next': False})(),
        }, request=request)
        self.assertIn('2 complete observations', rendered)
        self.assertIn('0 complete days out of 7', rendered)
        self.assertNotIn('2 complete out of 7', rendered)
        self.assertNotIn('2 complete days out of 7', rendered)
        self.client.force_login(self.owner)
        page = self.client.get('/summaries/activity/')
        second = self.client.get('/summaries/activity/?page=2')
        detail = self.client.get(f'/summaries/activity/{rows[1].id}/')
        self.assertEqual(page.context['weekly'], [])
        self.assertContains(page, 'Unresolved Oura history is not used')
        self.assertContains(page, 'Unresolved history')
        self.assertContains(page, str(rows[0].id))
        self.assertContains(detail, rows[1].source_record_id)
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, 'Previous')
        self.assertContains(detail, '12')
        self.assertEqual(SummaryRecord.objects.filter(owner=self.owner).count(), 31)

    def test_meals_remain_explicit_when_summary_fallback_is_ambiguous(self):
        DietEntry.objects.create(owner=self.owner, local_date=self.day, meal='lunch', description='Synthetic bowl',
                                 calories=0, synthetic=False)
        for source, calories in (('manual', '50'), ('csv:oura', '60')):
            SummaryRecord.objects.create(
                owner=self.owner, kind='nutrition', local_date=self.day, source_timezone='America/Chicago',
                source_system=source, source_record_id=source, entry_method='manually_reported',
                completeness='partial', values={'calories': calories, 'protein': '20', 'total_carbohydrates': None,
                                                'fat': None, 'fiber': None})
        metrics = day_metrics(self.owner, self.day)
        self.assertEqual(metrics['calories']['value'], '0')
        self.assertEqual(metrics['calories']['status'], 'value')
        self.assertTrue(metrics['calories']['logged'])
        self.assertEqual(metrics['evidence']['protein']['status'], 'selection_required')
        self.assertIsNone(metrics['chips'][0]['value'])
        self.assertIsNone(metrics['chips'][0]['bar'])

    def _recovery(self, day, source, device, method, sleep):
        from tracking.summaries import validate_values
        values = validate_values('recovery', {
            'sleep_minutes': sleep, 'hrv_ms': None, 'resting_hr_bpm': None, 'readiness': None, 'hrv_method': '',
        })
        return SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=day, source_timezone='America/Chicago',
            source_system=source, source_record_id=uuid4().hex, entry_method=method, device=device,
            completeness='complete', values=values, synthetic=False)

    def test_same_day_weight_readings_stay_on_the_chart(self):
        from decimal import Decimal
        from uuid import UUID
        from tracking.models import Measurement
        first = UUID('00000000-0000-4000-8000-000000000001')
        second = UUID('00000000-0000-4000-8000-000000000002')
        Measurement.objects.create(
            id=first, owner=self.owner, metric='weight', value=Decimal('70.000'), unit='kg',
            local_date=self.day, observed_at=timezone.now(), source_system='manual',
            source_record_id='weight-with-time', synthetic=False)
        Measurement.objects.create(
            id=second, owner=self.owner, metric='weight', value=Decimal('71.000'), unit='kg',
            local_date=self.day, observed_at=None, source_system='manual',
            source_record_id='weight-without-time', synthetic=False)
        plotted = observations(self.owner, 'measurements:weight', self.day, self.day, False)
        self.assertEqual(plotted['count'], 2)
        self.assertEqual([row['value'] for row in plotted['rows']], ['70.000', '71.000'])
        self.assertEqual(plotted['evidence']['ambiguous_days'], 0)
        self.assertEqual(plotted['evidence']['notice'], '')
        plan = fitness_plan(self.owner, self.day)
        weight = next(line for line in plan['trends'] if line['metric'] == 'measurements:weight')
        self.assertEqual(weight['series'][0]['observed'], 2)
        self.assertFalse(weight['evidence']['ambiguous_days'])
        self.client.force_login(self.owner)
        page = self.client.get('/trends/', {'metric': 'measurements:weight', 'start': self.day.isoformat(),
                                             'end': self.day.isoformat()})
        self.assertContains(page, '2 observations')
        self.assertContains(page, '70.000')
        self.assertContains(page, '71.000')
        self.assertNotContains(page, 'Unresolved history')

    def test_entry_method_and_display_delimiters_do_not_merge_series(self):
        yesterday = self.day - timedelta(days=1)
        self._recovery(yesterday, 'manual', 'device-A', 'manually_reported', '8')
        self._recovery(self.day, 'manual', 'device-A', 'imported', '4')
        plotted = observations(self.owner, 'recovery:sleep_minutes', yesterday, self.day, False)
        self.assertEqual(len(plotted['datasets']), 2)
        self.assertEqual(sorted(row['value'] for row in plotted['rows']), ['4', '8'])
        plan = fitness_plan(self.owner, self.day)
        sleep = next(line for line in plan['trends'] if line['metric'] == 'recovery:sleep_minutes')
        self.assertEqual(sorted(row['observed'] for row in sleep['series']), [1, 1])
        self.assertTrue(all(row['change'] is None for row in sleep['series']))
        self.assertEqual(len({row['series_id'] for row in sleep['series']}), 2)
        groups = weekly_averages(SummaryRecord.objects.filter(owner=self.owner, kind='recovery'), 'recovery')
        self.assertEqual(sorted(group['entry_method'] for group in groups), ['imported', 'manually_reported'])
        sleep_averages = [field for group in groups for field in group['averages'] if field['label'] == 'Sleep duration']
        self.assertEqual(sorted(field['value'] for field in sleep_averages), [Decimal('4.00'), Decimal('8.00')])
        self.activity(self.owner, yesterday, 'manual', '8', entry_method='manually_reported', device='device-A')
        self.activity(self.owner, self.day, 'manual', '4', entry_method='imported', device='device-A')
        steps = weekly_averages(SummaryRecord.objects.filter(owner=self.owner, kind='activity'), 'activity')
        step_values = [field['value'] for group in steps for field in group['averages'] if field['label'] == 'Steps']
        self.assertEqual(sorted(step_values), [Decimal('4.00'), Decimal('8.00')])
        self.assertNotIn(Decimal('6.00'), step_values)
        early = yesterday - timedelta(days=2)
        later = yesterday - timedelta(days=1)
        self._recovery(later, 'manual · min', 'device-A', 'imported', '3')
        self._recovery(early, 'manual', 'min · device-A', 'imported', '6')
        collision = observations(self.owner, 'recovery:sleep_minutes', early, self.day, False)
        collision_rows = [row for row in collision['rows'] if row['date'] in {early, later}]
        self.assertEqual(len(collision_rows), 2)
        self.assertEqual(len({row['series_id'] for row in collision_rows}), 2)
        self.assertEqual({row['source'] for row in collision_rows}, {collision_rows[0]['source']})

    def test_health_cutoff_does_not_select_one_side_of_a_split_day(self):
        from tracking.summaries import validate_values
        yesterday = self.day - timedelta(days=1)
        filler = []
        for index in range(1999):
            values = validate_values('health', {
                'name': f'filler-{index}', 'unit': 'mg/dL', 'value': '1', 'reference_range': '',
            })
            filler.append(SummaryRecord(
                owner=self.owner, kind='health', local_date=yesterday, source_timezone='America/Chicago',
                source_system='manual', source_record_id=f'filler-{index}', entry_method='manually_reported',
                device='', completeness='complete', values=values, synthetic=False))
        SummaryRecord.objects.bulk_create(filler, batch_size=500)

        def boundary(left, right):
            SummaryRecord.objects.filter(source_record_id__startswith='boundary-').delete()
            for name, value in (('boundary-low', left), ('boundary-high', right)):
                values = validate_values('health', {
                    'name': 'boundary-lab', 'unit': 'mg/dL', 'value': value, 'reference_range': '0-1',
                })
                SummaryRecord.objects.create(
                    id=UUID('00000000-0000-4000-8000-000000000010') if name.endswith('low') else UUID('ffffffff-ffff-4fff-bfff-ffffffffffff'),
                    owner=self.owner, kind='health', local_date=self.day, source_timezone='America/Chicago',
                    source_system='manual', source_record_id=name, entry_method='manually_reported',
                    device='', completeness='complete', values=values, synthetic=False)
            plotted = observations(self.owner, 'health:value', yesterday, self.day, False)
            self.assertTrue(plotted['truncated'])
            self.assertEqual(plotted['evidence']['boundary_excluded'], 1)
            self.assertEqual(plotted['count'], 1999)
            self.assertNotIn(left, [row['value'] for row in plotted['rows']])
            self.assertNotIn(right, [row['value'] for row in plotted['rows']])
            self.assertTrue(all(row['value'] == '1' for row in plotted['rows']))

        boundary('123', '987')
        boundary('987', '123')
        boundary('5', '5')

    def test_plan_trend_keeps_the_record_limit(self):
        from decimal import Decimal
        from tracking.models import Measurement
        Measurement.objects.bulk_create([
            Measurement(
                owner=self.owner, metric='weight', value=Decimal('70.000'), unit='kg', local_date=self.day,
                source_system='manual', source_record_id=f'cap-{index}', synthetic=False)
            for index in range(2001)
        ], batch_size=500)
        plotted = observations(self.owner, 'measurements:weight', self.day - timedelta(days=89), self.day, False)
        self.assertTrue(plotted['truncated'])
        self.assertEqual(plotted['count'], 2000)
        plan = fitness_plan(self.owner, self.day)
        weight = next(line for line in plan['trends'] if line['metric'] == 'measurements:weight')
        self.assertTrue(weight['truncated'])
        self.assertEqual(weight['evidence']['ambiguous_days'], 0)
        self.client.force_login(self.owner)
        page = self.client.get('/plan/')
        self.assertContains(page, 'Limited to the first 2000 records.')

    def test_watch_metric_availability_keeps_zero_and_ignores_null_competitors(self):
        self.activity(self.owner, self.day, 'manual', None, entry_method='manually_reported', device='device-A',
                      values={'steps': None, 'workout_minutes': None, 'active_calories': None, 'total_calories': None,
                              'workout_summary': ''})
        blank = watch_signals(self.owner, self.day)
        self.assertEqual(blank['activity'], [])
        self.assertEqual(blank['activity_evidence']['status'], 'unavailable')
        self.assertEqual(blank['activity_evidence']['metrics']['steps']['status'], 'unavailable')
        zero_day = self.day - timedelta(days=1)
        self.activity(self.owner, zero_day, 'manual', '0', entry_method='manually_reported', device='device-A')
        zero = watch_signals(self.owner, zero_day)
        self.assertEqual(zero['activity_evidence']['status'], 'value')
        self.assertEqual(zero['activity'][0]['steps'], '0')
        self.assertEqual(zero['activity'][0]['entry_method'], 'manually_reported')
        mixed = self.day - timedelta(days=2)
        self.activity(self.owner, mixed, 'manual', None, entry_method='manually_reported', device='device-A',
                      values={'steps': None, 'workout_minutes': None, 'active_calories': None, 'total_calories': None,
                              'workout_summary': ''})
        self.activity(self.owner, mixed, 'csv:oura', '5', entry_method='imported', device='CSV')
        known = watch_signals(self.owner, mixed)
        self.assertEqual(known['activity_evidence']['status'], 'value')
        self.assertEqual(len(known['activity']), 1)
        self.assertEqual(known['activity'][0]['steps'], '5')
        self.assertEqual(known['activity_evidence']['metrics']['steps']['status'], 'value')
        from tracking.summaries import validate_values
        left = validate_values('recovery', {
            'sleep_minutes': '8', 'hrv_ms': None, 'resting_hr_bpm': None, 'readiness': None, 'hrv_method': '',
        })
        right = validate_values('recovery', {
            'sleep_minutes': None, 'hrv_ms': '40', 'resting_hr_bpm': None, 'readiness': None,
            'hrv_method': 'RMSSD',
        }, device='device-B')
        SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=mixed, source_timezone='America/Chicago',
            source_system='manual', source_record_id='sleep-only', entry_method='manually_reported',
            device='device-A', completeness='complete', values=left)
        SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=mixed, source_timezone='America/Chicago',
            source_system='csv:oura', source_record_id='hrv-only', entry_method='imported',
            device='device-B', completeness='complete', values=right)
        recovery = watch_signals(self.owner, mixed)
        self.assertEqual(recovery['recovery_evidence']['status'], 'value')
        self.assertEqual(recovery['recovery_evidence']['metrics']['sleep_minutes']['status'], 'value')
        self.assertEqual(recovery['recovery_evidence']['metrics']['hrv_ms']['status'], 'value')
        self.assertEqual(recovery['recovery_evidence']['metrics']['readiness']['status'], 'unavailable')
        self.assertEqual(len(recovery['recovery']), 2)

    def test_today_shows_alternatives_and_legacy_exclusion_without_a_fake_zero(self):
        shown = []
        for index in range(9):
            record = self.activity(
                self.owner, self.day, f'source-{index}', str(index + 1), entry_method='manually_reported',
                device='<img src=x onerror=alert(1)>' if index == 8 else f'device-{index}')
            shown.append(record)
        metrics = day_metrics(self.owner, self.day)
        self.assertEqual(len(metrics['evidence']['steps']['alternatives']), 9)
        self.assertEqual(len(metrics['chips'][2]['alternatives']), 8)
        self.assertEqual(metrics['evidence']['unresolved_count'], 0)
        self.client.force_login(self.owner)
        page = self.client.get(f'/?day={self.day.isoformat()}')
        self.assertContains(page, 'More than one record')
        self.assertContains(page, '&lt;img src=x')
        self.assertNotContains(page, '<img src=x')
        omitted = metrics['chips'][2]['alternatives']
        shown_ids = {item['summary_id'] for item in omitted}
        self.assertEqual(len(shown_ids), 8)
        for item in omitted:
            self.assertContains(page, f'/summaries/activity/{item["summary_id"]}/')
            self.assertContains(page, item['entry_method'])
        hidden = next(record for record in shown if str(record.id) not in shown_ids)
        self.assertNotContains(page, f'/summaries/activity/{hidden.id}/')
        self.assertEqual(metrics['chips'][2]['alternative_shown'], 8)
        self.assertEqual(metrics['chips'][2]['alternative_total'], 9)
        self.assertContains(page, 'Showing 8 of 9 alternatives')
        self.assertContains(page, 'Activity history')
        self.assertContains(page, metrics['chips'][2]['history_href'])
        history = self.client.get(metrics['chips'][2]['history_href'])
        self.assertContains(history, str(hidden.id))
        legacy_day = self.day - timedelta(days=3)
        self.activity(self.owner, legacy_day, 'oura', '99')
        legacy = self.client.get(f'/?day={legacy_day.isoformat()}')
        self.assertContains(legacy, 'Unresolved history')
        self.assertContains(legacy, '1 unresolved')
        self.assertNotContains(legacy, 'More than one record')
        self.assertNotContains(legacy, 'aria-label="Steps"')
        self.assertNotContains(legacy, '>99<')
        derived_day = self.day - timedelta(days=4)
        self.derived('current', False, derived_day, '77')
        derived = self.client.get(f'/?day={derived_day.isoformat()}')
        self.assertContains(derived, '1 unavailable')
        self.assertNotContains(derived, 'More than one record')
        self.assertNotContains(derived, 'aria-label="Steps"')

    def test_direct_plan_ids_keep_pipe_tuples_distinct(self):
        from tracking.summaries import validate_values
        pairs = (
            ('manual|part', 'device', '5', '5', '10', '2'),
            ('manual', 'part|device', '5', '9', '12', '4'),
        )
        for source, device, steps, calories, carbs, fiber in pairs:
            self.activity(self.owner, self.day, source, steps, entry_method='imported', device=device,
                          values=validate_values('activity', {
                              'steps': steps, 'workout_minutes': None, 'active_calories': None,
                              'total_calories': None, 'workout_summary': '',
                          }, device=device))
            SummaryRecord.objects.create(
                owner=self.owner, kind='nutrition', local_date=self.day, source_timezone='America/Chicago',
                source_system=source, source_record_id=f'nutrition-{source}', entry_method='imported',
                device=device, completeness='complete', synthetic=False,
                values=validate_values('nutrition', {
                    'calories': calories, 'protein': '1', 'total_carbohydrates': carbs, 'fat': None, 'fiber': fiber,
                }))
        plan = fitness_plan(self.owner, self.day)
        steps = {row['series_id']: row for row in plan['analysis']['steps']}
        calories = {row['series_id']: row for row in plan['analysis']['calories']}
        nets = {row['series_id']: row for row in plan['analysis']['net_carbohydrates']}
        self.assertEqual(len(steps), 2)
        self.assertEqual(len(calories), 2)
        self.assertEqual(len(nets), 2)
        self.assertEqual({row['average'] for row in steps.values()}, {'5.0'})
        self.assertEqual(sorted(row['average'] for row in calories.values()), ['5.0', '9.0'])
        self.assertEqual({row['average'] for row in nets.values()}, {'8.0'})
        self.assertFalse(any('steps|manual|part|device|imported|0' == row['series_id'] for row in steps.values()))
        self.assertEqual({row['source'] for row in steps.values()}, {'manual|part', 'manual'})
        self.assertEqual({row['device'] for row in steps.values()}, {'device', 'part|device'})

    def test_today_discloses_bounded_alternatives_for_each_metric(self):
        from pathlib import Path
        from tracking.summaries import validate_values
        food_day = self.day - timedelta(days=6)
        records = []
        for index in range(9):
            values = validate_values('nutrition', {
                'calories': str(100 + index), 'protein': str(10 + index), 'total_carbohydrates': None,
                'fat': None, 'fiber': str(index),
            })
            record = SummaryRecord(
                owner=self.owner, kind='nutrition', local_date=food_day, source_timezone='America/Chicago',
                source_system=f'food-{index}', source_record_id=f'food-{index}', entry_method='imported',
                device='Y' * 120 if index == 8 else '', completeness='complete', synthetic=index == 0,
                values=values)
            record.full_clean()
            record.save()
            records.append(record)
        metrics = day_metrics(self.owner, food_day, include_synthetic=True)
        self.assertEqual(metrics['calories']['alternative_shown'], 8)
        self.assertEqual(metrics['calories']['alternative_total'], 9)
        self.assertEqual(metrics['calories']['history_href'], '/summaries/nutrition/?synthetic=1')
        for key, chip in (('calories', metrics['calories']), ('protein', metrics['chips'][0]), ('fiber', metrics['chips'][1])):
            self.assertEqual(chip['status'], 'selection_required')
            self.assertEqual((chip['alternative_shown'], chip['alternative_total']), (8, 9))
            self.assertIn('synthetic=1', chip['history_href'])
            self.assertIsNone(chip['value'])
        self.client.force_login(self.owner)
        page = self.client.get(f'/?day={food_day.isoformat()}&synthetic=1')
        self.assertContains(page, 'Showing 8 of 9 alternatives')
        self.assertContains(page, 'Nutrition history')
        self.assertContains(page, 'alternative-list')
        self.assertContains(page, 'Y' * 120)
        hidden = next(record for record in records if str(record.id) not in {item['summary_id'] for item in metrics['calories']['alternatives']})
        self.assertNotContains(page, f'/summaries/nutrition/{hidden.id}/')
        history = self.client.get(metrics['calories']['history_href'])
        self.assertContains(history, str(hidden.id))
        zero_day = self.day - timedelta(days=7)
        self.activity(self.owner, zero_day, 'manual', '0', entry_method='manually_reported', device='Desk')
        NutritionTargets.objects.create(owner=self.owner, values={'steps': '10000', 'calories': '2000'})
        zero = self.client.get(f'/?day={zero_day.isoformat()}')
        self.assertContains(zero, 'aria-label="Steps"')
        self.assertContains(zero, 'class="w-0"')
        self.assertNotContains(zero, 'alternative-list')
        self.assertNotContains(zero, 'Showing 8 of')
        equal_day = self.day - timedelta(days=8)
        self.activity(self.owner, equal_day, 'manual', '0', entry_method='manually_reported', device='Desk')
        self.activity(self.owner, equal_day, 'csv:oura', '0', entry_method='imported', device='CSV')
        equal = self.client.get(f'/?day={equal_day.isoformat()}')
        self.assertContains(equal, 'alternative-list')
        self.assertContains(equal, 'personal · 0')
        self.assertNotContains(equal, 'Showing 8 of')
        self.assertNotContains(equal, 'aria-label="Steps"')
        css = Path('tracking/static/tracking/app.css').read_text()
        self.assertIn('.calorie-hero .alternative-list,.metric-chip .alternative-list{min-width:0;max-width:100%;margin:8px 0 0;padding:0 0 0 1.1rem;overflow-wrap:anywhere}', css)
        self.assertIn('.calorie-hero .alternative-list a,.metric-chip .alternative-list a{min-width:0;overflow-wrap:anywhere}', css)
