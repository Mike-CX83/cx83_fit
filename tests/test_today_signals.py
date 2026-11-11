"""Today check-in line, meal saves, and the watch-signal read."""
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from tracking.journal import save_journal
from tracking.meals import save_meal
from tracking.models import DietEntry, NutritionTargets, SummaryRecord
from tracking.today import day_metrics
from tracking.watch import watch_signals


class TodaySignalTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(settings.OWNER_USERNAME)
        self.day = timezone.localdate()

    def test_checkin_line_and_watch_keep_missing_facts_unknown(self):
        metrics = day_metrics(self.owner, self.day)
        self.assertFalse(metrics['checkin'])
        signals = watch_signals(self.owner, self.day)
        self.assertEqual(signals['recovery'], [])
        self.assertEqual(signals['activity'], [])
        self.assertIsNone(signals['weight'])
        self.assertFalse(signals['food']['calories_known'])
        self.assertFalse(signals['checkin'])
        self.assertFalse(signals['sobriety']['known'])
        save_journal(self.owner, 'Synthetic check-in.', self.day.isoformat(), str(uuid4()), {
            'domain_id': 12, 'metric_key': 'explicit_choice', 'value_state': 'observed', 'boolean': False,
        }, synthetic=True)
        personal = watch_signals(self.owner, self.day)
        self.assertFalse(personal['checkin'])
        self.assertFalse(personal['sobriety']['known'])
        included = watch_signals(self.owner, self.day, include_synthetic=True)
        self.assertTrue(included['checkin'])
        self.assertEqual(included['sobriety']['observations'][0]['value_json'], {'boolean': False})
        self.assertTrue(day_metrics(self.owner, self.day, include_synthetic=True)['checkin'])

    def test_today_bars_use_stylesheet_widths(self):
        NutritionTargets.objects.create(owner=self.owner, values={
            'calories': '2000', 'protein': '100', 'fiber': '30', 'steps': '10000'})
        self.client.force_login(self.owner)
        unknown = self.client.get('/?synthetic=1')
        self.assertContains(unknown, 'Not logged')
        self.assertContains(unknown, 'goal-bar capacity is-empty')
        self.assertNotContains(unknown, 'class="w-')
        self.assertNotContains(unknown, 'style="width:')
        meal = DietEntry.objects.create(
            owner=self.owner, local_date=self.day, meal='breakfast', description='Synthetic meal',
            calories=0, protein_g=25, fiber_g=15, synthetic=True)
        SummaryRecord.objects.create(
            owner=self.owner, kind='activity', local_date=self.day, source_timezone='America/Chicago',
            source_system='manual', source_record_id='steps-zero', completeness='complete',
            values={'steps': 0}, synthetic=True)
        zero = self.client.get('/?synthetic=1')
        self.assertContains(zero, 'aria-label="Calories"')
        self.assertContains(zero, 'aria-label="Protein"')
        self.assertContains(zero, 'aria-label="Fiber"')
        self.assertContains(zero, 'aria-label="Steps"')
        self.assertContains(zero, 'class="w-0"')
        self.assertContains(zero, 'class="w-25"')
        self.assertContains(zero, 'class="w-50"')
        self.assertContains(zero, 'aria-valuenow="0"')
        self.assertContains(zero, '2000 left')
        self.assertContains(zero, 'goal-bar capacity is-empty')
        self.assertContains(zero, 'aria-valuetext="Not enough to score"')
        self.assertNotContains(zero, 'style="width:')
        self.assert_named_progressbars(zero.content.decode())
        meal.calories = 1000
        meal.save(update_fields=['calories'])
        partial = self.client.get('/?synthetic=1')
        self.assertContains(partial, 'class="w-50"')
        self.assertContains(partial, '1000 left')
        self.assertNotContains(partial, 'style="width:')
        meal.calories = 2000
        meal.save(update_fields=['calories'])
        full = self.client.get('/?synthetic=1')
        self.assertContains(full, 'class="w-100"')
        self.assertContains(full, '0 left')
        self.assertNotContains(full, ' over')
        self.assertNotContains(full, 'style="width:')
        meal.calories = 3000
        meal.save(update_fields=['calories'])
        over = self.client.get('/?synthetic=1')
        self.assertContains(over, 'class="w-100"')
        self.assertContains(over, '1000 over')
        self.assertNotContains(over, 'w-150')
        self.assertNotContains(over, 'style="width:')
        self.assert_named_progressbars(over.content.decode())

    def test_chip_fill_keeps_a_positive_height(self):
        css = Path(settings.BASE_DIR, 'tracking/static/tracking/app.css').read_text()
        self.assertIn(
            '.metric-chip .goal-bar.thin{box-sizing:border-box;height:14px;padding-top:10px}', css)
        self.assertIn('.metric-chip .goal-bar.thin>span{height:4px}', css)
        self.assertNotIn('.metric-chip .goal-bar{height:4px;padding-top:10px}', css)

    def assert_named_progressbars(self, html):
        bars = []
        for opening in html.split('role="progressbar"')[1:]:
            tag = opening.split('>', 1)[0]
            self.assertIn('aria-label="', tag)
            label = tag.split('aria-label="', 1)[1].split('"', 1)[0]
            self.assertTrue(label.strip())
            bars.append(label)
        self.assertGreaterEqual(len(bars), 1)

    def test_meal_save_retries_the_same_request(self):
        request_id = str(uuid4())
        first = save_meal(self.owner, self.day, 'lunch', 'Synthetic bowl', calories='400', protein_g='30',
                          source_system='mcp', source_record_id=request_id, synthetic=True)
        second = save_meal(self.owner, self.day, 'lunch', 'Synthetic bowl updated', calories='420',
                           source_system='mcp', source_record_id=request_id, synthetic=True)
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(DietEntry.objects.count(), 1)
        self.assertEqual(DietEntry.objects.get().description, 'Synthetic bowl updated')
        self.assertEqual(DietEntry.objects.get().calories, 420)
