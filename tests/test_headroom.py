"""Your Headroom displays Daily State. Synthetic records only."""
from datetime import timedelta
from uuid import uuid4
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from tracking.headroom import headroom
from tracking.journal import save_journal
from tracking.models import DietEntry, NutritionTargets, SummaryRecord


class HeadroomTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(settings.OWNER_USERNAME)
        self.today = timezone.localdate()
        self.client.force_login(self.owner)

    def rate(self, metric, rating, day=None, synthetic=True):
        day = day or self.today
        domain = {'energy': 19, 'mood': 13, 'focus': 14}[metric]
        save_journal(self.owner, f'Synthetic {metric} note.', day.isoformat(), str(uuid4()), {
            'domain_id': domain, 'metric_key': metric, 'value_state': 'observed', 'rating': rating,
        }, synthetic=synthetic)

    def test_blank_day_does_not_invent_a_low_score(self):
        card = headroom(self.owner, self.today)
        self.assertIsNone(card['score'])
        self.assertEqual(card['status'], 'unknown')
        self.assertEqual(card['status_label'], 'Not enough to score')
        self.assertEqual(card['action']['label'], 'Add mood, energy, or focus')
        self.assertIsNone(card['change'])
        self.assertIn('anger', card['uncollected'].lower())
        self.assertNotIn('Short sleep', card['summary'])
        page = self.client.get('/')
        self.assertContains(page, 'Headspace')
        self.assertNotContains(page, 'Your Headroom')
        self.assertContains(page, 'Not enough to score')
        self.assertNotContains(page, 'Running low')
        self.assertContains(page, 'goal-bar capacity is-empty')
        self.assertContains(page, 'aria-label="Headspace Daily State"')
        self.assertContains(page, 'aria-valuetext="Not enough to score"')
        self.assertNotContains(page, 'aria-valuenow=')
        self.assertNotContains(page, 'style="width:')
        self.assertNotContains(page, 'class="w-')

    def test_two_ratings_match_daily_state_and_ignore_synthetic_on_the_personal_page(self):
        self.rate('energy', 6)
        self.rate('focus', 8)
        card = headroom(self.owner, self.today, include_synthetic=True)
        self.assertEqual(card['score'], '70.00')
        self.assertEqual(card['formula'], 'daily-state-1')
        self.assertEqual(card['status_label'], 'Steady')
        self.assertEqual(card['action']['label'], 'Nothing to change from what is on file')
        self.assertIsNone(headroom(self.owner, self.today)['score'])
        hidden = self.client.get('/')
        self.assertNotContains(hidden, '70.00')
        shown = self.client.get('/?synthetic=1')
        self.assertContains(shown, '70.00')
        self.assertContains(shown, 'Steady')
        self.assertContains(shown, 'aria-label="Headspace Daily State"')
        self.assertContains(shown, 'aria-valuenow="70"')
        self.assertContains(shown, 'class="w-70"')
        self.assertNotContains(shown, 'aria-valuetext="Not enough to score"')
        self.assertNotContains(shown, 'style="width:')
        self.assertNotContains(shown, 'goal-bar capacity is-empty')

    def test_one_rating_stays_blank_even_when_the_number_is_low(self):
        self.rate('mood', 2)
        card = headroom(self.owner, self.today, include_synthetic=True)
        self.assertIsNone(card['score'])
        self.assertNotEqual(card['status'], 'running_low')

    def test_short_sleep_explains_without_changing_the_score(self):
        self.rate('mood', 8)
        self.rate('energy', 8)
        SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=self.today, source_timezone='America/Chicago',
            source_system='oura', source_record_id='sleep-short', completeness='partial',
            values={'sleep_minutes': '300'}, synthetic=True)
        card = headroom(self.owner, self.today, include_synthetic=True)
        self.assertEqual(card['score'], '80.00')
        self.assertEqual(card['status_label'], 'Steady')
        self.assertEqual(card['action']['label'], 'Rest')
        self.assertIn('Pause a demanding task', [item['label'] for item in card['alternatives']])
        self.assertIn('oura is 5 hours', card['summary'])
        self.assertNotIn('6.5', card['summary'])
        self.assertNotIn('manual is 8', card['summary'])

    def test_short_and_long_sleep_stay_unselected(self):
        self.rate('mood', 8)
        self.rate('energy', 8)
        SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=self.today, source_timezone='America/Chicago',
            source_system='manual', source_record_id='sleep-long', completeness='partial',
            values={'sleep_minutes': '480'}, synthetic=True)
        SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=self.today, source_timezone='America/Chicago',
            source_system='oura', source_record_id='sleep-short', completeness='partial',
            values={'sleep_minutes': '300'}, synthetic=True)
        card = headroom(self.owner, self.today, include_synthetic=True)
        self.assertEqual(card['score'], '80.00')
        self.assertNotIn('short sleep', card['summary'].lower())
        self.assertIn('More than one record. This number stays unknown.', card['limitations'])
        self.assertNotIn('oura is 5 hours', card['summary'].lower())

    def test_low_score_names_a_missing_meal_and_a_real_change(self):
        yesterday = self.today - timedelta(days=1)
        self.rate('mood', 8, yesterday)
        self.rate('energy', 8, yesterday)
        headroom(self.owner, yesterday, include_synthetic=True)
        self.rate('mood', 2, self.today)
        self.rate('energy', 3, self.today)
        SummaryRecord.objects.create(
            owner=self.owner, kind='recovery', local_date=self.today, source_timezone='America/Chicago',
            source_system='manual', source_record_id='sleep-low-day', completeness='partial',
            values={'sleep_minutes': '240'}, synthetic=True)
        card = headroom(self.owner, self.today, include_synthetic=True)
        self.assertEqual(card['score'], '25.00')
        self.assertEqual(card['status_label'], 'Running low')
        self.assertEqual(card['action']['label'], 'Get something to eat')
        self.assertIn('/diary/', card['action']['href'])
        self.assertIn('no meal is logged', card['summary'])
        self.assertIn('short sleep', card['summary'].lower())
        self.assertIn('mood is 2 out of 10', card['summary'])
        self.assertTrue(card['change'].startswith('Down from 80.00'))
        self.assertEqual([item['label'] for item in card['alternatives']], ['Rest', 'Take a short break'])
        self.assertNotIn('stress', card['summary'].lower())
        page = self.client.get('/?synthetic=1')
        self.assertContains(page, 'Running low')
        self.assertContains(page, 'Get something to eat')

    def test_food_under_half_the_goal_is_the_action_and_a_small_move_is_not_a_drop(self):
        NutritionTargets.objects.create(owner=self.owner, values={'calories': '2000', 'steps': '10000'})
        DietEntry.objects.create(
            owner=self.owner, local_date=self.today, meal='lunch', description='Synthetic bowl',
            calories='400', synthetic=True)
        SummaryRecord.objects.create(
            owner=self.owner, kind='activity', local_date=self.today, source_timezone='America/Chicago',
            source_system='manual', source_record_id='steps-low', completeness='partial',
            values={'steps': '1000'}, synthetic=True)
        yesterday = self.today - timedelta(days=1)
        self.rate('mood', 7, yesterday)
        self.rate('energy', 7, yesterday)
        headroom(self.owner, yesterday, include_synthetic=True)
        self.rate('mood', 7)
        self.rate('energy', 7)
        card = headroom(self.owner, self.today, include_synthetic=True)
        self.assertEqual(card['score'], '70.00')
        self.assertEqual(card['status_label'], 'Steady')
        self.assertEqual(card['action']['label'], 'Get something to eat')
        self.assertIn('food is under half the calorie goal', card['summary'].lower())
        self.assertIn('steps from manual are under half the goal', [item.lower() for item in card['factors']])
        self.assertIn('Take a short walk', [item['label'] for item in card['alternatives']])
        self.assertTrue(card['change'].startswith('About the same'))

    def test_missing_sleep_is_not_called_short(self):
        self.rate('mood', 4)
        self.rate('focus', 4)
        card = headroom(self.owner, self.today, include_synthetic=True)
        self.assertEqual(card['score'], '40.00')
        self.assertEqual(card['status_label'], 'Stretched')
        self.assertEqual(card['action']['label'], 'Get something to eat')
        self.assertIn('sleep', card['missing'])
        self.assertNotIn('short sleep', card['summary'].lower())
        self.assertIn('no meal is logged', card['summary'].lower())

    def test_running_low_can_offer_a_person_without_claiming_stress(self):
        self.rate('mood', 2)
        self.rate('focus', 2)
        card = headroom(self.owner, self.today, include_synthetic=True)
        self.assertEqual(card['score'], '20.00')
        self.assertEqual(card['status_label'], 'Running low')
        self.assertEqual(
            [item['label'] for item in card['alternatives']],
            ['Take a short break', 'Reach out to someone'])
        self.assertNotIn('stress', card['summary'].lower())
        self.assertNotIn('lonely', card['summary'].lower())
