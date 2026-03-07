"""
Tests for InteractionHistoryStore — recording, stats, persistence.
"""

import os
import json
import tempfile
import unittest
from models.interaction_history import InteractionHistoryStore, InteractionRecord


class TestInteractionRecord(unittest.TestCase):
    def test_creation(self):
        r = InteractionRecord(service_id="s1", composition_id="c1", success=True, utility=0.8)
        self.assertEqual(r.service_id, "s1")
        self.assertEqual(r.composition_id, "c1")
        self.assertTrue(r.success)

    def test_to_dict(self):
        r = InteractionRecord(service_id="s1", utility=0.5)
        d = r.to_dict()
        self.assertIn("service_id", d)
        self.assertIn("timestamp", d)
        self.assertIn("utility", d)

    def test_from_dict(self):
        d = {"service_id": "s1", "composition_id": "c1", "success": False, "utility": 0.3}
        r = InteractionRecord.from_dict(d)
        self.assertEqual(r.service_id, "s1")
        self.assertFalse(r.success)


class TestInteractionHistoryStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self.tmp.write("[]")
        self.tmp.close()
        self.store = InteractionHistoryStore(path=self.tmp.name)

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            os.remove(self.tmp.name)

    def test_record_and_count(self):
        rec = InteractionRecord(service_id="s1", composition_id="c1")
        self.store.record(rec)
        count = self.store.get_interaction_count("s1")
        self.assertEqual(count, 1)

    def test_summary(self):
        s = self.store.summary()
        self.assertIn("total_records", s)

    def test_success_rate_no_records(self):
        rate = self.store.get_success_rate("nonexistent")
        self.assertEqual(rate, 0.0)

    def test_avg_utility_no_records(self):
        avg = self.store.get_avg_utility("nonexistent")
        self.assertEqual(avg, 0.0)

    def test_clear(self):
        self.store.record(InteractionRecord(service_id="s1"))
        self.store.clear()
        self.assertEqual(self.store.get_interaction_count("s1"), 0)

    def test_persistence(self):
        self.store.record(InteractionRecord(service_id="s1", utility=0.9))
        # Reload from same file
        store2 = InteractionHistoryStore(path=self.tmp.name)
        self.assertEqual(store2.get_interaction_count("s1"), 1)

    def test_collaboration_counts(self):
        self.store.record(InteractionRecord(
            service_id="s1", co_services=["s2", "s3"]
        ))
        collabs = self.store.get_collaboration_counts("s1")
        self.assertIsInstance(collabs, dict)


if __name__ == "__main__":
    unittest.main()
