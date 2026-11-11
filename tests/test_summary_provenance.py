"""Owner-only unresolved history. Fabricated rows, and no mutation controls for tombstones."""
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from tracking.models import OuraConnection, SummaryCorrection, SummaryRecord, WriteRequest
from tracking.projection_identity import stable_source_id


class SummaryProvenanceTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(settings.OWNER_USERNAME)
        self.other = get_user_model().objects.create_user('synthetic-provenance-other')
        self.client.force_login(self.owner)
        self.day = timezone.localdate()

    def legacy(self, owner, day, synthetic=False, deleted=False, source='oura'):
        return SummaryRecord.objects.create(
            owner=owner, kind='activity', local_date=day, source_timezone='America/Chicago', source_system=source,
            source_record_id=uuid4().hex, entry_method='imported', device='Oura', completeness='partial',
            values={'steps': '12', 'active_calories': '1', 'total_calories': '1'}, synthetic=synthetic,
            deleted_at=timezone.now() if deleted else None)

    def test_inventory_is_owner_only_paginated_and_read_only(self):
        rows = [self.legacy(self.owner, self.day - timedelta(days=offset), synthetic=offset % 2 == 0) for offset in range(31)]
        deleted = rows[0]
        deleted.deleted_at = timezone.now()
        deleted.save(update_fields=['deleted_at'])
        hidden = self.legacy(self.other, self.day, source='oura')
        before = list(SummaryRecord.objects.order_by('id').values_list(
            'id', 'values', 'derivation', 'version', 'synthetic', 'deleted_at', 'source_record_id'))
        anonymous = Client()
        stranger = Client()
        stranger.force_login(self.other)
        with CaptureQueriesContext(connection) as captured:
            denied = anonymous.get('/summaries/provenance/')
            forbidden = stranger.get('/summaries/provenance/')
            page = self.client.get('/summaries/provenance/')
            second = self.client.get('/summaries/provenance/?page=2')
            listing = self.client.get('/summaries/activity/')
            detail = self.client.get(f'/summaries/activity/{rows[1].id}/')
        self.assertEqual(denied.status_code, 302)
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertContains(page, 'Account/test attribution unverified')
        self.assertContains(page, '31 records')
        self.assertNotContains(page, 'confirm_delete')
        self.assertNotContains(page, 'Delete this record')
        self.assertNotContains(page, str(hidden.id))
        self.assertContains(second, 'Previous')
        self.assertContains(listing, 'Unresolved history')
        self.assertContains(listing, 'Account/test attribution unverified')
        self.assertContains(detail, 'Account/test attribution unverified')
        self.assertContains(detail, '12')
        self.assertEqual(list(SummaryRecord.objects.order_by('id').values_list(
            'id', 'values', 'derivation', 'version', 'synthetic', 'deleted_at', 'source_record_id')), before)
        self.assertFalse(any(item['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'REPLACE'))
                             and 'tracking_summary' in item['sql'].lower() for item in captured))

    def test_tombstone_inspection_is_read_only_and_owner_scoped(self):
        note = 'kept-note <script>alert(1)</script>\n' + ('Z' * 180)
        deleted = self.legacy(self.owner, self.day - timedelta(days=1), synthetic=False, deleted=True)
        deleted.notes = note
        deleted.source_record_id = 'tombstone-source-false'
        deleted.values = {'steps': '0', 'active_calories': '1', 'total_calories': '1', 'workout_minutes': None}
        deleted.save(update_fields=['notes', 'source_record_id', 'values'])
        flagged = self.legacy(self.owner, self.day - timedelta(days=2), synthetic=True, deleted=True)
        flagged.notes = 'stored-true-note'
        flagged.source_record_id = 'tombstone-source-true'
        flagged.save(update_fields=['notes', 'source_record_id'])
        live = self.legacy(self.owner, self.day - timedelta(days=3), synthetic=False)
        live.notes = 'live-original-note'
        live.source_record_id = 'live-source-id'
        live.save(update_fields=['notes', 'source_record_id'])
        ring = OuraConnection.objects.create(
            owner=self.owner, account_key='fabricated-account-key', source_account_id='fabricated-external-account',
            synthetic=True, token_ciphertext='fabricated-token-value', state='disconnected')
        derived_day = self.day - timedelta(days=4)
        raw_id = str(uuid4())
        derived = SummaryRecord.objects.create(
            owner=self.owner, kind='activity', local_date=derived_day, source_timezone='', source_system='oura',
            source_record_id=stable_source_id(ring, 'activity', derived_day), entry_method='derived', device='Oura',
            completeness='partial', values={'steps': '9', 'active_calories': '1', 'total_calories': '1'},
            notes='derived-tombstone-note', synthetic=True, connection=ring, deleted_at=timezone.now(),
            derivation={
                'schema_version': 2, 'recipe_version': 1, 'account_id': str(ring.id), 'timezone_status': 'unknown',
                'status': 'current', 'quality': 'current', 'conflict_reason': '',
                'current_contributors': [{'raw_id': raw_id, 'identity_key': 'ab' * 32,
                                          'collection': 'daily_activity', 'source_record_id': 'fabricated-provider',
                                          'version': 1}],
                'contributor_identities_ever': [{'raw_id': raw_id, 'identity_key': 'ab' * 32,
                                                 'collection': 'daily_activity', 'source_record_id': 'fabricated-provider'}],
            })
        nutrition = SummaryRecord.objects.create(
            owner=self.owner, kind='nutrition', local_date=self.day - timedelta(days=5),
            source_timezone='America/Chicago', source_system='oura', source_record_id='nutrition-tombstone',
            entry_method='imported', completeness='partial', deleted_at=timezone.now(),
            values={'calories': '1', 'protein': None, 'total_carbohydrates': None, 'fat': None, 'fiber': None},
            notes='nutrition-secret-note')
        hidden = self.legacy(self.other, self.day, source='oura')
        hidden.source_record_id = 'other-owner-source'
        hidden.save(update_fields=['source_record_id'])
        long_value = 'X' * 400
        for index in range(21):
            marker = 'oldest-correction-sentinel' if index == 0 else (
                'newest-correction-sentinel' if index == 20 else f'fill-{index}')
            receipt = WriteRequest.objects.create(
                owner=self.owner, request_id=uuid4(), payload_hash='ab' * 32,
                response={'secret': 'fabricated-receipt-secret'})
            SummaryCorrection.objects.create(
                record=deleted, request=receipt,
                before={'values': {'steps': '1'}} if index == 20 else None,
                after={'version': index + 1, 'values': {
                    'steps': marker, 'untrusted': '<img src=x onerror=alert(1)>', 'span': long_value}})
        inspection = f'/summaries/provenance/{deleted.id}/'
        before = (
            list(SummaryRecord.objects.order_by('id').values_list(
                'id', 'values', 'notes', 'derivation', 'version', 'synthetic', 'deleted_at', 'source_record_id')),
            list(SummaryCorrection.objects.order_by('id').values_list('id', 'record_id', 'before', 'after')),
            WriteRequest.objects.count(),
            list(OuraConnection.objects.order_by('id').values_list('id', 'account_key', 'source_account_id', 'token_ciphertext')),
        )
        anonymous = Client()
        stranger = Client()
        stranger.force_login(self.other)
        with CaptureQueriesContext(connection) as captured:
            denied = anonymous.get(inspection)
            forbidden = stranger.get(inspection)
            missing = self.client.get(f'/summaries/provenance/{uuid4()}/')
            invalid = self.client.get('/summaries/provenance/not-a-uuid/')
            foreign = self.client.get(f'/summaries/provenance/{hidden.id}/')
            outside = self.client.get(f'/summaries/provenance/{nutrition.id}/')
            ordinary = self.client.get(f'/summaries/activity/{deleted.id}/')
            posted = self.client.post(inspection)
            page = self.client.get(inspection)
            older = self.client.get(inspection + '?page=2')
            bad_page = self.client.get(inspection + '?page=0')
            flagged_page = self.client.get(f'/summaries/provenance/{flagged.id}/')
            live_page = self.client.get(f'/summaries/provenance/{live.id}/')
            live_detail = self.client.get(f'/summaries/activity/{live.id}/')
            derived_page = self.client.get(f'/summaries/provenance/{derived.id}/')
            inventory = self.client.get('/summaries/provenance/')
        self.assertEqual(denied.status_code, 302)
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(invalid.status_code, 404)
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(outside.status_code, 404)
        self.assertEqual(ordinary.status_code, 404)
        self.assertEqual(posted.status_code, 405)
        self.assertEqual(bad_page.status_code, 404)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'tombstone-source-false')
        self.assertContains(page, str(deleted.id))
        self.assertContains(page, 'kept-note')
        self.assertContains(page, 'Z' * 180)
        self.assertContains(page, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(page, '<script>')
        self.assertContains(page, '&lt;img src=x onerror=alert(1)&gt;')
        self.assertNotContains(page, '<img src=x')
        self.assertContains(page, long_value)
        self.assertContains(page, '0 steps')
        self.assertContains(page, 'Unknown')
        self.assertContains(page, 'newest-correction-sentinel')
        self.assertNotContains(page, 'oldest-correction-sentinel')
        self.assertContains(page, 'Older')
        self.assertContains(older, 'oldest-correction-sentinel')
        self.assertContains(older, 'Newer')
        self.assertNotContains(page, 'confirm_delete')
        self.assertNotContains(page, 'Delete this record')
        self.assertNotContains(page, f'/summaries/activity/{deleted.id}/edit/')
        self.assertNotContains(page, f'/summaries/activity/{deleted.id}/delete/')
        self.assertNotContains(page, 'fabricated-receipt-secret')
        self.assertNotContains(page, 'fabricated-account-key')
        self.assertNotContains(page, 'fabricated-external-account')
        self.assertNotContains(page, 'fabricated-token-value')
        self.assertNotContains(page, 'other-owner-source')
        self.assertNotContains(page, 'nutrition-secret-note')
        self.assertContains(flagged_page, 'tombstone-source-true')
        self.assertContains(flagged_page, 'stored-true-note')
        self.assertContains(flagged_page, 'true. This stored flag does not prove')
        self.assertContains(live_page, 'live-source-id')
        self.assertContains(live_page, 'live-original-note')
        self.assertNotContains(live_page, 'confirm_delete')
        self.assertContains(live_detail, 'Delete this record')
        self.assertContains(derived_page, f'Connection {ring.id}')
        self.assertContains(derived_page, 'Class: test')
        self.assertContains(derived_page, 'derived-tombstone-note')
        self.assertContains(derived_page, 'Projection unavailable')
        self.assertNotContains(derived_page, 'fabricated-account-key')
        self.assertNotContains(derived_page, 'fabricated-external-account')
        self.assertNotContains(derived_page, 'fabricated-token-value')
        self.assertContains(inventory, 'Inspect original')
        self.assertContains(inventory, f'/summaries/provenance/{deleted.id}/')
        self.assertNotContains(inventory, 'other-owner-source')
        self.assertEqual((
            list(SummaryRecord.objects.order_by('id').values_list(
                'id', 'values', 'notes', 'derivation', 'version', 'synthetic', 'deleted_at', 'source_record_id')),
            list(SummaryCorrection.objects.order_by('id').values_list('id', 'record_id', 'before', 'after')),
            WriteRequest.objects.count(),
            list(OuraConnection.objects.order_by('id').values_list('id', 'account_key', 'source_account_id', 'token_ciphertext')),
        ), before)
        watched = ('tracking_summary', 'tracking_summarycorrection', 'tracking_writerequest', 'tracking_ouraconnection')
        self.assertFalse(any(
            item['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'REPLACE'))
            and any(table in item['sql'].lower() for table in watched) for item in captured))
