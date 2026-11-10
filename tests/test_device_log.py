"""Deleted Oura projections stay suppressed. Fabricated rows only."""
import hashlib
import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models.query import QuerySet
from django.test import TransactionTestCase
from django.utils import timezone

from tracking.device_log import project_stored_devices
from tracking.models import OuraConnection, OuraRecord, SummaryCorrection, SummaryRecord, WriteRequest
from tracking.plan import fitness_plan
from tracking.summaries import delete_summary, serialize_summary


class DeletedDeviceProjectionTests(TransactionTestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(settings.OWNER_USERNAME)
        self.today = timezone.localdate()
        self.connection = OuraConnection.objects.create(
            owner=self.owner, account_key='fabricated-ring', source_account_id='fabricated-ring', synthetic=False)

    def store(self, collection, source, day, payload):
        OuraRecord.objects.create(
            connection=self.connection, collection=collection,
            identity_key=hashlib.sha256(source.encode()).hexdigest(),
            source_record_id=source, identity_kind='provider_id', raw_json=json.dumps(payload))

    def activity(self, source, day, steps):
        self.store('daily_activity', source, day, {
            'day': day.isoformat(), 'steps': steps, 'active_calories': 100, 'total_calories': 200})

    def sleep(self, source, day, seconds):
        self.store('sleep', source, day, {'day': day.isoformat(), 'total_sleep_duration': seconds})

    def fingerprint(self, record):
        record.refresh_from_db()
        return {
            'id': str(record.id), 'kind': record.kind, 'source_system': record.source_system,
            'source_record_id': record.source_record_id, 'device': record.device,
            'synthetic': record.synthetic, 'entry_method': record.entry_method,
            'version': record.version, 'values': record.values,
            'deleted_at': record.deleted_at, 'updated_at': record.updated_at,
        }

    def audits(self):
        requests = list(WriteRequest.objects.filter(owner=self.owner).order_by('created_at', 'id').values(
            'id', 'request_id', 'payload_hash', 'response'))
        corrections = list(SummaryCorrection.objects.filter(record__owner=self.owner).order_by('created_at', 'id').values(
            'id', 'request_id', 'before', 'after'))
        return requests, corrections

    def test_deleted_activity_stays_suppressed_while_other_rows_project(self):
        self.activity('fabricated-activity-today', self.today, 1111)
        self.sleep('fabricated-sleep-today', self.today, 3600)
        project_stored_devices(self.owner, self.today)
        activity = SummaryRecord.objects.get(owner=self.owner, kind='activity', local_date=self.today)
        recovery = SummaryRecord.objects.get(owner=self.owner, kind='recovery', local_date=self.today)
        delete_summary(self.owner, str(activity.id), activity.version, str(uuid4()))
        kept = self.fingerprint(activity)
        recovery_before = self.fingerprint(recovery)
        receipts = self.audits()
        self.activity('fabricated-activity-yesterday', self.today - timedelta(days=1), 2222)
        project_stored_devices(self.owner, self.today)
        self.assertTrue(connection.get_autocommit())
        first = fitness_plan(self.owner, self.today)
        second = fitness_plan(self.owner, self.today)
        self.client.force_login(self.owner)
        page = self.client.get('/plan/')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, '2222.0')
        self.assertContains(page, '60.0')
        self.assertNotContains(page, '1111')
        self.assertEqual(self.fingerprint(activity), kept)
        self.assertEqual(self.fingerprint(recovery), recovery_before)
        self.assertEqual(self.audits(), receipts)
        self.assertEqual(SummaryRecord.objects.filter(
            owner=self.owner, kind='activity', local_date=self.today).count(), 1)
        self.assertEqual(SummaryRecord.objects.filter(
            owner=self.owner, kind='activity', local_date=self.today, deleted_at__isnull=True).count(), 0)
        self.assertEqual(first['analysis']['steps'][0]['average'], '2222.0')
        self.assertEqual(first['analysis']['steps'][0]['observed_days'], 1)
        self.assertEqual(second['analysis']['sleep_minutes'][0]['average'], '60.0')
        self.assertEqual(SummaryRecord.objects.get(
            owner=self.owner, kind='activity', local_date=self.today - timedelta(days=1)).version, 1)

    def test_deleted_recovery_stays_suppressed_while_activity_remains(self):
        self.activity('fabricated-activity-kept', self.today, 3333)
        self.sleep('fabricated-sleep-deleted', self.today, 7200)
        project_stored_devices(self.owner, self.today)
        activity = SummaryRecord.objects.get(owner=self.owner, kind='activity', local_date=self.today)
        recovery = SummaryRecord.objects.get(owner=self.owner, kind='recovery', local_date=self.today)
        delete_summary(self.owner, str(recovery.id), recovery.version, str(uuid4()))
        kept = self.fingerprint(recovery)
        activity_before = self.fingerprint(activity)
        receipts = self.audits()
        self.sleep('fabricated-sleep-yesterday', self.today - timedelta(days=1), 10800)
        project_stored_devices(self.owner, self.today)
        self.assertTrue(connection.get_autocommit())
        for _ in range(2):
            fitness_plan(self.owner, self.today)
        self.client.force_login(self.owner)
        page = self.client.get('/plan/')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, '3333.0')
        self.assertContains(page, '180.0')
        self.assertNotContains(page, '120.0')
        self.assertEqual(self.fingerprint(recovery), kept)
        self.assertEqual(self.fingerprint(activity), activity_before)
        self.assertEqual(self.audits(), receipts)
        self.assertEqual(SummaryRecord.objects.filter(
            owner=self.owner, kind='recovery', local_date=self.today, deleted_at__isnull=True).count(), 0)
        self.assertEqual(SummaryRecord.objects.filter(
            owner=self.owner, kind='recovery', local_date=self.today).count(), 1)

    def test_imported_projection_is_idempotent(self):
        self.activity('fabricated-activity-once', self.today, 4444)
        self.assertTrue(connection.get_autocommit())
        project_stored_devices(self.owner, self.today)
        first = self.fingerprint(SummaryRecord.objects.get(owner=self.owner, kind='activity'))
        project_stored_devices(self.owner, self.today)
        fitness_plan(self.owner, self.today)
        second = self.fingerprint(SummaryRecord.objects.get(owner=self.owner, kind='activity'))
        self.assertEqual(second, first)
        self.assertEqual(second['version'], 1)
        self.assertFalse(second['deleted_at'])
        self.assertEqual(SummaryRecord.objects.filter(owner=self.owner, kind='activity').count(), 1)

    def test_manual_oura_row_is_not_replaced(self):
        manual = SummaryRecord.objects.create(
            owner=self.owner, kind='activity', local_date=self.today, source_timezone='America/Chicago',
            source_system='oura', source_record_id='fabricated-manual-activity', entry_method='manually_reported',
            device='Oura', completeness='partial', synthetic=False,
            values={'steps': '50', 'workout_minutes': None, 'active_calories': None,
                    'total_calories': None, 'workout_summary': ''})
        self.activity('fabricated-imported-activity', self.today, 999)
        before = self.fingerprint(manual)
        self.assertTrue(connection.get_autocommit())
        project_stored_devices(self.owner, self.today)
        fitness_plan(self.owner, self.today)
        self.assertEqual(self.fingerprint(manual), before)
        self.assertEqual(SummaryRecord.objects.filter(owner=self.owner, kind='activity').count(), 1)
        self.assertEqual(WriteRequest.objects.filter(owner=self.owner).count(), 0)

    def test_changed_live_projection_updates_the_imported_row(self):
        self.activity('fabricated-activity-changed', self.today, 1000)
        project_stored_devices(self.owner, self.today)
        row = SummaryRecord.objects.get(owner=self.owner, kind='activity')
        self.assertEqual(row.version, 1)
        self.assertIsNone(row.deleted_at)
        raw = OuraRecord.objects.get(source_record_id='fabricated-activity-changed')
        payload = json.loads(raw.raw_json)
        payload['steps'] = 9000
        raw.raw_json = json.dumps(payload)
        raw.save(update_fields=['raw_json'])
        self.assertTrue(connection.get_autocommit())
        project_stored_devices(self.owner, self.today)
        plan = fitness_plan(self.owner, self.today)
        self.assertFalse(plan['projection']['writes'])
        row.refresh_from_db()
        self.assertEqual(row.version, 2)
        self.assertIsNone(row.deleted_at)
        self.assertEqual(row.values['steps'], '9000')
        self.assertEqual(plan['analysis']['steps'][0]['average'], '9000.0')
        self.assertEqual(SummaryRecord.objects.filter(owner=self.owner, kind='activity').count(), 1)
        self.assertEqual(WriteRequest.objects.filter(owner=self.owner).count(), 0)

    def test_stale_activity_update_cannot_resurrect_a_deletion(self):
        self.stale_update_keeps_the_tombstone('activity')

    def test_stale_recovery_update_cannot_resurrect_a_deletion(self):
        self.stale_update_keeps_the_tombstone('recovery')

    def stale_update_keeps_the_tombstone(self, kind):
        self.activity('fabricated-race-activity', self.today, 1000)
        self.sleep('fabricated-race-sleep', self.today, 28800)
        project_stored_devices(self.owner, self.today)
        target = SummaryRecord.objects.get(owner=self.owner, kind=kind)
        collection = 'daily_activity' if kind == 'activity' else 'sleep'
        raw = OuraRecord.objects.get(connection=self.connection, collection=collection)
        payload = json.loads(raw.raw_json)
        payload.update({'steps': 9000} if kind == 'activity' else {'total_sleep_duration': 18000})
        raw.raw_json = json.dumps(payload)
        raw.save(update_fields=['raw_json'])
        raw_before = list(OuraRecord.objects.order_by('id').values())
        state = {}
        real_update = QuerySet.update

        def intercepted(queryset, **kwargs):
            if queryset.model is SummaryRecord and 'deleted_at' not in kwargs and 'database' not in state:
                current = SummaryRecord.objects.get(pk=target.pk)
                self.assertIsNone(current.deleted_at)
                self.assertEqual(current.version, 1)
                self.assertTrue(connection.get_autocommit())
                self.assertFalse(connection.in_atomic_block)
                deleted = delete_summary(self.owner, str(current.pk), current.version, str(uuid4()))
                state['database'] = serialize_summary(SummaryRecord.objects.get(pk=current.pk))
                state['audits'] = self.audits()
                self.assertIsNotNone(deleted['deleted_at'])
                self.assertEqual(deleted['version'], 2)
            return real_update(queryset, **kwargs)

        with patch.object(QuerySet, 'update', intercepted):
            project_stored_devices(self.owner, self.today)
        plan = fitness_plan(self.owner, self.today)
        self.assertFalse(plan['projection']['writes'])
        after = serialize_summary(SummaryRecord.objects.get(pk=target.pk))
        field = 'steps' if kind == 'activity' else 'sleep_minutes'
        self.assertEqual(after, state['database'])
        self.assertEqual(after['id'], str(target.id))
        self.assertEqual(after['version'], 2)
        self.assertIsNotNone(after['deleted_at'])
        self.assertEqual(plan['analysis'][field], [])
        self.assertEqual(self.audits(), state['audits'])
        self.assertEqual(list(OuraRecord.objects.order_by('id').values()), raw_before)
        repeated = fitness_plan(self.owner, self.today)
        self.assertEqual(repeated['analysis'][field], [])
        self.assertEqual(serialize_summary(SummaryRecord.objects.get(pk=target.pk)), after)
        self.client.force_login(self.owner)
        page = self.client.get('/plan/')
        self.assertEqual(page.status_code, 200)
        if kind == 'activity':
            self.assertContains(page, 'No steps.')
            self.assertNotContains(page, '9000')
        else:
            self.assertContains(page, 'No sleep.')
            self.assertNotContains(page, '300.0')
