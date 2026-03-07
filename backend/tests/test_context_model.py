"""
Tests for context models — LocationContext, NetworkContext, TemporalContext,
DeviceContext, SystemLoadContext, ExecutionContext.
"""

import unittest
from models.context import (
    LocationContext,
    NetworkContext,
    TemporalContext,
)


class TestLocationContext(unittest.TestCase):
    def test_defaults(self):
        loc = LocationContext()
        self.assertEqual(loc.city, "")
        self.assertEqual(loc.country, "")
        self.assertFalse(loc.is_set())

    def test_is_set_with_city(self):
        loc = LocationContext(city="Paris")
        self.assertTrue(loc.is_set())

    def test_to_dict(self):
        loc = LocationContext(city="Algiers", country="Algeria", latitude=36.7, longitude=3.05)
        d = loc.to_dict()
        self.assertEqual(d["city"], "Algiers")
        self.assertEqual(d["country"], "Algeria")

    def test_from_dict(self):
        d = {"city": "London", "country": "UK", "latitude": 51.5, "longitude": -0.12}
        loc = LocationContext.from_dict(d)
        self.assertEqual(loc.city, "London")
        self.assertAlmostEqual(loc.latitude, 51.5)

    def test_from_dict_none(self):
        loc = LocationContext.from_dict(None)
        self.assertEqual(loc.city, "")


class TestNetworkContext(unittest.TestCase):
    def test_defaults(self):
        net = NetworkContext()
        self.assertEqual(net.network_type, "unknown")
        self.assertFalse(net.is_set())

    def test_is_set_with_type(self):
        net = NetworkContext(network_type="wifi")
        self.assertTrue(net.is_set())

    def test_to_dict(self):
        net = NetworkContext(network_type="5G", bandwidth_mbps=100.0, latency_ms=5.0)
        d = net.to_dict()
        self.assertEqual(d["network_type"], "5G")
        self.assertAlmostEqual(d["bandwidth_mbps"], 100.0)

    def test_from_dict(self):
        d = {"network_type": "4G", "bandwidth_mbps": 50}
        net = NetworkContext.from_dict(d)
        self.assertEqual(net.network_type, "4G")

    def test_from_dict_none(self):
        net = NetworkContext.from_dict(None)
        self.assertEqual(net.network_type, "unknown")


class TestTemporalContext(unittest.TestCase):
    def test_defaults(self):
        t = TemporalContext()
        self.assertEqual(t.period, "morning")
        self.assertTrue(t.is_business_hours)

    def test_from_now(self):
        t = TemporalContext.from_now()
        self.assertIn(t.period, ("morning", "afternoon", "evening", "night"))
        self.assertIn(t.weekday, range(7))

    def test_to_dict(self):
        t = TemporalContext()
        d = t.to_dict()
        self.assertIn("period", d)
        self.assertIn("is_business_hours", d)


class TestExecutionContext(unittest.TestCase):
    """Tests for the full ExecutionContext dataclass."""

    def test_to_dict(self):
        from models.context import ExecutionContext
        ctx = ExecutionContext()
        d = ctx.to_dict()
        self.assertIn("location", d)
        self.assertIn("network", d)
        self.assertIn("temporal", d)

    def test_to_flat_dict(self):
        from models.context import ExecutionContext
        ctx = ExecutionContext()
        flat = ctx.to_flat_dict()
        self.assertIsInstance(flat, dict)


if __name__ == "__main__":
    unittest.main()
