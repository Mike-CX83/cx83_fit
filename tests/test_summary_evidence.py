"""Phase A evidence contract. Fabricated rows only. Reads must not refresh or rewrite history."""
import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from tracking.models import OuraConnection, SummaryRecord
from tracking.projection_identity import legacy_candidate, stable_source_id
from tracking.reads import read_overview, read_tracking
from tracking.summary_evidence import (
    evidence_counts, evidence_envelope, legacy_candidate as shared_legacy, resolve_metric, unresolved_history,
)


class SummaryEvidenceTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('synthetic-owner')
        self.other = get_user_model().objects.create_user('synthetic-other-owner')
        self.day = timezone.localdate()
        self.sequence = 0

    def record(self, owner=None, **changes):
        owner = self.owner if owner is None else owner
        values = {'steps': '4', 'active_calories': '1', 'total_calories': '1', 'workout_minutes': None, 'workout_summary': ''}
        self.sequence += 1
        fields = {
            'owner': owner, 'kind': 'activity', 'local_date': self.day - timedelta(days=self.sequence),
            'source_timezone': 'America/Chicago',
            'source_system': 'oura', 'source_record_id': uuid4().hex, 'entry_method': 'imported', 'device': 'Oura',
            'completeness': 'partial', 'values': values, 'synthetic': False,
        }
        fields.update(changes)
        return SummaryRecord.objects.create(**fields)

    def derived(self, owner, synthetic, status, day=None, steps='9'):
        day = self.day if day is None else day
        ring = OuraConnection.objects.create(
            owner=owner, account_key=f'fabricated-{uuid4().hex[:12]}', source_account_id='fabricated-external-account',
            synthetic=synthetic, token_ciphertext='fabricated-token-value', state='disconnected')
        raw_id = str(uuid4())
        ever = [{'raw_id': raw_id, 'identity_key': 'ab' * 32, 'collection': 'daily_activity',
                 'source_record_id': 'fabricated-provider'}]
        current = [] if status != 'current' else [{**ever[0], 'version': 1}]
        schema = [] if status == 'invalid' else 2
        stored_status = 'current' if status == 'invalid' else status
        derivation = {
            'schema_version': schema, 'recipe_version': 1, 'account_id': str(ring.id), 'timezone_status': 'unknown',
            'status': stored_status, 'quality': stored_status, 'current_contributors': current,
            'contributor_identities_ever': ever, 'conflict_reason': '',
        }
        return SummaryRecord.objects.create(
            owner=owner, kind='activity', local_date=day, source_timezone='', source_system='oura',
            source_record_id=stable_source_id(ring, 'activity', day), entry_method='derived', device='Oura',
            completeness='partial', values={'steps': steps, 'active_calories': '1', 'total_calories': '1'},
            synthetic=synthetic, connection=ring, derivation=derivation)

    def test_exact_predicate_matches_the_accepted_helper_and_excludes_neighbors(self):
        legacy = [self.record(synthetic=flag) for flag in (False, True)]
        neighbors = [
            self.record(entry_method='manually_reported', source_record_id='manual-oura'),
            self.record(source_system='csv:oura', source_record_id='csv-oura'),
            self.record(kind='nutrition', source_record_id='nutrition-oura', values={'calories': '1'}),
            self.record(kind='health', source_record_id='health-import', values={'name': 'Synthetic', 'value': '1'}),
            self.record(source_system='synthetic-source', entry_method='imported', source_record_id='other-import'),
        ]
        for row in legacy:
            self.assertIs(shared_legacy(row), True)
            self.assertIs(legacy_candidate(row), True)
            envelope = evidence_envelope(row)
            self.assertEqual(envelope['provenance_status'], 'legacy_unresolved')
            self.assertEqual(envelope['eligibility_status'], 'unresolved')
            self.assertNotEqual(envelope['eligibility_reason'], 'corrupt')
            self.assertIs(envelope['stored_class_verified'], False)
            self.assertIsNone(envelope['connection_id'])
        for row in neighbors:
            self.assertIs(shared_legacy(row), False)
            self.assertIs(legacy_candidate(row), False)
            self.assertNotEqual(evidence_envelope(row)['provenance_status'], 'legacy_unresolved')

    def test_derived_statuses_stay_unavailable_and_distinct(self):
        rows = {status: self.derived(self.owner, status == 'conflict', status, self.day - timedelta(days=index))
                for index, status in enumerate(('current', 'stale', 'conflict', 'invalid'))}
        seen = []
        for status, row in rows.items():
            envelope = evidence_envelope(row)
            seen.append((envelope['derived_status'], envelope['eligibility_status'], envelope['calculation'],
                         envelope['stored_class_verified'], envelope['connection_id']))
            self.assertEqual(envelope['eligibility_status'], 'unavailable')
            self.assertEqual(envelope['calculation'], 'unavailable')
            self.assertNotIn('account_key', json.dumps(envelope))
            self.assertNotIn('fabricated-external-account', json.dumps(envelope))
            self.assertNotIn('fabricated-token-value', json.dumps(envelope))
        self.assertEqual(seen[0][0], 'current')
        self.assertEqual(seen[1][0], 'stale')
        self.assertEqual(seen[2][0], 'conflict')
        self.assertEqual(seen[3][0], 'invalid')
        self.assertIs(seen[0][3], True)
        self.assertIs(seen[3][3], False)
        self.assertIsNone(seen[3][4])

    def test_metric_resolution_keeps_zero_and_refuses_a_winner(self):
        zero = self.record(source_system='manual', entry_method='manually_reported', source_record_id='zero',
                           values={'steps': '0'})
        unknown = self.record(source_system='manual', entry_method='manually_reported', source_record_id='unknown',
                              local_date=self.day - timedelta(days=3), values={'steps': None})
        other = self.record(source_system='csv:oura', entry_method='imported', source_record_id='same-zero',
                            local_date=self.day - timedelta(days=4), values={'steps': '0'})
        legacy = self.record(source_record_id='legacy-steps', local_date=self.day - timedelta(days=5), values={'steps': '99'})
        with patch('tracking.projection_identity.refresh_stored_sources', side_effect=AssertionError('refresh called')):
            self.assertEqual(resolve_metric([zero], 'steps')['value'], '0')
            self.assertEqual(resolve_metric([unknown], 'steps')['status'], 'unavailable')
            self.assertIsNone(resolve_metric([unknown], 'steps')['value'])
            competing = resolve_metric([zero, other, legacy], 'steps')
        self.assertEqual(competing['status'], 'selection_required')
        self.assertIsNone(competing['value'])
        self.assertEqual([item['value'] for item in competing['alternatives']], ['0', '0'])
        self.assertEqual(competing['excluded'][0]['eligibility_reason'], 'legacy_unresolved')

    def test_history_counts_do_not_treat_the_newest_unresolved_row_as_fresh(self):
        self.record(source_system='manual', entry_method='manually_reported', source_record_id='older-manual',
                    local_date=self.day - timedelta(days=2), values={'steps': '5'})
        self.record(source_record_id='newer-legacy', local_date=self.day, values={'steps': '80'})
        self.derived(self.other, False, 'current')
        window = SummaryRecord.objects.filter(owner=self.owner, deleted_at__isnull=True)
        with CaptureQueriesContext(connection) as captured:
            counts = evidence_counts(window)
            tracked = read_tracking(self.owner, 'activity', self.day - timedelta(days=3), self.day, True)
            overview = read_overview(self.owner, self.day - timedelta(days=3), self.day, True)
        self.assertFalse(any(item['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'REPLACE')) for item in captured))
        self.assertEqual(counts['eligible_count'], 1)
        self.assertEqual(counts['unresolved_count'], 1)
        self.assertEqual(counts['eligible_latest_date'], (self.day - timedelta(days=2)).isoformat())
        self.assertEqual(counts['historical_latest_date'], self.day.isoformat())
        self.assertEqual(tracked['count'], 2)
        self.assertEqual(tracked['coverage']['eligible_count'], 1)
        self.assertEqual(tracked['coverage']['unresolved_count'], 1)
        self.assertEqual(overview['evidence']['eligible_latest_date'], counts['eligible_latest_date'])
        self.assertEqual(overview['sections']['activity']['count'], 2)
        self.assertNotEqual(overview['evidence']['eligible_latest_date'], overview['evidence']['historical_latest_date'])
        self.assertFalse(unresolved_history(self.owner).filter(owner=self.other).exists())
        self.assertEqual(unresolved_history(self.other).count(), 1)
