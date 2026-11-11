"""Local H0 identity foundation. Fabricated rows and disposable databases only."""
import copy
import hashlib
import json
import os
import sqlite3
import subprocess
import textwrap
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.models.query import QuerySet
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from scripts.backup import snapshot, verify_restore
from tracking.models import OuraConnection, OuraRecord, SummaryCorrection, SummaryRecord, WriteRequest
from tracking.plan import fitness_plan, plan_window
from tracking.projection_identity import (
    _metadata_shape, account_relationship, identity_inventory, legacy_candidate,
    provenance_status, refresh_stored_sources, stable_source_id,
)
from tracking.summaries import delete_summary


class ProjectionIdentityTests(TransactionTestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(settings.OWNER_USERNAME)
        self.today = timezone.localdate()

    def connect(self, owner, key, synthetic=False):
        return OuraConnection.objects.create(
            owner=owner, account_key=key, source_account_id=key, synthetic=synthetic, state='disconnected')

    def store(self, connection, collection, source, day, payload):
        OuraRecord.objects.create(
            connection=connection, collection=collection, identity_key=hashlib.sha256(source.encode()).hexdigest(),
            source_record_id=source, identity_kind='provider_id',
            raw_json=json.dumps({'day': day.isoformat(), **payload}))

    def test_read_does_not_write_and_sqlite_does_not_pretend_to_lock(self):
        ring = self.connect(self.owner, 'fabricated-read')
        self.store(ring, 'daily_activity', 'fabricated-read-activity', self.today, {
            'steps': 1000, 'active_calories': 10, 'total_calories': 20})
        with CaptureQueriesContext(connection) as captured:
            plan = fitness_plan(self.owner, self.today)
        self.assertFalse(plan['projection']['writes'])
        self.assertEqual(plan['projection']['status'], 'unavailable')
        self.assertFalse(any(item['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for item in captured))
        self.assertEqual(SummaryRecord.objects.count(), 0)
        self.assertEqual(settings.DATABASES['default']['OPTIONS']['transaction_mode'], 'IMMEDIATE')
        source = Path(settings.BASE_DIR, 'tracking/projection_identity.py').read_text()
        self.assertNotIn('select_for_update', source)
        self.assertNotEqual(Path(settings.DATABASES['default']['NAME']).resolve(), Path(settings.BASE_DIR, 'private/dashboard.sqlite3'))

    def test_accounts_classes_and_order_stay_separate(self):
        other = get_user_model().objects.create_user('synthetic-other-owner')
        expected = []
        for label, keys in (('forward', ('alpha', 'beta')), ('reverse', ('beta', 'alpha'))):
            owner = self.owner if label == 'forward' else other
            for key in keys:
                ring = self.connect(owner, key, synthetic=key == 'beta')
                self.store(ring, 'daily_activity', f'{label}-{key}', self.today, {
                    'steps': 1000 if key == 'alpha' else 2000, 'active_calories': 1, 'total_calories': 2})
            refresh_stored_sources(owner, self.today)
            found = {
                (row.connection.account_key, row.synthetic): row.values['steps']
                for row in SummaryRecord.objects.filter(owner=owner, entry_method='derived')
            }
            expected.append(found)
        self.assertEqual(expected[0], {('alpha', False): '1000', ('beta', True): '2000'})
        self.assertEqual(expected[0], expected[1])
        self.assertEqual(SummaryRecord.objects.filter(owner=self.owner, entry_method='derived').count(), 2)
        plan = fitness_plan(self.owner, self.today, include_synthetic=True)
        self.assertEqual(plan['analysis']['steps'], [])

    def test_zero_unknown_timezone_and_malformed_inputs(self):
        ring = self.connect(self.owner, 'fabricated-zero')
        self.store(ring, 'daily_activity', 'fabricated-zero-steps', self.today, {
            'steps': 0, 'active_calories': None, 'total_calories': None})
        refresh_stored_sources(self.owner, self.today)
        row = SummaryRecord.objects.get(entry_method='derived')
        self.assertEqual(row.values['steps'], '0')
        self.assertIsNone(row.values['active_calories'])
        self.assertEqual(row.source_timezone, '')
        self.assertEqual(row.derivation['timezone_status'], 'unknown')
        self.assertEqual(row.version, 1)
        stamp = row.updated_at
        refresh_stored_sources(self.owner, self.today)
        row.refresh_from_db()
        self.assertEqual(row.version, 1)
        self.assertEqual(row.updated_at, stamp)
        self.assertEqual(WriteRequest.objects.filter(owner=self.owner).count(), 1)
        self.store(ring, 'daily_activity', 'fabricated-bool', self.today - timedelta(days=1), {
            'steps': True, 'active_calories': 1, 'total_calories': 1})
        OuraRecord.objects.filter(source_record_id='fabricated-bool').update(
            raw_json=json.dumps({'day': (self.today - timedelta(days=1)).isoformat(), 'steps': True, 'active_calories': 1, 'total_calories': 1}))
        refresh_stored_sources(self.owner, self.today)
        self.assertFalse(SummaryRecord.objects.filter(local_date=self.today - timedelta(days=1)).exists())
        start, _ = plan_window(self.today)
        self.store(ring, 'daily_activity', 'fabricated-edge', start, {'steps': 3, 'active_calories': 1, 'total_calories': 1})
        self.store(ring, 'daily_activity', 'fabricated-outside', start - timedelta(days=1), {'steps': 4, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        self.assertTrue(SummaryRecord.objects.filter(local_date=start, entry_method='derived').exists())
        self.assertFalse(SummaryRecord.objects.filter(local_date=start - timedelta(days=1)).exists())

    def test_conflicts_do_not_pick_a_winner_or_sum(self):
        ring = self.connect(self.owner, 'fabricated-conflict')
        self.store(ring, 'daily_activity', 'fabricated-a', self.today, {'steps': 10, 'active_calories': 1, 'total_calories': 1})
        self.store(ring, 'daily_activity', 'fabricated-b', self.today, {'steps': 20, 'active_calories': 1, 'total_calories': 1})
        self.store(ring, 'sleep', 'fabricated-sleep-a', self.today, {'total_sleep_duration': 3600})
        self.store(ring, 'sleep', 'fabricated-sleep-b', self.today, {'total_sleep_duration': 7200})
        results = refresh_stored_sources(self.owner, self.today)
        self.assertIn('multiple_activity', [item['reason'] for item in results])
        self.assertIn('overlapping_sleep', [item['reason'] for item in results])
        self.assertEqual(SummaryRecord.objects.filter(entry_method='derived').count(), 0)

    def test_legacy_and_derived_tombstones_block_later_identities(self):
        first = self.connect(self.owner, 'fabricated-legacy-a')
        second = self.connect(self.owner, 'fabricated-legacy-b', synthetic=True)
        legacy = SummaryRecord.objects.create(
            owner=self.owner, kind='activity', local_date=self.today, source_timezone='America/Chicago',
            source_system='oura', source_record_id='fabricated-legacy', entry_method='imported',
            device='Oura', completeness='partial', synthetic=False,
            values={'steps': '5', 'workout_minutes': None, 'active_calories': None, 'total_calories': None, 'workout_summary': ''})
        delete_summary(self.owner, str(legacy.id), legacy.version, str(uuid4()))
        self.store(first, 'daily_activity', 'fabricated-after-legacy', self.today, {'steps': 8, 'active_calories': 1, 'total_calories': 1})
        self.store(second, 'daily_activity', 'fabricated-after-legacy-test', self.today, {'steps': 9, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        self.assertEqual(SummaryRecord.objects.filter(entry_method='derived').count(), 0)
        self.assertTrue(legacy_candidate(SummaryRecord.objects.get(pk=legacy.id)) is False or SummaryRecord.objects.get(pk=legacy.id).deleted_at)
        kept = SummaryRecord.objects.get(pk=legacy.id)
        self.assertIsNotNone(kept.deleted_at)
        self.assertEqual(kept.values['steps'], '5')

    def test_derived_deletion_keeps_lineage_across_a_moved_day(self):
        ring = self.connect(self.owner, 'fabricated-move')
        self.store(ring, 'daily_activity', 'fabricated-move-raw', self.today, {'steps': 15, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        row = SummaryRecord.objects.get(entry_method='derived')
        raw_id = str(OuraRecord.objects.get().id)
        self.assertIn(raw_id, [item.get('raw_id') for item in row.derivation['contributor_identities_ever']])
        delete_summary(self.owner, str(row.id), row.version, str(uuid4()))
        raw = OuraRecord.objects.get()
        payload = json.loads(raw.raw_json)
        payload['day'] = (self.today - timedelta(days=1)).isoformat()
        payload['steps'] = 16
        raw.raw_json = json.dumps(payload)
        raw.save(update_fields=['raw_json'])
        refresh_stored_sources(self.owner, self.today)
        self.assertEqual(SummaryRecord.objects.filter(entry_method='derived').count(), 1)
        row.refresh_from_db()
        self.assertIsNotNone(row.deleted_at)
        self.assertEqual(row.values['steps'], '15')
        self.assertEqual(row.version, 2)

    def test_source_collision_and_invalid_shape_are_rejected(self):
        ring = self.connect(self.owner, 'fabricated-collision')
        stable = stable_source_id(ring, 'activity', self.today)
        original = SummaryRecord.objects.create(
            owner=self.owner, kind='activity', local_date=self.today, source_timezone='America/Chicago',
            source_system='oura', source_record_id=stable, entry_method='manually_reported',
            device='Notebook', completeness='partial', synthetic=False,
            values={'steps': '4', 'workout_minutes': None, 'active_calories': None, 'total_calories': None, 'workout_summary': ''})
        before = (original.version, original.values, original.updated_at, original.entry_method)
        self.store(ring, 'daily_activity', 'fabricated-collision-raw', self.today, {'steps': 40, 'active_calories': 1, 'total_calories': 1})
        result = refresh_stored_sources(self.owner, self.today)
        self.assertIn('source_key_collision', [item['reason'] for item in result])
        original.refresh_from_db()
        self.assertEqual((original.version, original.values, original.updated_at, original.entry_method), before)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SummaryRecord.objects.create(
                    owner=self.owner, kind='activity', local_date=self.today - timedelta(days=1), source_timezone='',
                    source_system='oura', source_record_id='derived:oura:invalid', entry_method='derived',
                    device='Oura', completeness='partial', synthetic=False, values={'steps': '1'},
                    connection=None, derivation=None)

    def test_stale_refresh_loses_the_compare_and_swap_without_reinserting(self):
        ring = self.connect(self.owner, 'fabricated-cas')
        self.store(ring, 'daily_activity', 'fabricated-cas-raw', self.today, {'steps': 30, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        row = SummaryRecord.objects.get(entry_method='derived')
        raw = OuraRecord.objects.get()
        payload = json.loads(raw.raw_json)
        payload['steps'] = 31
        raw.raw_json = json.dumps(payload)
        raw.save(update_fields=['raw_json'])
        real_update = QuerySet.update

        def intercepted(queryset, **kwargs):
            if queryset.model is SummaryRecord and 'deleted_at' not in kwargs and row.deleted_at is None:
                current = SummaryRecord.objects.get(pk=row.pk)
                delete_summary(self.owner, str(current.pk), current.version, str(uuid4()))
            return real_update(queryset, **kwargs)

        with patch.object(QuerySet, 'update', intercepted):
            refresh_stored_sources(self.owner, self.today)
        self.assertEqual(SummaryRecord.objects.filter(entry_method='derived').count(), 1)
        row.refresh_from_db()
        self.assertIsNotNone(row.deleted_at)
        self.assertEqual(row.values['steps'], '30')
        self.assertEqual(row.version, 2)

    def test_recipe_revision_keeps_identity_and_equal_refresh_does_not_churn(self):
        ring = self.connect(self.owner, 'fabricated-recipe')
        self.store(ring, 'daily_activity', 'fabricated-recipe-raw', self.today, {'steps': 12, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        row = SummaryRecord.objects.get(entry_method='derived')
        identity = row.source_record_id
        with patch('tracking.projection_identity.RECIPE_VERSION', 2):
            refresh_stored_sources(self.owner, self.today)
            row.refresh_from_db()
            self.assertEqual(row.source_record_id, identity)
            self.assertEqual(row.version, 2)
            self.assertEqual(row.derivation['recipe_version'], 2)
            self.assertEqual(SummaryCorrection.objects.filter(record=row).count(), 2)
            stamp = row.updated_at
            refresh_stored_sources(self.owner, self.today)
            row.refresh_from_db()
            self.assertEqual(row.version, 2)
            self.assertEqual(row.updated_at, stamp)

    def test_inventory_labels_candidates_without_rewriting_them(self):
        imported = SummaryRecord.objects.create(
            owner=self.owner, kind='activity', local_date=self.today, source_timezone='America/Chicago',
            source_system='oura', source_record_id='fabricated-candidate', entry_method='imported',
            completeness='partial', values={'steps': '1', 'workout_minutes': None, 'active_calories': None, 'total_calories': None, 'workout_summary': ''})
        manual = SummaryRecord.objects.create(
            owner=self.owner, kind='activity', local_date=self.today - timedelta(days=1), source_timezone='America/Chicago',
            source_system='oura', source_record_id='fabricated-manual', entry_method='manually_reported',
            completeness='partial', values={'steps': '2', 'workout_minutes': None, 'active_calories': None, 'total_calories': None, 'workout_summary': ''})
        csv_row = SummaryRecord.objects.create(
            owner=self.owner, kind='activity', local_date=self.today - timedelta(days=2), source_timezone='America/Chicago',
            source_system='csv:oura', source_record_id='fabricated-csv', entry_method='imported',
            completeness='partial', values={'steps': '3', 'workout_minutes': None, 'active_calories': None, 'total_calories': None, 'workout_summary': ''})
        nutrition = SummaryRecord.objects.create(
            owner=self.owner, kind='nutrition', local_date=self.today, source_timezone='America/Chicago',
            source_system='oura', source_record_id='fabricated-nutrition', entry_method='imported',
            completeness='partial', values={'calories': '1', 'protein': None, 'total_carbohydrates': None, 'fat': None, 'fiber': None})
        before = list(SummaryRecord.objects.order_by('id').values_list('id', 'updated_at', 'values', 'entry_method', 'synthetic'))
        report = identity_inventory(self.owner)
        self.assertEqual(report['legacy_unresolved_count'], 1)
        self.assertEqual(list(SummaryRecord.objects.order_by('id').values_list('id', 'updated_at', 'values', 'entry_method', 'synthetic')), before)
        self.assertTrue(legacy_candidate(imported))
        self.assertFalse(legacy_candidate(manual))
        self.assertFalse(legacy_candidate(csv_row))
        self.assertFalse(legacy_candidate(nutrition))
        self.assertEqual(report['originals'][0]['provenance_status'] in ('legacy_unresolved', None), True)

    def metadata(self, ring, status='current'):
        return {
            'schema_version': 2, 'recipe_version': 1, 'account_id': str(ring.id), 'timezone_status': 'unknown',
            'status': status, 'quality': status, 'current_contributors': [], 'contributor_identities_ever': [],
            'conflict_reason': '',
        }

    def test_legacy_source_identity_survives_a_provider_day_change(self):
        ring = self.connect(self.owner, 'fabricated-moved-source')
        legacy = SummaryRecord.objects.create(
            owner=self.owner, kind='activity', local_date=self.today - timedelta(days=1), source_timezone='America/Chicago',
            source_system='oura', source_record_id='fabricated-same-id', entry_method='imported', completeness='partial',
            values={'steps': '100', 'workout_minutes': None, 'active_calories': None, 'total_calories': None, 'workout_summary': ''})
        delete_summary(self.owner, str(legacy.id), legacy.version, str(uuid4()))
        self.store(ring, 'daily_activity', 'fabricated-same-id', self.today, {'steps': 100, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        self.assertFalse(SummaryRecord.objects.filter(entry_method='derived', derivation__status='current').exists())
        prefix = 't' * 120
        SummaryRecord.objects.create(
            owner=self.owner, kind='activity', local_date=self.today - timedelta(days=3), source_timezone='America/Chicago',
            source_system='oura', source_record_id=prefix, entry_method='manually_reported', completeness='partial',
            values={'steps': '1', 'workout_minutes': None, 'active_calories': None, 'total_calories': None, 'workout_summary': ''},
            deleted_at=timezone.now())
        self.store(ring, 'daily_activity', prefix + 'more', self.today - timedelta(days=2), {'steps': 8, 'active_calories': 1, 'total_calories': 1})
        self.store(ring, 'daily_activity', 'fabricated-unrelated', self.today - timedelta(days=4), {'steps': 3, 'active_calories': 1, 'total_calories': 1})
        csv_row = SummaryRecord.objects.create(
            owner=self.owner, kind='activity', local_date=self.today - timedelta(days=4), source_timezone='America/Chicago',
            source_system='csv:oura', source_record_id='fabricated-unrelated', entry_method='imported', completeness='partial',
            values={'steps': '9', 'workout_minutes': None, 'active_calories': None, 'total_calories': None, 'workout_summary': ''},
            deleted_at=timezone.now())
        refresh_stored_sources(self.owner, self.today)
        self.assertFalse(SummaryRecord.objects.filter(entry_method='derived', local_date=self.today - timedelta(days=2)).exists())
        kept = SummaryRecord.objects.get(entry_method='derived', local_date=self.today - timedelta(days=4))
        self.assertEqual(kept.values['steps'], '3')
        self.assertEqual(kept.derivation['status'], 'current')
        csv_row.refresh_from_db()
        self.assertEqual(csv_row.source_system, 'csv:oura')

    def test_deleted_lineage_distinguishes_account_relationships(self):
        first = OuraConnection.objects.create(
            owner=self.owner, account_key='fabricated-original', source_account_id='provider-1', synthetic=False, state='disconnected')
        moved = self.today - timedelta(days=1)
        self.store(first, 'daily_activity', 'same-provider-id', self.today, {'steps': 15, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        original = SummaryRecord.objects.get(entry_method='derived')
        delete_summary(self.owner, str(original.id), original.version, str(uuid4()))
        OuraRecord.objects.filter(connection=first).delete()

        equivalent = OuraConnection.objects.create(
            owner=self.owner, account_key='fabricated-reauthorized', source_account_id='provider-1', synthetic=False, state='disconnected')
        self.assertEqual(account_relationship(first, equivalent), 'equivalent')
        self.store(equivalent, 'daily_activity', 'same-provider-id', moved, {'steps': 99, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        self.assertFalse(SummaryRecord.objects.filter(entry_method='derived', deleted_at__isnull=True).exists())
        OuraRecord.objects.filter(connection=equivalent).delete()

        distinct = OuraConnection.objects.create(
            owner=self.owner, account_key='fabricated-distinct', source_account_id='provider-2', synthetic=False, state='disconnected')
        self.assertEqual(account_relationship(first, distinct), 'distinct')
        self.store(distinct, 'daily_activity', 'same-provider-id', moved, {'steps': 77, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        self.assertEqual(SummaryRecord.objects.get(entry_method='derived', deleted_at__isnull=True).values['steps'], '77')
        SummaryRecord.objects.filter(entry_method='derived', deleted_at__isnull=True).delete()
        OuraRecord.objects.filter(connection=distinct).delete()

        unresolved = OuraConnection.objects.create(
            owner=self.owner, account_key='fabricated-unresolved', source_account_id=None, synthetic=False, state='disconnected')
        self.assertEqual(account_relationship(first, unresolved), 'unresolved')
        self.store(unresolved, 'daily_activity', 'same-provider-id', moved, {'steps': 66, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        self.assertFalse(SummaryRecord.objects.filter(entry_method='derived', deleted_at__isnull=True).exists())

    def test_source_retraction_is_inside_the_write_transaction(self):
        ring = self.connect(self.owner, 'fabricated-race')
        raw = OuraRecord.objects.create(
            connection=ring, collection='daily_activity',
            identity_key=hashlib.sha256(b'fabricated-race-raw').hexdigest(),
            source_record_id='fabricated-race-raw', identity_kind='provider_id',
            raw_json=json.dumps({'day': self.today.isoformat(), 'steps': 100, 'active_calories': 1, 'total_calories': 1}))
        hook = {'hits': 0}

        def retract_before_begin(execute, sql, params, many, context):
            if sql.upper().startswith('BEGIN IMMEDIATE') and not hook['hits']:
                hook['hits'] += 1
                with sqlite3.connect(settings.DATABASES['default']['NAME'], uri=str(settings.DATABASES['default']['NAME']).startswith('file:')) as db:
                    db.execute('DELETE FROM tracking_ourarecord WHERE id=?', (raw.id.hex,))
            return execute(sql, params, many, context)

        with connection.execute_wrapper(retract_before_begin):
            refresh_stored_sources(self.owner, self.today)
        self.assertEqual(hook['hits'], 1)
        self.assertEqual(OuraRecord.objects.count(), 0)
        self.assertFalse(SummaryRecord.objects.filter(derivation__status='current').exists())

        raw = OuraRecord.objects.create(
            connection=ring, collection='daily_activity',
            identity_key=hashlib.sha256(b'fabricated-lock-raw').hexdigest(),
            source_record_id='fabricated-lock-raw', identity_kind='provider_id',
            raw_json=json.dumps({'day': self.today.isoformat(), 'steps': 4, 'active_calories': 1, 'total_calories': 1}))
        held = {'locked': None, 'error': ''}

        def competing_write(execute, sql, params, many, context):
            outcome = execute(sql, params, many, context)
            normalized = ' '.join(sql.split()).upper()
            if held['locked'] is None and normalized.startswith('SELECT') and 'TRACKING_OURARECORD' in normalized:
                try:
                    with sqlite3.connect(settings.DATABASES['default']['NAME'], uri=str(settings.DATABASES['default']['NAME']).startswith('file:'), timeout=0.2) as db:
                        db.execute('BEGIN IMMEDIATE')
                        db.execute('DELETE FROM tracking_ourarecord WHERE id=?', (raw.id.hex,))
                        db.commit()
                    held['locked'] = False
                except sqlite3.OperationalError as exc:
                    held['locked'] = True
                    held['error'] = str(exc)
            return outcome

        with connection.execute_wrapper(competing_write):
            refresh_stored_sources(self.owner, self.today)
        self.assertTrue(held['locked'])
        self.assertIn('locked', held['error'].lower())
        self.assertTrue(SummaryRecord.objects.filter(derivation__status='current').exists())
        with sqlite3.connect(settings.DATABASES['default']['NAME'], uri=str(settings.DATABASES['default']['NAME']).startswith('file:')) as db:
            db.execute('DELETE FROM tracking_ourarecord WHERE id=?', (raw.id.hex,))
        refresh_stored_sources(self.owner, self.today)
        self.assertFalse(SummaryRecord.objects.filter(derivation__status='current').exists())

    def test_invalid_identity_is_not_relabeled_current(self):
        ring = self.connect(self.owner, 'fabricated-invalid')
        other = get_user_model().objects.create_user('synthetic-other')
        unsaved = SummaryRecord(
            owner=other, kind='activity', local_date=self.today, source_timezone='', source_system='oura',
            source_record_id='derived:oura:invalid', entry_method='derived', derivation=['malformed'], synthetic=False)
        self.assertEqual(provenance_status(unsaved), 'invalid')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SummaryRecord.objects.create(
                    owner=self.owner, connection=ring, synthetic=False, kind='activity', local_date=self.today,
                    source_timezone='', source_system='oura', source_record_id=stable_source_id(ring, 'activity', self.today),
                    entry_method='derived', values={'steps': '1'}, derivation=['malformed'])
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SummaryRecord.objects.create(
                    owner=self.owner, connection=ring, synthetic=False, kind='activity', local_date=self.today - timedelta(days=1),
                    source_timezone='', source_system='oura', source_record_id=stable_source_id(ring, 'activity', self.today - timedelta(days=1)),
                    entry_method='derived', values={'steps': '1'}, derivation={'status': 'current'})
        stolen = stable_source_id(ring, 'activity', self.today)
        spoofed = SummaryRecord.objects.create(
            owner=other, connection=ring, synthetic=True, kind='activity', local_date=self.today, source_timezone='',
            source_system='oura', source_record_id=stolen, entry_method='derived', values={'steps': '999'},
            derivation=self.metadata(ring))
        before = (spoofed.version, spoofed.synthetic, spoofed.source_record_id, spoofed.updated_at, spoofed.derivation)
        self.assertEqual(identity_inventory(other)['derived'][0]['status'], 'invalid')
        refresh_stored_sources(other, self.today)
        spoofed.refresh_from_db()
        self.assertEqual((spoofed.version, spoofed.synthetic, spoofed.source_record_id, spoofed.updated_at, spoofed.derivation), before)

    def test_malformed_numbers_and_duplicate_members_do_not_become_current(self):
        ring = self.connect(self.owner, 'fabricated-malformed')
        self.store(ring, 'daily_activity', 'fabricated-valid', self.today, {'steps': 12, 'active_calories': 1, 'total_calories': 1})
        self.store(ring, 'daily_activity', 'fabricated-border', self.today - timedelta(days=1), {
            'steps': 999999999, 'active_calories': 1, 'total_calories': 1})
        huge_day = self.today - timedelta(days=2)
        self.store(ring, 'daily_activity', 'fabricated-huge', huge_day, {'steps': 1, 'active_calories': 1, 'total_calories': 1})
        OuraRecord.objects.filter(source_record_id='fabricated-huge').update(
            raw_json=json.dumps({'day': huge_day.isoformat(), 'steps': 10**40, 'active_calories': 1, 'total_calories': 1}))
        infinity_day = self.today - timedelta(days=3)
        duplicate_day = self.today - timedelta(days=4)
        OuraRecord.objects.create(
            connection=ring, collection='daily_activity', identity_key='c' * 64, source_record_id='fabricated-infinity',
            identity_kind='provider_id', raw_json='{"day":"%s","steps":1e309,"active_calories":1,"total_calories":1}' % infinity_day.isoformat())
        duplicate = OuraRecord.objects.create(
            connection=ring, collection='daily_activity', identity_key='d' * 64, source_record_id='fabricated-duplicate',
            identity_kind='provider_id',
            raw_json='{"day":"%s","steps":5,"active_calories":1,"total_calories":1,"steps":50}' % duplicate_day.isoformat())
        original_text = duplicate.raw_json
        ambiguous = OuraRecord.objects.create(
            connection=ring, collection='daily_activity', identity_key='e' * 64, source_record_id='fabricated-two-days',
            identity_kind='provider_id', raw_json='{"day":"2026-11-10","day":"2026-11-09","steps":4}')
        refresh_stored_sources(self.owner, self.today)
        self.assertEqual(SummaryRecord.objects.get(local_date=self.today, entry_method='derived').values['steps'], '12')
        self.assertEqual(SummaryRecord.objects.get(local_date=self.today - timedelta(days=1), entry_method='derived').values['steps'], '999999999')
        self.assertFalse(SummaryRecord.objects.filter(local_date__in=[huge_day, infinity_day, duplicate_day], entry_method='derived').exists())
        duplicate.refresh_from_db()
        self.assertEqual(duplicate.raw_json, original_text)
        self.assertFalse(SummaryRecord.objects.filter(values__steps='50').exists())
        ambiguous.refresh_from_db()
        self.assertIn('"day":"2026-11-10"', ambiguous.raw_json)
        self.assertIn('"day":"2026-11-09"', ambiguous.raw_json)

    def test_derived_deletion_keeps_class_and_collection(self):
        synthetic = OuraConnection.objects.create(
            owner=self.owner, account_key='fabricated-class', source_account_id='provider-1', synthetic=True, state='disconnected')
        personal = OuraConnection.objects.create(
            owner=self.owner, account_key='fabricated-class', source_account_id='provider-1', synthetic=False, state='disconnected')
        self.assertEqual(account_relationship(synthetic, personal), 'equivalent')
        self.store(synthetic, 'daily_activity', 'same-id', self.today, {'steps': 15, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        deleted = SummaryRecord.objects.get(entry_method='derived')
        delete_summary(self.owner, str(deleted.id), deleted.version, str(uuid4()))
        self.store(personal, 'daily_activity', 'same-id', self.today, {'steps': 21, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        personal_row = SummaryRecord.objects.get(entry_method='derived', synthetic=False, deleted_at__isnull=True)
        self.assertEqual(personal_row.values['steps'], '21')
        self.assertEqual(personal_row.derivation['status'], 'current')
        self.store(personal, 'sleep', 'same-id', self.today, {'total_sleep_duration': 3600})
        delete_summary(self.owner, str(personal_row.id), personal_row.version, str(uuid4()))
        refresh_stored_sources(self.owner, self.today)
        recovery = SummaryRecord.objects.get(entry_method='derived', kind='recovery', deleted_at__isnull=True)
        self.assertEqual(recovery.derivation['status'], 'current')
        self.assertEqual(recovery.values['sleep_minutes'], '60.000')

    def test_nested_metadata_stays_invalid_without_a_rewrite(self):
        ring = self.connect(self.owner, 'fabricated-nested')
        self.store(ring, 'daily_activity', 'fabricated-nested-raw', self.today, {'steps': 6, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        row = SummaryRecord.objects.get(entry_method='derived')
        broken = dict(row.derivation)
        broken['contributor_identities_ever'] = [{'identity_key': []}]
        broken['current_contributors'] = [1]
        broken['schema_version'] = -1
        SummaryRecord.objects.filter(pk=row.pk).update(derivation=broken)
        self.assertEqual(identity_inventory(self.owner)['derived'][0]['status'], 'invalid')
        before = (row.version, row.updated_at, row.synthetic, row.source_record_id)
        refresh_stored_sources(self.owner, self.today)
        row.refresh_from_db()
        self.assertEqual((row.version, row.updated_at, row.synthetic, row.source_record_id), before)
        self.assertEqual(row.derivation['contributor_identities_ever'], [{'identity_key': []}])
        self.assertEqual(provenance_status(row), 'invalid')

    def test_payload_identity_and_oversized_json_do_not_abort_refresh(self):
        ring = self.connect(self.owner, 'fabricated-parser')
        self.store(ring, 'daily_activity', 'same-id', self.today, {'steps': 4, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        self.assertEqual(SummaryRecord.objects.get(derivation__status='current').values['steps'], '4')
        raw = OuraRecord.objects.get(source_record_id='same-id')
        mismatch = json.dumps({'id': 'different', 'day': self.today.isoformat(), 'steps': 1, 'active_calories': 1, 'total_calories': 1})
        raw.raw_json = mismatch
        raw.save(update_fields=['raw_json'])
        refresh_stored_sources(self.owner, self.today)
        raw.refresh_from_db()
        self.assertEqual(raw.raw_json, mismatch)
        self.assertFalse(SummaryRecord.objects.filter(derivation__status='current').exists())
        sibling = self.today - timedelta(days=1)
        self.store(ring, 'daily_activity', 'fabricated-sibling', sibling, {'steps': 8, 'active_calories': 1, 'total_calories': 1})
        huge_day = self.today - timedelta(days=2)
        OuraRecord.objects.create(
            connection=ring, collection='daily_activity', identity_key='f' * 64, source_record_id='fabricated-huge-literal',
            identity_kind='provider_id',
            raw_json='{"day":"%s","steps":%s,"active_calories":1,"total_calories":1}' % (huge_day.isoformat(), '9' * 5000))
        refresh_stored_sources(self.owner, self.today)
        self.assertEqual(SummaryRecord.objects.get(local_date=sibling, entry_method='derived').values['steps'], '8')
        self.assertFalse(SummaryRecord.objects.filter(local_date=huge_day, entry_method='derived').exists())
        self.assertFalse(SummaryRecord.objects.filter(local_date=self.today, derivation__status='current').exists())

    def test_one_field_metadata_stays_invalid_without_a_crash_or_rewrite(self):
        ring = self.connect(self.owner, 'fabricated-one-field')
        self.store(ring, 'daily_activity', 'fabricated-one-field-raw', self.today, {'steps': 9, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        row = SummaryRecord.objects.get(entry_method='derived')
        original = copy.deepcopy(row.derivation)
        scalars = {
            'schema_version': (None, True, False, 0, -1, 2.0, '2', [], {}),
            'recipe_version': (None, True, False, 0, -1, 1.5, '1', [], {}),
            'status': (None, True, 1, 1.5, 'nope', [], {}),
            'quality': (None, True, 'stale', [], {}),
            'timezone_status': (None, True, 'known', [], {}),
            'conflict_reason': (None, 1, [], {}),
            'account_id': (None, True, 'other-account', [], {}),
            'current_contributors': (None, {}, 'x', []),
            'contributor_identities_ever': (None, {}, 'x', []),
        }
        nested_values = (None, True, False, 0, 1.5, '', 'not-valid', [], {})
        mutations = [(name, value) for name, values in scalars.items() for value in values]
        for side in ('current_contributors', 'contributor_identities_ever'):
            for field in ('raw_id', 'identity_key', 'collection', 'source_record_id'):
                mutations.extend(((side, field), value) for value in nested_values)
        mutations.extend((('current_contributors', 'version'), value) for value in (None, True, False, 0, -1, 1.5, '1', [], {}))
        current = copy.deepcopy(original['current_contributors'][0])
        current['extra'] = 'fabricated'
        mutations.append(('current_contributors', [current]))
        missing = copy.deepcopy(original['current_contributors'][0])
        missing.pop('collection')
        mutations.append(('current_contributors', [missing]))
        for change in mutations:
            mutated = copy.deepcopy(original)
            if isinstance(change[0], tuple):
                side, field = change[0]
                mutated[side][0][field] = change[1]
            else:
                mutated[change[0]] = change[1]
            try:
                SummaryRecord.objects.filter(pk=row.pk).update(derivation=mutated)
            except IntegrityError:
                self.assertIs(False, _metadata_shape(mutated, ring, 'activity'))
                continue
            self.assertEqual(identity_inventory(self.owner)['derived'][0]['status'], 'invalid', change)
            before = (row.version, row.updated_at, row.values, mutated)
            refresh_stored_sources(self.owner, self.today)
            row.refresh_from_db()
            self.assertEqual((row.version, row.updated_at, row.values, row.derivation), before)
            SummaryRecord.objects.filter(pk=row.pk).update(derivation=original)

    def test_invalid_tombstone_cannot_waive_deletion(self):
        first = self.connect(self.owner, 'fabricated-tombstone-a')
        second = self.connect(self.owner, 'fabricated-tombstone-b')
        self.store(first, 'daily_activity', 'same-id', self.today, {'steps': 14, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        deleted = SummaryRecord.objects.get(entry_method='derived')
        delete_summary(self.owner, str(deleted.id), deleted.version, str(uuid4()))
        deleted.refresh_from_db()
        incoherent = copy.deepcopy(deleted.derivation)
        incoherent['contributor_identities_ever'] = []
        SummaryRecord.objects.filter(pk=deleted.pk).update(derivation=incoherent)
        self.assertEqual(identity_inventory(self.owner)['derived'][0]['status'], 'invalid')
        raw = OuraRecord.objects.get(connection=first)
        moved = json.loads(raw.raw_json)
        moved['day'] = (self.today - timedelta(days=1)).isoformat()
        raw.raw_json = json.dumps(moved)
        raw.version += 1
        raw.save(update_fields=['raw_json', 'version'])
        before_tomb = list(SummaryRecord.objects.filter(pk=deleted.pk).values())
        before_raw = list(OuraRecord.objects.filter(pk=raw.pk).values())
        refresh_stored_sources(self.owner, self.today)
        self.assertFalse(SummaryRecord.objects.filter(connection=first, deleted_at__isnull=True, derivation__status='current').exists())
        self.assertEqual(list(SummaryRecord.objects.filter(pk=deleted.pk).values()), before_tomb)
        self.assertEqual(list(OuraRecord.objects.filter(pk=raw.pk).values()), before_raw)
        self.store(second, 'daily_activity', 'same-id', self.today, {'steps': 16, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        independent = SummaryRecord.objects.get(connection=second, deleted_at__isnull=True)
        self.assertEqual(independent.derivation['status'], 'current')
        self.assertEqual(independent.values['steps'], '16')
        other = get_user_model().objects.create_user('synthetic-cross-owner')
        foreign = self.connect(other, 'fabricated-foreign-account')
        SummaryRecord.objects.filter(pk=deleted.pk).update(connection=foreign)
        refresh_stored_sources(self.owner, self.today)
        self.assertFalse(SummaryRecord.objects.filter(connection=first, deleted_at__isnull=True, derivation__status='current').exists())

    def test_absent_payload_id_requires_a_coherent_stored_provider_identity(self):
        ring = self.connect(self.owner, 'fabricated-absent-id')
        self.store(ring, 'daily_activity', 'fabricated-coherent', self.today, {'steps': 5, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        self.assertEqual(SummaryRecord.objects.get(derivation__status='current').values['steps'], '5')
        cases = {
            'kind': {'identity_kind': 'content_hash_no_id'},
            'hash': {'identity_key': '0' * 64},
            'source': {'source_record_id': None},
        }
        for offset, (name, changes) in enumerate(cases.items(), start=1):
            day = self.today - timedelta(days=offset)
            self.store(ring, 'daily_activity', f'fabricated-{name}', day, {'steps': 7, 'active_calories': 1, 'total_calories': 1})
            OuraRecord.objects.filter(source_record_id=f'fabricated-{name}').update(**changes)
        refresh_stored_sources(self.owner, self.today)
        self.assertEqual(SummaryRecord.objects.get(derivation__status='current').values['steps'], '5')
        self.assertEqual(SummaryRecord.objects.filter(derivation__status='current').count(), 1)

    def test_zero_version_and_recipe_contradictions_do_not_save_invalid_current(self):
        ring = self.connect(self.owner, 'fabricated-proposal')
        self.store(ring, 'daily_activity', 'fabricated-proposal-raw', self.today, {'steps': 11, 'active_calories': 1, 'total_calories': 1})
        created = OuraRecord.objects.get()
        OuraRecord.objects.filter(pk=created.pk).update(version=0)
        raw_before = created.raw_json
        refresh_stored_sources(self.owner, self.today)
        created.refresh_from_db()
        self.assertEqual(created.raw_json, raw_before)
        self.assertEqual(created.version, 0)
        self.assertFalse(SummaryRecord.objects.exists())
        self.assertFalse(SummaryCorrection.objects.exists())
        OuraRecord.objects.filter(pk=created.pk).update(version=1)
        refresh_stored_sources(self.owner, self.today)
        row = SummaryRecord.objects.get(entry_method='derived')
        self.assertEqual(row.values['steps'], '11')
        ever = copy.deepcopy(row.derivation['contributor_identities_ever'])
        OuraRecord.objects.filter(pk=created.pk).update(version=0)
        refresh_stored_sources(self.owner, self.today)
        row.refresh_from_db()
        self.assertNotEqual(row.derivation['status'], 'current')
        self.assertEqual(row.values['steps'], '11')
        self.assertEqual(row.derivation['contributor_identities_ever'], ever)
        self.assertNotEqual(identity_inventory(self.owner)['derived'][0]['status'], 'invalid')
        created.refresh_from_db()
        self.assertEqual(created.version, 0)
        self.assertEqual(created.raw_json, raw_before)
        collection = copy.deepcopy(row.derivation)
        collection['status'] = 'current'
        collection['quality'] = 'current'
        collection['current_contributors'] = copy.deepcopy(ever)
        collection['current_contributors'][0]['version'] = 1
        collection['current_contributors'][0]['collection'] = 'sleep'
        collection['contributor_identities_ever'][0]['collection'] = 'sleep'
        versions = copy.deepcopy(collection)
        versions['current_contributors'][0]['collection'] = 'daily_activity'
        versions['contributor_identities_ever'][0]['collection'] = 'daily_activity'
        second = copy.deepcopy(versions['current_contributors'][0])
        second['version'] = 2
        versions['current_contributors'].append(second)
        for mutated in (collection, versions):
            SummaryRecord.objects.filter(pk=row.pk).update(derivation=mutated, version=row.version)
            before = (row.version, row.updated_at, mutated)
            self.assertEqual(identity_inventory(self.owner)['derived'][0]['status'], 'invalid')
            refresh_stored_sources(self.owner, self.today)
            row.refresh_from_db()
            self.assertEqual((row.version, row.updated_at, row.derivation), before)

    def _drop_payload_id(self, raw, **changes):
        payload = json.loads(raw.raw_json)
        payload.pop('id', None)
        changes['raw_json'] = json.dumps(payload)
        OuraRecord.objects.filter(pk=raw.pk).update(**changes)
        raw.refresh_from_db()

    def test_rejected_incoming_identity_retires_a_valid_current_observation(self):
        ring = self.connect(self.owner, 'fabricated-transition')
        self.store(ring, 'daily_activity', 'fabricated-transition-raw', self.today, {'steps': 18, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        row = SummaryRecord.objects.get(entry_method='derived')
        ever = copy.deepcopy(row.derivation['contributor_identities_ever'])
        raw = OuraRecord.objects.get()
        cases = (
            {'identity_key': 'z' * 64},
            {'identity_key': '0' * 64},
            {'source_record_id': None},
            {'source_record_id': 'changed-id', 'identity_key': hashlib.sha256(b'changed-id').hexdigest()},
        )
        for changes in cases:
            self._drop_payload_id(raw, **changes)
            refresh_stored_sources(self.owner, self.today)
            row.refresh_from_db()
            self.assertNotEqual(row.derivation['status'], 'current')
            self.assertEqual(row.values['steps'], '18')
            self.assertEqual(row.derivation['contributor_identities_ever'], ever)
            audits = SummaryCorrection.objects.count()
            version = row.version
            refresh_stored_sources(self.owner, self.today)
            row.refresh_from_db()
            self.assertEqual(row.version, version)
            self.assertEqual(SummaryCorrection.objects.count(), audits)
            self.assertEqual(identity_inventory(self.owner)['derived'][0]['status'], row.derivation['status'])
            OuraRecord.objects.filter(pk=raw.pk).update(
                source_record_id='fabricated-transition-raw',
                identity_key=hashlib.sha256(b'fabricated-transition-raw').hexdigest(),
                identity_kind='provider_id', raw_json=json.dumps({
                    'day': self.today.isoformat(), 'steps': 18, 'active_calories': 1, 'total_calories': 1}))
            refresh_stored_sources(self.owner, self.today)
            row.refresh_from_db()
            self.assertEqual(row.derivation['status'], 'current')
            self.assertEqual(row.derivation['contributor_identities_ever'], ever)

        stale = copy.deepcopy(row.derivation)
        stale.update(status='stale', quality='stale', current_contributors=[], conflict_reason='missing_input')
        SummaryRecord.objects.filter(pk=row.pk).update(derivation=stale)
        self._drop_payload_id(raw, identity_key='z' * 64)
        version = row.version
        audits = SummaryCorrection.objects.count()
        refresh_stored_sources(self.owner, self.today)
        row.refresh_from_db()
        self.assertEqual(row.derivation['status'], 'stale')
        self.assertEqual(row.version, version)
        self.assertEqual(SummaryCorrection.objects.count(), audits)
        self.assertEqual(row.derivation['contributor_identities_ever'], ever)

        broken = copy.deepcopy(ever and row.derivation)
        broken['schema_version'] = []
        SummaryRecord.objects.filter(pk=row.pk).update(derivation=broken)
        before = (row.version, broken, row.values['steps'])
        refresh_stored_sources(self.owner, self.today)
        row.refresh_from_db()
        self.assertEqual((row.version, row.derivation, row.values['steps']), before)

        absent = self.connect(self.owner, 'fabricated-transition-absent')
        OuraRecord.objects.create(
            connection=absent, collection='daily_activity', identity_key='z' * 64,
            source_record_id='fabricated-absent-source', identity_kind='provider_id',
            raw_json=json.dumps({'day': self.today.isoformat(), 'steps': 3, 'active_calories': 1, 'total_calories': 1}))
        refresh_stored_sources(self.owner, self.today)
        self.assertFalse(SummaryRecord.objects.filter(connection=absent).exists())

    def test_empty_cumulative_lineage_cannot_waive_deletion(self):
        for status in ('current', 'stale', 'conflict'):
            owner = get_user_model().objects.create_user(f'synthetic-empty-{status}')
            ring = self.connect(owner, f'fabricated-empty-{status}')
            self.store(ring, 'daily_activity', 'same-id', self.today, {'steps': 4, 'active_calories': 1, 'total_calories': 1})
            refresh_stored_sources(owner, self.today)
            deleted = SummaryRecord.objects.get(owner=owner, entry_method='derived')
            delete_summary(owner, str(deleted.id), deleted.version, str(uuid4()))
            deleted.refresh_from_db()
            meta = copy.deepcopy(deleted.derivation)
            meta.update(status=status, quality=status, current_contributors=[], contributor_identities_ever=[])
            SummaryRecord.objects.filter(pk=deleted.pk).update(derivation=meta)
            raw = OuraRecord.objects.get(connection=ring)
            payload = json.loads(raw.raw_json)
            payload['day'] = (self.today - timedelta(days=1)).isoformat()
            raw.raw_json = json.dumps(payload)
            raw.save(update_fields=['raw_json'])
            before = list(SummaryRecord.objects.filter(pk=deleted.pk).values())
            refresh_stored_sources(owner, self.today)
            self.assertFalse(SummaryRecord.objects.filter(owner=owner, deleted_at__isnull=True, derivation__status='current').exists())
            self.assertEqual(list(SummaryRecord.objects.filter(pk=deleted.pk).values()), before)
            other = self.connect(owner, f'fabricated-empty-distinct-{status}')
            self.store(other, 'daily_activity', 'same-id', self.today, {'steps': 6, 'active_calories': 1, 'total_calories': 1})
            refresh_stored_sources(owner, self.today)
            self.assertEqual(SummaryRecord.objects.get(connection=other, deleted_at__isnull=True).values['steps'], '6')

        owner = get_user_model().objects.create_user('synthetic-malformed-lineage')
        ring = self.connect(owner, 'fabricated-malformed-lineage')
        self.store(ring, 'daily_activity', 'same-id', self.today, {'steps': 8, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(owner, self.today)
        deleted = SummaryRecord.objects.get(owner=owner, entry_method='derived')
        delete_summary(owner, str(deleted.id), deleted.version, str(uuid4()))
        meta = copy.deepcopy(deleted.derivation)
        meta.update(status='stale', quality='stale', current_contributors=[])
        meta['contributor_identities_ever'] = [{'identity_key': []}]
        meta['schema_version'] = 2.0
        SummaryRecord.objects.filter(pk=deleted.pk).update(derivation=meta)
        raw = OuraRecord.objects.get(connection=ring)
        payload = json.loads(raw.raw_json)
        payload['day'] = (self.today - timedelta(days=1)).isoformat()
        raw.raw_json = json.dumps(payload)
        raw.save(update_fields=['raw_json'])
        refresh_stored_sources(owner, self.today)
        self.assertFalse(SummaryRecord.objects.filter(owner=owner, connection=ring, deleted_at__isnull=True).exists())

    def test_disposable_backup_restores_identity_metadata_and_audits(self):
        ring = self.connect(self.owner, 'fabricated-backup')
        self.store(ring, 'daily_activity', 'fabricated-backup-raw', self.today, {'steps': 6, 'active_calories': 1, 'total_calories': 1})
        refresh_stored_sources(self.owner, self.today)
        name = str(settings.DATABASES['default']['NAME'])
        owning = Path(settings.BASE_DIR) / 'private' / 'dashboard.sqlite3'
        self.assertNotEqual(Path(name), owning)
        private = Path(os.environ['TMPDIR']) / f'cx83-fit-h0-backup-{uuid4().hex}'
        private.mkdir(mode=0o700)
        with sqlite3.connect(name, uri=name.startswith('file:')) as source, sqlite3.connect(private / 'dashboard.sqlite3') as destination:
            source.backup(destination)
        os.chmod(private / 'dashboard.sqlite3', 0o600)
        target = Path(os.environ['TMPDIR']) / f'cx83-fit-h0-restore-{uuid4().hex}'
        target.mkdir(mode=0o700)
        snapshot(private, target)
        self.assertTrue(verify_restore(target)['counts_match'])

        def grab(path):
            with sqlite3.connect(path) as db:
                return (
                    db.execute('SELECT "source_record_id", "connection_id", "derivation", "values" FROM tracking_summaryrecord').fetchall(),
                    db.execute('SELECT before, after FROM tracking_summarycorrection').fetchall(),
                )
        self.assertEqual(grab(private / 'dashboard.sqlite3'), grab(target / 'dashboard.sqlite3'))

    def test_disposable_forward_migration_preserves_legacy_bytes(self):
        repo = Path(settings.BASE_DIR).resolve()
        root = Path(os.environ['TMPDIR']).resolve() / f'cx83-fit-h0-migrate-{uuid4().hex}'
        root.mkdir(mode=0o700)
        self.assertFalse(str(root).startswith(str(repo)))
        self.assertFalse(root.is_relative_to(repo / 'private'))
        script = textwrap.dedent('''
            import os, sqlite3, sys
            from pathlib import Path
            root = Path(os.environ["DISPOSABLE_ROOT"]).resolve()
            repo = Path(os.environ["SOURCE_ROOT"]).resolve()
            assert not str(root).startswith(str(repo))
            os.environ["DASHBOARD_PRIVATE_ROOT"] = str(root)
            os.environ["DASHBOARD_LOCAL_ONLY"] = "1"
            os.environ["DASHBOARD_ALLOWED_HOSTS"] = "127.0.0.1,localhost,testserver"
            os.environ["OWNER_USERNAME"] = "synthetic-owner"
            os.environ["DJANGO_SECRET_KEY"] = "synthetic-secret-key-for-disposable-migration-proof-0001"
            os.environ["SMS_ENABLED"] = "0"
            os.environ["SITE_EDITS_ENABLED"] = "0"
            sys.path.insert(0, str(repo))
            import django
            django.setup()
            from django.conf import settings
            from django.contrib.auth import get_user_model
            from django.core.management import call_command
            from django.utils import timezone
            name = Path(settings.DATABASES["default"]["NAME"]).resolve()
            assert name.is_relative_to(root)
            assert name != (repo / "private" / "dashboard.sqlite3").resolve()
            call_command("migrate", "tracking", "0010_holding_space", verbosity=0, interactive=False)
            user = get_user_model()(username="synthetic-owner", last_login=timezone.now())
            user.set_unusable_password()
            user.save()
            db = sqlite3.connect(name)
            rows = [
                ("11111111-1111-1111-1111-111111111111", "2026-11-10", "oura", "fabricated-legacy-byte", "imported", None),
                ("11111111-1111-1111-1111-111111111112", "2026-11-08", "oura", "fabricated-legacy-tombstone", "imported", "2026-11-08 12:00:00"),
                ("11111111-1111-1111-1111-111111111113", "2026-11-07", "oura", "fabricated-manual-byte", "manually_reported", "2026-11-07 12:00:00"),
                ("11111111-1111-1111-1111-111111111114", "2026-11-08", "csv:oura", "fabricated-csv-byte", "imported", "2026-11-08 12:00:00"),
            ]
            for identity, day, source, source_id, method, deleted in rows:
                db.execute(
                    'INSERT INTO tracking_summaryrecord ("id", "owner_id", "kind", "local_date", "source_timezone", "source_system", "source_record_id", "entry_method", "device", "completeness", "values", "notes", "synthetic", "version", "created_at", "updated_at", "deleted_at") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (identity, user.id, "activity", day, "America/Chicago", source, source_id, method, "Oura", "partial", '{"steps": "7"}', "", 0, 1, "2026-11-10 12:00:00", "2026-11-10 12:00:00", deleted))
            db.execute(
                'INSERT INTO tracking_ouraconnection ("id", "owner_id", "account_key", "source_account_id", "synthetic", "generation", "token_ciphertext", "state", "created_at") VALUES (?,?,?,?,?,?,?,?,?)',
                ("33333333-3333-3333-3333-333333333333", user.id, "fabricated-byte", "fabricated-byte", 0, "44444444-4444-4444-4444-444444444444", "", "disconnected", "2026-11-10 12:00:00"))
            db.execute(
                'INSERT INTO tracking_ourarecord ("id", "connection_id", "collection", "identity_key", "source_record_id", "identity_kind", "raw_json", "version", "updated_at") VALUES (?,?,?,?,?,?,?,?,?)',
                ("55555555-5555-5555-5555-555555555555", "33333333-3333-3333-3333-333333333333", "daily_activity", "ab" * 32, "fabricated-raw-byte", "provider_id", '{"day":"2026-11-08","steps":7}', 1, "2026-11-10 12:00:00"))
            db.execute(
                "INSERT INTO tracking_writerequest (owner_id, request_id, payload_hash, response, created_at) VALUES (?,?,?,?,?)",
                (user.id, "22222222-2222-2222-2222-222222222222", "abc", '{"deleted_at": "2026-11-10T12:00:00+00:00"}', "2026-11-10 12:00:00"))
            request_id = db.execute("SELECT id FROM tracking_writerequest").fetchone()[0]
            db.execute(
                'INSERT INTO tracking_summarycorrection ("record_id", "request_id", "before", "after", "created_at") VALUES (?,?,?,?,?)',
                ("11111111-1111-1111-1111-111111111111", request_id, '{"steps": "7"}', '{"steps": "7", "deleted_at": "kept"}', "2026-11-10 12:00:00"))
            db.commit()
            def snapshot():
                return {
                    "summary": db.execute('SELECT "id", "owner_id", "kind", "local_date", "source_timezone", "source_system", "source_record_id", "entry_method", "device", "completeness", "values", "notes", "synthetic", "version", "created_at", "updated_at", "deleted_at" FROM tracking_summaryrecord ORDER BY id').fetchall(),
                    "receipt": db.execute('SELECT "owner_id", "request_id", "payload_hash", "response", "created_at" FROM tracking_writerequest').fetchall(),
                    "correction": db.execute('SELECT "record_id", "request_id", "before", "after", "created_at" FROM tracking_summarycorrection').fetchall(),
                    "raw": db.execute('SELECT "id", "connection_id", "collection", "identity_key", "source_record_id", "identity_kind", "raw_json", "version" FROM tracking_ourarecord').fetchall(),
                }
            before = snapshot()
            call_command("migrate", "tracking", "0011_projection_identity", verbosity=0, interactive=False)
            after = snapshot()
            assert before == after, (before, after)
            extra = db.execute("SELECT connection_id, derivation FROM tracking_summaryrecord ORDER BY id").fetchall()
            assert extra == [(None, None), (None, None), (None, None), (None, None)]
            call_command("migrate", "tracking", "0010_holding_space", verbosity=0, interactive=False)
            assert snapshot() == before
            call_command("migrate", "tracking", "0011_projection_identity", verbosity=0, interactive=False)
            from tracking.models import OuraConnection, SummaryRecord
            ring = OuraConnection.objects.create(owner=user, account_key="fabricated-derived", source_account_id="fabricated-derived", synthetic=False, state="disconnected")
            derived = {
                "schema_version": 2, "recipe_version": 1, "account_id": str(ring.id), "timezone_status": "unknown",
                "status": "current", "quality": "current", "current_contributors": [], "contributor_identities_ever": [],
                "conflict_reason": "",
            }
            SummaryRecord.objects.create(
                owner=user, connection=ring, synthetic=False, kind="activity", local_date="2026-11-06", source_timezone="",
                source_system="oura", source_record_id=f"derived:oura:{ring.id}:0:activity:2026-11-06", entry_method="derived",
                values={"steps": "1"}, derivation=derived)
            preserved = db.execute("SELECT derivation FROM tracking_summaryrecord WHERE entry_method='derived'").fetchone()
            try:
                call_command("migrate", "tracking", "0010_holding_space", verbosity=0, interactive=False)
            except Exception as exc:
                assert "Operational rollback" in str(exc), exc
            else:
                raise SystemExit("reverse should refuse populated derived data")
            db.close()
            checked = sqlite3.connect(name)
            columns = [row[1] for row in checked.execute("PRAGMA table_info(tracking_summaryrecord)")]
            assert "connection_id" in columns and "derivation" in columns
            assert checked.execute("SELECT derivation FROM tracking_summaryrecord WHERE entry_method='derived'").fetchone() == preserved
            print("MIGRATION_BYTES_PRESERVED")
        ''')
        env = os.environ.copy()
        env.update({'DISPOSABLE_ROOT': str(root), 'SOURCE_ROOT': str(repo), 'PYTHONDONTWRITEBYTECODE': '1'})
        completed = subprocess.run([sys_executable(), '-c', script], cwd=repo, env=env, text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn('MIGRATION_BYTES_PRESERVED', completed.stdout)


def sys_executable():
    return os.environ.get('VIRTUAL_ENV_PYTHON') or sys_python()


def sys_python():
    import sys
    return sys.executable
