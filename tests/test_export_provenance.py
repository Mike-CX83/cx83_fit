"""Additive export provenance. Original archive members stay preserved."""
import json
import tempfile
import zipfile
from datetime import date, datetime
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models.query import QuerySet
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from tracking.exports import PROVENANCE_MEMBER, README_V1, build_export
from tracking.models import (
    JournalScore, OuraConnection, OuraPage, OuraRecord, SobrietyDay, SummaryCorrection, SummaryRecord, WriteRequest,
)
from tracking.projection_identity import stable_source_id
from tracking.summary_evidence import evidence_envelope


FROZEN = datetime(2026, 11, 10, 18, 0, tzinfo=ZoneInfo('America/Chicago'))
HISTORY_KEYS = {
    'format', 'exported_at', 'includes_synthetic', 'deletion_policy', 'measurements', 'summaries', 'photos',
    'corrections', 'nutrition_targets', 'reviews', 'diet_entries', 'clinical_items', 'holding_partners',
    'holding_messages', 'journal_entries', 'journal_observations', 'journal_memories', 'journal_questions',
    'journal_scores', 'sobriety_pattern', 'journal_corrections',
}
PATTERN_KEYS = {
    'local_date', 'formula_version', 'potential', 'use_recorded', 'wear', 'drivers', 'run_started',
    'days_in_run', 'synthetic',
}
TABLES = (
    'tracking_summaryrecord', 'tracking_summarycorrection', 'tracking_writerequest', 'tracking_ourarecord',
    'tracking_ourapage', 'tracking_ourarevision', 'tracking_sobrietyday', 'tracking_journalscore',
)


def snapshot():
    stored = {}
    with connection.cursor() as cursor:
        for table in TABLES:
            cursor.execute(f'SELECT * FROM {table} ORDER BY rowid')
            stored[table] = cursor.fetchall()
    return stored


class ExportProvenanceTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('synthetic-owner')
        self.other = get_user_model().objects.create_user('synthetic-export-other')
        self.day = date(2026, 11, 1)

    def values(self):
        return {'steps': '0', 'active_calories': None, 'total_calories': None, 'workout_minutes': None, 'workout_summary': ''}

    def record(self, owner=None, **changes):
        owner = self.owner if owner is None else owner
        fields = {
            'owner': owner, 'kind': 'activity', 'local_date': self.day, 'source_timezone': 'America/Chicago',
            'source_system': 'oura', 'source_record_id': uuid4().hex, 'entry_method': 'imported', 'device': 'Oura',
            'completeness': 'partial', 'values': self.values(), 'notes': '', 'synthetic': False,
        }
        fields.update(changes)
        return SummaryRecord.objects.create(**fields)

    def derived(self, owner, synthetic, status, day, *, ever_style='dict', extra=None, connection_owner=None):
        connection_owner = owner if connection_owner is None else connection_owner
        ring = OuraConnection.objects.create(
            owner=connection_owner, account_key=f'sentinel-account-key-{uuid4().hex[:8]}',
            source_account_id='sentinel-external-account', synthetic=synthetic,
            token_ciphertext='sentinel-token-value', state='disconnected')
        raw_id = str(uuid4())
        identity = {'raw_id': raw_id, 'identity_key': 'ab' * 32, 'collection': 'daily_activity',
                    'source_record_id': 'fabricated-provider'}
        ever = [raw_id] if ever_style == 'uuid' else [identity]
        current = [] if status in {'stale', 'conflict'} else [{**identity, 'version': 1}]
        stored_status = 'current' if status == 'invalid' else status
        derivation = {
            'schema_version': [] if status == 'invalid' else 2, 'recipe_version': 1, 'account_id': str(ring.id),
            'timezone_status': 'unknown', 'status': stored_status, 'quality': stored_status,
            'current_contributors': current, 'contributor_identities_ever': ever, 'conflict_reason': 'sentinel-conflict-reason',
        }
        if extra:
            derivation.update(extra)
        row = SummaryRecord.objects.create(
            owner=owner, kind='activity', local_date=day, source_timezone='', source_system='oura',
            source_record_id=stable_source_id(ring, 'activity', day), entry_method='derived', device='Oura',
            completeness='partial', values=self.values(), synthetic=synthetic, connection=ring, derivation=derivation)
        return row, ring

    def pattern(self, local_date, coverage, formula='sobriety-pattern-1', synthetic=False, wear=None):
        return SobrietyDay.objects.create(
            owner=self.owner, local_date=local_date, formula_version=formula, potential='incomplete',
            use_recorded=False, wear=wear if wear is not None else {'devices': []}, drivers=['kept-driver'],
            coverage=coverage, synthetic=synthetic)

    def export(self, owner=None, include_synthetic=True):
        owner = self.owner if owner is None else owner
        with patch('tracking.exports.timezone.now', return_value=FROZEN):
            handle = build_export(owner, include_synthetic)
        self.addCleanup(handle.close)
        return zipfile.ZipFile(handle)

    def test_old_members_and_sidecar_keep_their_contracts(self):
        legacy = [self.record(synthetic=flag, kind=kind, local_date=self.day) for flag, kind in (
            (False, 'activity'), (True, 'recovery'))]
        legacy[1].values = {'sleep_minutes': '480', 'hrv_ms': None, 'resting_hr_bpm': None, 'readiness': None, 'hrv_method': ''}
        legacy[1].save(update_fields=['values'])
        manual = self.record(entry_method='manually_reported', source_record_id='manual-oura', local_date=date(2026, 10, 30),
                              notes='=café\nnext', source_system='oura', kind='recovery',
                              values={'sleep_minutes': '0', 'hrv_ms': None, 'resting_hr_bpm': None, 'readiness': None, 'hrv_method': ''})
        neighbors = [
            self.record(source_system='csv:oura', source_record_id='csv-oura', local_date=self.day),
            self.record(kind='nutrition', source_record_id='nutrition-oura', local_date=self.day,
                        values={'calories': '0', 'protein': None}),
            self.record(kind='health', source_record_id='health-import', local_date=self.day,
                        values={'name': 'Synthetic', 'value': None, 'unit': ''}),
            self.record(source_system='synthetic-source', entry_method='imported', source_record_id='other-import',
                        local_date=self.day),
        ]
        current, ring = self.derived(self.owner, False, 'current', self.day, ever_style='uuid', extra={
            'nested_secret': {'token': 'sentinel-extra-metadata'}})
        stale, _ring = self.derived(self.owner, False, 'stale', self.day)
        conflict, _ring = self.derived(self.owner, True, 'conflict', self.day)
        invalid, _ring = self.derived(self.owner, False, 'invalid', self.day)
        deleted, _ring = self.derived(self.owner, False, 'current', self.day)
        deleted.deleted_at = timezone.now()
        deleted.save(update_fields=['deleted_at'])
        foreign, foreign_ring = self.derived(
            self.owner, False, 'current', self.day, connection_owner=self.other)
        foreign_ring.account_key = 'sentinel-foreign-account-key'
        foreign_ring.token_ciphertext = 'sentinel-foreign-token'
        foreign_ring.save(update_fields=['account_key', 'token_ciphertext'])
        other_row, _other_ring = self.derived(self.other, False, 'current', self.day)
        receipt = WriteRequest.objects.create(owner=self.owner, request_id=uuid4(), payload_hash='cd' * 32,
                                               response={'kept': '  spaced  '})
        SummaryCorrection.objects.create(record=manual, request=receipt, before={'notes': '  spaced  value'},
                                          after={'notes': 'next', 'values': {'sleep_minutes': '0'}})
        raw_text = ' { "id" : "synthetic-raw" , "keep" : true }\n'
        raw = OuraRecord.objects.create(
            connection=ring, collection='daily_activity', identity_key='ab' * 32, source_record_id='synthetic-raw',
            identity_kind='provider_id', raw_json=raw_text)
        OuraPage.objects.create(connection=ring, collection='daily_activity', sha256='ef' * 32, raw_json=raw_text)
        JournalScore.objects.create(
            owner=self.owner, kind='daily_state', local_date=self.day, formula_version='daily-state-1', result=None,
            coverage={'secret': 'sentinel-score-coverage'}, synthetic=False)
        wear = {'devices': [{'name': 'watch-a', 'status': 'off_wrist'}]}
        old = self.pattern(date(2020, 1, 1), {}, wear=wear)
        blank_marker = self.pattern(date(2020, 1, 1), {'evidence_gate_version': None}, formula='sobriety-pattern-0')
        malformed = self.pattern(date(2026, 11, 2), [])
        wrong_type = self.pattern(date(2026, 11, 3), {'evidence_gate_version': 7})
        future = self.pattern(date(2026, 11, 4), {'evidence_gate_version': 'h0-future', 'secret': 'sentinel-future-marker'})
        recognized = self.pattern(date(2026, 11, 5), {'evidence_gate_version': 'h0-b2', 'recovery': [{'values': {'sleep_minutes': '1'}}]})
        hidden = self.pattern(date(2026, 11, 6), {'evidence_gate_version': 'h0-b2'}, synthetic=True)
        before = snapshot()
        guards = [
            patch('tracking.projection_identity.refresh_stored_sources', side_effect=AssertionError('refresh called')),
            patch('tracking.sobriety_pattern.read_pattern', side_effect=AssertionError('pattern called')),
            patch('tracking.journal_continuity.score_day', side_effect=AssertionError('score called')),
            patch('tracking.headroom.headroom', side_effect=AssertionError('headroom called')),
            patch('tracking.oura.sync.new_sync', side_effect=AssertionError('sync called')),
            patch('tracking.oura.sync.resume', side_effect=AssertionError('resume called')),
            patch('tracking.oura.transport.request', side_effect=AssertionError('provider called')),
        ]
        for guard in guards:
            guard.start()
            self.addCleanup(guard.stop)
        with CaptureQueriesContext(connection) as captured:
            first = self.export()
            second = self.export()
            default = self.export(include_synthetic=False)
        self.assertFalse(any(item['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'REPLACE')) for item in captured))
        self.assertEqual(snapshot(), before)
        self.assertEqual(first.read('history.json'), second.read('history.json'))
        self.assertEqual(first.read('summaries.csv'), second.read('summaries.csv'))
        self.assertEqual(first.read(PROVENANCE_MEMBER), second.read(PROVENANCE_MEMBER))
        history = json.loads(first.read('history.json'))
        self.assertEqual(set(history), HISTORY_KEYS)
        self.assertEqual(history['format'], 'private-health-export-v1')
        self.assertEqual(history['exported_at'], FROZEN.isoformat())
        self.assertTrue(history['includes_synthetic'])
        self.assertEqual(history['corrections'][0]['before'], {'notes': '  spaced  value'})
        self.assertEqual(history['corrections'][0]['after'], {'notes': 'next', 'values': {'sleep_minutes': '0'}})
        self.assertEqual(history['journal_scores'][0]['coverage'], {'secret': 'sentinel-score-coverage'})
        for row in history['sobriety_pattern']:
            self.assertEqual(set(row), PATTERN_KEYS)
        preserved = next(row for row in history['sobriety_pattern']
                         if row['local_date'] == '2020-01-01' and row['formula_version'] == 'sobriety-pattern-1')
        self.assertEqual(preserved['wear'], wear)
        csv_bytes = first.read('summaries.csv')
        self.assertTrue(csv_bytes.startswith(b'\xef\xbb\xbf'))
        text = csv_bytes.decode('utf-8-sig')
        self.assertIn('\r\n', text)
        self.assertTrue(text.startswith('id,kind,local_date,source_timezone,source_system,source_record_id,entry_method,device,completeness,values,notes,synthetic,version,deleted_at\r\n'))
        self.assertIn("'=café\nnext", text)
        self.assertIn('""sleep_minutes"": ""0""', text)
        self.assertIn('""active_calories"": null', text)
        page_name = next(name for name in first.namelist() if name.startswith('oura/pages/'))
        record_name = f'oura/records/{raw.pk}.json'
        self.assertEqual(first.read(page_name), raw_text.encode())
        raw_member = json.loads(first.read(record_name))
        self.assertEqual(raw_member['raw_json'], raw_text)
        self.assertEqual(raw_member['source_account_id'], 'sentinel-external-account')
        sidecar = json.loads(first.read(PROVENANCE_MEMBER))
        self.assertEqual(set(sidecar['summaries']), {str(row['id']) for row in history['summaries']})
        self.assertNotIn(str(other_row.id), sidecar['summaries'])
        self.assertNotIn('sentinel-foreign-token', first.read(PROVENANCE_MEMBER).decode())
        self.assertNotIn(b'sentinel-token-value', b''.join(first.read(name) for name in first.namelist()))
        self.assertNotIn(b'sentinel-foreign-token', b''.join(first.read(name) for name in first.namelist()))
        self.assertNotIn(b'sentinel-foreign-account-key', b''.join(first.read(name) for name in first.namelist()))
        sidecar_text = first.read(PROVENANCE_MEMBER).decode()
        for hidden_text in ('sentinel-account-key', 'sentinel-external-account', 'sentinel-extra-metadata',
                            'sentinel-conflict-reason', 'sentinel-score-coverage', 'sentinel-future-marker',
                            'account_key', 'source_account_id', 'conflict_reason', 'sleep_minutes'):
            self.assertNotIn(hidden_text, sidecar_text)
        by_id = sidecar['summaries']
        for row in legacy:
            self.assertEqual(by_id[str(row.id)]['provenance_status'], 'legacy_unresolved')
            self.assertEqual(by_id[str(row.id)]['eligibility_status'], 'unresolved')
            self.assertIs(by_id[str(row.id)]['stored_class_verified'], False)
            self.assertNotIn('lineage', by_id[str(row.id)])
        self.assertEqual(by_id[str(legacy[1].id)]['deletion_state'], 'present')
        for row in neighbors:
            self.assertNotEqual(by_id[str(row.id)]['provenance_status'], 'legacy_unresolved')
            self.assertEqual(by_id[str(row.id)]['attribution'], 'no_derived_claim')
        manual_item = by_id[str(manual.id)]
        self.assertEqual(manual_item['attribution'], 'no_derived_claim')
        self.assertNotIn('lineage', manual_item)
        current_item = by_id[str(current.id)]
        self.assertEqual(current_item['derived_status'], 'current')
        self.assertEqual(current_item['calculation'], 'unavailable')
        self.assertEqual(current_item['connection_id'], str(ring.id))
        self.assertIs(current_item['derived_class'], False)
        self.assertEqual(current_item['lineage']['timezone_status'], 'unknown')
        self.assertEqual(current_item['lineage']['contributor_identities_ever'], [current.derivation['contributor_identities_ever'][0]])
        self.assertIsInstance(current_item['lineage']['contributor_identities_ever'][0], str)
        self.assertEqual(current_item['lineage']['current_contributors'][0]['version'], 1)
        self.assertEqual(by_id[str(stale.id)]['lineage']['current_contributors'], [])
        self.assertEqual(by_id[str(conflict.id)]['derived_status'], 'conflict')
        self.assertIs(by_id[str(conflict.id)]['derived_class'], True)
        self.assertNotIn('lineage', by_id[str(invalid.id)])
        self.assertIsNone(by_id[str(invalid.id)]['connection_id'])
        self.assertIsNone(by_id[str(invalid.id)]['derived_class'])
        self.assertEqual(by_id[str(deleted.id)]['deletion_state'], 'deleted')
        self.assertEqual(by_id[str(deleted.id)]['calculation'], 'unavailable')
        self.assertIsNone(by_id[str(foreign.id)]['connection_id'])
        self.assertNotIn('lineage', by_id[str(foreign.id)])
        self.assertEqual(evidence_envelope(foreign)['provenance_status'], 'invalid')
        qualifications = {item['id']: item for item in sidecar['sobriety_pattern']}
        self.assertEqual([item['export_index'] for item in sidecar['sobriety_pattern']], list(range(len(history['sobriety_pattern']))))
        for item in sidecar['sobriety_pattern']:
            original = history['sobriety_pattern'][item['export_index']]
            self.assertEqual(item['local_date'], original['local_date'])
            self.assertEqual(item['formula_version'], original['formula_version'])
            self.assertIs(item['stored_synthetic'], original['synthetic'])
            self.assertNotIn('wear', item)
            self.assertNotIn('drivers', item)
        self.assertEqual(qualifications[str(old.id)]['cache_qualification'], 'historical_unvalidated')
        self.assertEqual(qualifications[str(blank_marker.id)]['cache_qualification'], 'historical_unvalidated')
        self.assertEqual(qualifications[str(malformed.id)]['cache_qualification'], 'historical_unvalidated')
        self.assertEqual(qualifications[str(wrong_type.id)]['cache_qualification'], 'historical_unvalidated')
        self.assertEqual(qualifications[str(future.id)]['cache_qualification'], 'historical_unvalidated')
        self.assertIsNone(qualifications[str(future.id)]['evidence_gate_version'])
        self.assertEqual(qualifications[str(recognized.id)]['cache_qualification'], 'evidence_gate_recorded')
        self.assertEqual(qualifications[str(recognized.id)]['evidence_gate_version'], 'h0-b2')
        self.assertFalse(qualifications[str(recognized.id)]['recomputed'])
        self.assertFalse(qualifications[str(recognized.id)]['validated_at_export'])
        self.assertFalse(qualifications[str(recognized.id)]['clinical_verification'])
        self.assertEqual(sidecar['journal_scores'], 'journal_only')
        readme = first.read('README.txt')
        self.assertTrue(readme.startswith(README_V1))
        self.assertIn(b'historical_unvalidated', readme)
        self.assertIn(b'not a database backup', readme)
        default_history = json.loads(default.read('history.json'))
        default_side = json.loads(default.read(PROVENANCE_MEMBER))
        self.assertFalse(default_history['includes_synthetic'])
        self.assertNotIn(str(legacy[1].id), default_side['summaries'])
        self.assertIn(str(legacy[0].id), default_side['summaries'])
        self.assertNotIn(str(hidden.id), {item['id'] for item in default_side['sobriety_pattern']})
        self.assertEqual(set(default_side['summaries']), {row['id'] for row in default_history['summaries']})

    def test_empty_archive_has_a_sidecar_and_limits_fail_closed(self):
        empty_owner = get_user_model().objects.create_user('synthetic-empty-export')
        with self.export(empty_owner) as archive:
            sidecar = json.loads(archive.read(PROVENANCE_MEMBER))
            self.assertEqual(sidecar['summaries'], {})
            self.assertEqual(sidecar['sobriety_pattern'], [])
            self.assertTrue(archive.read('README.txt').startswith(README_V1))
        self.pattern(self.day, {})
        self.pattern(self.day, {}, formula='sobriety-pattern-0')
        closed = []
        real = tempfile.TemporaryFile

        def wrapped(*args, **kwargs):
            handle = real(*args, **kwargs)
            original = handle.close

            def close():
                closed.append(True)
                return original()

            handle.close = close
            return handle

        materialized = []
        original_fetch = QuerySet._fetch_all

        def traced(query):
            result = original_fetch(query)
            if query.model is SobrietyDay and query._result_cache:
                materialized.append(len(query._result_cache))
            return result

        with patch('tracking.exports.MAX_EXPORT_RECORDS', 1), patch.object(QuerySet, '_fetch_all', traced), patch('tracking.exports.tempfile.TemporaryFile', wrapped):
            with self.assertRaisesRegex(ValueError, 'record limit'):
                build_export(self.owner, True)
        self.assertEqual(materialized, [])
        self.assertTrue(closed)
        with self.export() as archive:
            history_size = len(archive.read('history.json'))
            sidecar_size = len(archive.read(PROVENANCE_MEMBER))
        closed.clear()
        with patch('tracking.exports.MAX_EXPORT_BYTES', history_size + sidecar_size - 1), patch('tracking.exports.tempfile.TemporaryFile', wrapped):
            with self.assertRaisesRegex(ValueError, '512 MiB'):
                build_export(self.owner, True)
        self.assertTrue(closed)

    def test_cache_limit_keeps_owner_class_and_exact_boundary(self):
        empty_owner = get_user_model().objects.create_user('synthetic-empty-cache-limit')
        with patch('tracking.exports.MAX_EXPORT_RECORDS', 0), self.export(empty_owner) as archive:
            self.assertEqual(json.loads(archive.read(PROVENANCE_MEMBER))['sobriety_pattern'], [])
        personal = self.pattern(self.day, {'evidence_gate_version': 'h0-b2'})
        synthetic = self.pattern(self.day, {}, formula='sobriety-pattern-0', synthetic=True)
        foreign = SobrietyDay.objects.create(
            owner=self.other, local_date=self.day, formula_version='foreign-formula', potential='incomplete',
            use_recorded=False, wear={'devices': [{'name': 'other'}]}, drivers=['other-driver'], coverage={},
            synthetic=False)
        with patch('tracking.exports.MAX_EXPORT_RECORDS', 1), self.export(include_synthetic=False) as archive:
            history = json.loads(archive.read('history.json'))['sobriety_pattern']
            items = json.loads(archive.read(PROVENANCE_MEMBER))['sobriety_pattern']
            history_text = archive.read('history.json').decode()
        self.assertEqual([item['id'] for item in items], [str(personal.id)])
        self.assertEqual(items[0]['export_index'], 0)
        self.assertEqual(history[0]['formula_version'], personal.formula_version)
        self.assertNotIn(str(synthetic.id), {item['id'] for item in items})
        self.assertNotIn(str(foreign.id), {item['id'] for item in items})
        self.assertNotIn('other-driver', history_text)
        with patch('tracking.exports.MAX_EXPORT_RECORDS', 2), self.export(include_synthetic=True) as archive:
            items = json.loads(archive.read(PROVENANCE_MEMBER))['sobriety_pattern']
            history = json.loads(archive.read('history.json'))['sobriety_pattern']
        self.assertEqual({item['id'] for item in items}, {str(personal.id), str(synthetic.id)})
        self.assertEqual([item['export_index'] for item in items], [0, 1])
        self.assertEqual([item['formula_version'] for item in items], [row['formula_version'] for row in history])
        self.assertNotIn(str(foreign.id), {item['id'] for item in items})
