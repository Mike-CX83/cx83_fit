"""Run with manage.py test tracking after installing the pinned dependencies."""
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.utils import timezone
from .domain import InvalidMeasurement
from .models import Correction, Measurement, WriteRequest
from .services import Conflict, RecordNotFound, list_measurements, put_measurement


class PersistenceTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="synthetic-owner", password="not-a-real-password")
        self.other = get_user_model().objects.create_user(username="synthetic-other", password="not-a-real-password")
        self.payload = {"metric": "weight", "value": "100.125", "unit": "kg", "local_date": "2026-11-05", "synthetic": True}

    def create(self):
        return put_measurement(self.owner, self.payload, str(uuid4()))

    def test_idempotent_create_and_conflicting_reuse(self):
        request_id = str(uuid4())
        result = put_measurement(self.owner, self.payload, request_id)
        self.assertEqual(put_measurement(self.owner, self.payload, request_id), result)
        self.assertEqual(Measurement.objects.count(), 1)
        self.assertEqual(Correction.objects.count(), 1)
        with self.assertRaises(Conflict):
            put_measurement(self.owner, {**self.payload, "value": "101"}, request_id)

    def test_update_roundtrip_audit_and_retry(self):
        created = self.create()
        request_id = str(uuid4())
        updated = put_measurement(self.owner, {**self.payload, "value": "101"}, request_id,
                                  created["id"], expected_version=1, source_system="mcp")
        self.assertEqual(updated["version"], 2)
        self.assertEqual(updated["source_record_id"], created["source_record_id"])
        self.assertEqual(put_measurement(self.owner, {**self.payload, "value": "101"}, request_id,
                                        created["id"], expected_version=1, source_system="mcp"), updated)
        audit = Correction.objects.filter(operation="update").get()
        self.assertEqual(audit.before["value"], "100.125")
        self.assertEqual(audit.actor_source, "mcp")
        self.assertEqual(Measurement.objects.get().value, 101)

    def test_stale_update_rolls_back_request_and_audit(self):
        created = self.create()
        put_measurement(self.owner, {**self.payload, "value": "101"}, str(uuid4()), created["id"], 1)
        with self.assertRaises(Conflict):
            put_measurement(self.owner, {**self.payload, "value": "102"}, str(uuid4()), created["id"], 1)
        self.assertEqual(WriteRequest.objects.count(), 2)
        self.assertEqual(Measurement.objects.get().value, 101)

    def test_owner_isolation_and_authentication(self):
        created = self.create()
        self.assertEqual(list_measurements(self.other, "2026-11-01", "2026-11-06", True)["count"], 0)
        with self.assertRaises(RecordNotFound):
            put_measurement(self.other, self.payload, str(uuid4()), created["id"], 1)
        with self.assertRaises(PermissionError):
            put_measurement(AnonymousUser(), self.payload, str(uuid4()))

    def test_synthetic_is_excluded_by_default(self):
        self.create()
        self.assertEqual(list_measurements(self.owner, "2026-11-01", "2026-11-06")["count"], 0)
        result = list_measurements(self.owner, "2026-11-01", "2026-11-06", True)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["coverage"]["days_with_observations"], 1)

    def test_imported_record_is_read_only(self):
        created = self.create()
        Measurement.objects.filter(id=created["id"]).update(source_system="provider")
        with self.assertRaises(PermissionError):
            put_measurement(self.owner, self.payload, str(uuid4()), created["id"], 1)

    def test_deleted_record_is_not_resurrected(self):
        request_id = str(uuid4())
        created = put_measurement(self.owner, self.payload, request_id)
        Measurement.objects.filter(id=created["id"]).update(deleted_at=timezone.now())
        put_measurement(self.owner, self.payload, request_id)
        self.assertEqual(list_measurements(self.owner, "2026-11-01", "2026-11-06", True)["count"], 0)
        with self.assertRaises(RecordNotFound):
            put_measurement(self.owner, self.payload, str(uuid4()), created["id"], 1)
        self.assertEqual(Measurement.objects.count(), 1)

    def test_synthetic_cannot_become_personal(self):
        created = self.create()
        with self.assertRaises(InvalidMeasurement):
            put_measurement(self.owner, {**self.payload, "synthetic": False}, str(uuid4()), created["id"], 1)

    def test_pagination_and_observation_coverage(self):
        self.create()
        self.create()
        first = list_measurements(self.owner, "2026-11-01", "2026-11-06", True, limit=1)
        second = list_measurements(self.owner, "2026-11-01", "2026-11-06", True, limit=1, offset=1)
        self.assertNotEqual(first["items"][0]["id"], second["items"][0]["id"])
        self.assertEqual(first["next_offset"], 1)
        self.assertIsNone(second["next_offset"])
        self.assertEqual(first["coverage"]["days_with_observations"], 1)

    def test_source_provenance_cannot_be_injected(self):
        with self.assertRaises(InvalidMeasurement):
            put_measurement(self.owner, {**self.payload, "source_record_id": "fake"}, str(uuid4()))
