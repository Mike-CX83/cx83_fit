"""Synthetic 90 day plan, diary push, goals, and trends. No personal records."""
import json
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.utils import timezone
from tracking.diary_push import parse_diary_push, store_diary_push
from tracking.models import ClinicalItem, DietEntry, Measurement, NutritionTargets, OuraConnection, OuraRecord, SummaryRecord
from tracking.plan import fitness_plan
from tracking.services import put_measurement


class PlanTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(settings.OWNER_USERNAME)
        self.today = timezone.localdate()

    def test_common_meals_goals_and_weight_trend(self):
        NutritionTargets.objects.create(owner=self.owner, values={'protein': '180', 'steps': '12000', 'calories': None})
        for offset, name in ((2, 'Eggs and toast'), (1, 'eggs   and toast'), (0, 'Soup')):
            DietEntry.objects.create(owner=self.owner, local_date=self.today - timedelta(days=offset),
                                     meal='breakfast', description=name)
        put_measurement(self.owner, {'metric': 'weight', 'value': '80', 'unit': 'kg',
            'local_date': str(self.today - timedelta(days=10)), 'synthetic': False}, '11111111-1111-1111-1111-111111111111')
        put_measurement(self.owner, {'metric': 'weight', 'value': '79', 'unit': 'kg',
            'local_date': str(self.today), 'synthetic': False}, '22222222-2222-2222-2222-222222222222')
        plan = fitness_plan(self.owner, self.today)
        self.assertEqual(plan['common_meals'][0]['description'], 'eggs and toast')
        self.assertEqual(plan['common_meals'][0]['times'], 2)
        self.assertEqual(plan['goals'][0]['label'], 'Protein')
        weight = next(line for line in plan['trends'] if line['title'] == 'Weight')
        self.assertEqual(weight['series'][0]['change'], '-1.000')
        self.assertIn('metric=measurements:weight', weight['href'])

    def test_myfitnesspal_push_updates_the_same_meal(self):
        line = f'{self.today.isoformat()} lunch chicken bowl | 600 | 45 | 8'
        first = parse_diary_push(line, self.today)
        store_diary_push(self.owner, first)
        second = parse_diary_push(line.replace('600', '610'), self.today)
        store_diary_push(self.owner, second)
        self.assertEqual(DietEntry.objects.count(), 1)
        self.assertEqual(DietEntry.objects.get().calories, 610)
        self.assertEqual(DietEntry.objects.get().source_system, 'myfitnesspal')
        with self.assertRaises(ValueError):
            parse_diary_push(f'{(self.today - timedelta(days=90)).isoformat()} lunch old meal', self.today)

    def test_device_burn_stays_separate_from_food(self):
        connection = OuraConnection.objects.create(owner=self.owner, account_key='synthetic-ring', synthetic=False)
        OuraRecord.objects.create(connection=connection, collection='daily_activity', identity_key='a'*64,
            source_record_id='activity-1', identity_kind='provider_id',
            raw_json=json.dumps({'day': self.today.isoformat(), 'steps': 14000, 'active_calories': 700, 'total_calories': 2800}))
        SummaryRecord.objects.create(owner=self.owner, kind='nutrition', local_date=self.today,
            source_timezone='America/Chicago', source_system='manual', source_record_id='food-1',
            completeness='partial', values={'calories': '2400', 'protein': '190', 'total_carbohydrates': None, 'fat': None, 'fiber': '30'})
        plan = fitness_plan(self.owner, self.today)
        self.assertFalse(plan['projection']['writes'])
        self.assertEqual(plan['projection']['status'], 'unavailable')
        self.assertEqual(plan['analysis']['active_calories'], [])
        self.assertEqual(plan['analysis']['calories'][0]['source'], 'manual')
        self.assertEqual(SummaryRecord.objects.filter(source_system='oura').count(), 0)

    def test_current_lab_remains_outside_the_window(self):
        ClinicalItem.objects.create(owner=self.owner, kind='lab', name='Synthetic panel', detail='recorded',
                                    recorded_on=self.today - timedelta(days=200))
        plan = fitness_plan(self.owner, self.today)
        self.assertEqual(plan['clinical']['labs'][0]['name'], 'Synthetic panel')
        self.client.force_login(self.owner)
        response = self.client.get('/plan/')
        self.assertContains(response, 'Most common meals')
        self.assertContains(response, 'metric=measurements:weight')
        self.assertNotContains(response, 'Paste from MyFitnessPal')
        diary = self.client.get('/diary/')
        self.assertContains(diary, 'Paste from MyFitnessPal')
        self.assertContains(diary, 'Add meal')

    def test_plan_coverage_bars_use_stylesheet_widths(self):
        self.client.force_login(self.owner)
        empty = self.client.get('/plan/')
        self.assertContains(empty, 'No steps.')
        self.assertNotContains(empty, 'style="width:')
        self.assertNotContains(empty, 'class="w-')
        for offset in range(45):
            day = self.today - timedelta(days=offset)
            SummaryRecord.objects.create(
                owner=self.owner, kind='activity', local_date=day, source_timezone='America/Chicago',
                source_system='manual', source_record_id=f'activity-{offset}', completeness='complete',
                values={'steps': 1000, 'workout_minutes': 30, 'active_calories': 400, 'total_calories': 2200})
            SummaryRecord.objects.create(
                owner=self.owner, kind='recovery', local_date=day, source_timezone='America/Chicago',
                source_system='manual', source_record_id=f'recovery-{offset}', completeness='complete',
                values={'sleep_minutes': 450})
            SummaryRecord.objects.create(
                owner=self.owner, kind='nutrition', local_date=day, source_timezone='America/Chicago',
                source_system='manual', source_record_id=f'nutrition-{offset}', completeness='complete',
                values={'calories': 2000, 'protein': 180})
        partial = self.client.get('/plan/')
        self.assertContains(partial, 'class="w-50"')
        self.assertContains(partial, '45 of 90 days')
        for label in (
            'Steps, manual, 45 of 90 days', 'Sleep, manual, 45 of 90 days',
            'Workouts, manual, 45 of 90 days', 'Active burn, manual, 45 of 90 days',
            'Total burn, manual, 45 of 90 days', 'Food calories, manual, 45 of 90 days',
            'Protein, manual, 45 of 90 days',
        ):
            self.assertContains(partial, f'aria-label="{label}"')
        self.assertEqual(partial.content.decode().count('role="progressbar"'), 7)
        self.assertNotContains(partial, 'style="width:')
        for offset in range(45, 90):
            SummaryRecord.objects.create(
                owner=self.owner, kind='activity', local_date=self.today - timedelta(days=offset),
                source_timezone='America/Chicago', source_system='manual',
                source_record_id=f'steps-{offset}', completeness='complete', values={'steps': 1000})
        full = self.client.get('/plan/')
        self.assertContains(full, 'class="w-100"')
        self.assertContains(full, '90 of 90 days')
        self.assertNotContains(full, 'style="width:')
        plan = fitness_plan(self.owner, self.today)
        plan['analysis']['steps'][0]['observed_days'] = 120
        request = RequestFactory().get('/plan/')
        request.user = self.owner
        request.resolver_match = type('Match', (), {'url_name': 'plan'})()
        rendered = render_to_string('tracking/plan.html', {'plan': plan}, request=request)
        self.assertIn('class="w-100"', rendered)
        self.assertIn('aria-label="Steps, manual, 120 of 90 days"', rendered)
        self.assertIn('120 of 90 days', rendered)
        self.assertNotIn('style="width:', rendered)
        self.assertNotIn('w-133', rendered)
        self.assertNotIn('w-120', rendered)
        for opening in rendered.split('role="progressbar"')[1:]:
            tag = opening.split('>', 1)[0]
            label = tag.split('aria-label="', 1)[1].split('"', 1)[0]
            self.assertTrue(label.strip())
