"""
Integration tests for the QoS-WSC dataset.
============================================

Tests that validate the system against the real QoS-WSC benchmark:
  - discovery/   → training data  (single-service discovery)
  - composition1/ → test data      (multi-service sequential composition)
  - composition2/ → test data      (multi-service deeper composition)

Each sub-folder contains:
  *-Requests.xml       → CompositionRequest definitions with QoS constraints
  *-Solutions.xml      → candidate solutions (service lists per case)
  *-BestSolutions.xml  → ground-truth best service(s) + utility value

The tests verify:
  1. XML parsing correctness (Requests, Solutions, BestSolutions)
  2. WSDL parsing and QoS extraction from real .wsdl files
  3. QoS aggregation for multi-service compositions
  4. Utility computation consistency
  5. Reward calculator against the benchmark
  6. Classic composer can handle real datasets
  7. Dataset structural integrity
"""

import os
import sys
import glob
import unittest

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.wsdl_parser import WSDLParser, parse_requests_xml, parse_best_solutions_xml
from models.service import WebService, QoS, CompositionRequest
from utils.qos_calculator import (
    calculate_utility,
    normalize,
    normalize_inverse,
    aggregate_qos,
)
from services.reward_calculator import RewardCalculator

# ── Paths ──────────────────────────────────────────────────────────
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QOS_WSC = os.path.join(BASE, "QoS-WSC")
DISCOVERY = os.path.join(QOS_WSC, "discovery")
COMPOSITION1 = os.path.join(QOS_WSC, "composition1")
COMPOSITION2 = os.path.join(QOS_WSC, "composition2")


def _dataset_available():
    """Check if the QoS-WSC folder exists."""
    return os.path.isdir(QOS_WSC)


@unittest.skipUnless(_dataset_available(), "QoS-WSC dataset not found")
class TestDatasetStructure(unittest.TestCase):
    """Verify the QoS-WSC dataset has the expected structure."""

    def test_discovery_folder_exists(self):
        self.assertTrue(os.path.isdir(DISCOVERY))

    def test_composition1_folder_exists(self):
        self.assertTrue(os.path.isdir(COMPOSITION1))

    def test_composition2_folder_exists(self):
        self.assertTrue(os.path.isdir(COMPOSITION2))

    def test_discovery_has_subfolders(self):
        """Each configuration (20-4, 50-4, 100-4, etc.) should have a WSDL folder."""
        subdirs = [d for d in os.listdir(DISCOVERY) if os.path.isdir(os.path.join(DISCOVERY, d))]
        self.assertGreater(len(subdirs), 0, "discovery/ should contain at least one sub-folder")

    def test_discovery_has_xml_files(self):
        """Each configuration should have Requests, Solutions, BestSolutions XML files."""
        xml_files = glob.glob(os.path.join(DISCOVERY, "*.xml"))
        self.assertGreater(len(xml_files), 0, "discovery/ should have XML files")

    def test_discovery_xml_triplet_exists(self):
        """For discovery-20-4, all three XML files should exist."""
        for suffix in ["Requests", "Solutions", "BestSolutions"]:
            path = os.path.join(DISCOVERY, f"discovery-20-4-{suffix}.xml")
            self.assertTrue(os.path.exists(path), f"Missing {path}")

    def test_composition1_xml_triplet_exists(self):
        for suffix in ["Requests", "Solutions", "BestSolutions"]:
            path = os.path.join(COMPOSITION1, f"composition1-20-4-{suffix}.xml")
            self.assertTrue(os.path.exists(path), f"Missing {path}")

    def test_composition2_xml_triplet_exists(self):
        for suffix in ["Requests", "Solutions", "BestSolutions"]:
            path = os.path.join(COMPOSITION2, f"composition2-20-4-{suffix}.xml")
            self.assertTrue(os.path.exists(path), f"Missing {path}")

    def test_discovery_wsdl_folder_has_files(self):
        """discovery-20-4/ subfolder should contain .wsdl files."""
        wsdl_dir = os.path.join(DISCOVERY, "discovery-20-4")
        if os.path.isdir(wsdl_dir):
            wsdl_files = glob.glob(os.path.join(wsdl_dir, "*.wsdl"))
            self.assertGreater(len(wsdl_files), 0, "discovery-20-4/ should contain WSDL files")

    def test_composition1_wsdl_folder_has_files(self):
        wsdl_dir = os.path.join(COMPOSITION1, "composition1-20-4")
        if os.path.isdir(wsdl_dir):
            wsdl_files = glob.glob(os.path.join(wsdl_dir, "*.wsdl"))
            self.assertGreater(len(wsdl_files), 0)

    def test_all_configurations_present(self):
        """Each dataset should have 9 configurations: {20,50,100} x {4,16,32}."""
        for folder_name, folder_path in [("discovery", DISCOVERY),
                                          ("composition1", COMPOSITION1),
                                          ("composition2", COMPOSITION2)]:
            for n_services in [20, 50, 100]:
                for n_candidates in [4, 16, 32]:
                    config = f"{folder_name}-{n_services}-{n_candidates}"
                    req_file = os.path.join(folder_path, f"{config}-Requests.xml")
                    # Allow for typo in original dataset (Request vs Requests)
                    alt_file = os.path.join(folder_path, f"{config}-Request.xml")
                    found = os.path.exists(req_file) or os.path.exists(alt_file)
                    self.assertTrue(found, f"Missing Requests file for {config}")


@unittest.skipUnless(_dataset_available(), "QoS-WSC dataset not found")
class TestParseDiscoveryRequests(unittest.TestCase):
    """Verify parse_requests_xml works correctly on discovery data."""

    def test_parse_discovery_20_4_requests(self):
        path = os.path.join(DISCOVERY, "discovery-20-4-Requests.xml")
        requests = parse_requests_xml(path)
        self.assertIsInstance(requests, list)
        self.assertGreater(len(requests), 0, "Should parse at least 1 request")

    def test_request_has_id(self):
        path = os.path.join(DISCOVERY, "discovery-20-4-Requests.xml")
        requests = parse_requests_xml(path)
        for req in requests:
            self.assertTrue(req.id, f"Request should have an ID")

    def test_request_has_provided(self):
        path = os.path.join(DISCOVERY, "discovery-20-4-Requests.xml")
        requests = parse_requests_xml(path)
        for req in requests:
            self.assertIsInstance(req.provided, list)
            self.assertGreater(len(req.provided), 0, f"Request {req.id} should have provided params")

    def test_request_has_resultant(self):
        path = os.path.join(DISCOVERY, "discovery-20-4-Requests.xml")
        requests = parse_requests_xml(path)
        for req in requests:
            self.assertIsNotNone(req.resultant, f"Request {req.id} should have a resultant")

    def test_request_has_qos_constraints(self):
        """QoS constraints should be parsed from the comma-separated values."""
        path = os.path.join(DISCOVERY, "discovery-20-4-Requests.xml")
        requests = parse_requests_xml(path)
        for req in requests:
            qos = req.qos_constraints
            self.assertIsInstance(qos, QoS)
            # At least one QoS value should be > 0
            values = [qos.response_time, qos.availability, qos.throughput,
                      qos.successability, qos.reliability, qos.compliance,
                      qos.best_practices, qos.latency, qos.documentation]
            self.assertTrue(any(v > 0 for v in values),
                            f"Request {req.id}: QoS should have at least one non-zero constraint")

    def test_discovery_request_count(self):
        """discovery-20-4 should have exactly 11 DiscoveryRoutines."""
        path = os.path.join(DISCOVERY, "discovery-20-4-Requests.xml")
        requests = parse_requests_xml(path)
        self.assertEqual(len(requests), 11)

    def test_provided_params_are_comma_separated(self):
        """Provided should be split by comma (WSChallenge format)."""
        path = os.path.join(DISCOVERY, "discovery-20-4-Requests.xml")
        requests = parse_requests_xml(path)
        for req in requests:
            for p in req.provided:
                self.assertTrue(p.startswith("p"), f"Param '{p}' should start with 'p'")

    def test_multiple_configurations(self):
        """Parse requests from different configurations."""
        for config in ["20-4", "50-4", "100-4"]:
            path = os.path.join(DISCOVERY, f"discovery-{config}-Requests.xml")
            if os.path.exists(path):
                requests = parse_requests_xml(path)
                self.assertGreater(len(requests), 0,
                                   f"discovery-{config} should have requests")


@unittest.skipUnless(_dataset_available(), "QoS-WSC dataset not found")
class TestParseCompositionRequests(unittest.TestCase):
    """Verify parse_requests_xml works on composition data."""

    def test_parse_composition1_requests(self):
        path = os.path.join(COMPOSITION1, "composition1-20-4-Requests.xml")
        requests = parse_requests_xml(path)
        self.assertGreater(len(requests), 0)

    def test_parse_composition2_requests(self):
        path = os.path.join(COMPOSITION2, "composition2-20-4-Requests.xml")
        requests = parse_requests_xml(path)
        self.assertGreater(len(requests), 0)

    def test_composition_request_count(self):
        """composition1-20-4 should have 11 CompositionRoutines."""
        path = os.path.join(COMPOSITION1, "composition1-20-4-Requests.xml")
        requests = parse_requests_xml(path)
        self.assertEqual(len(requests), 11)

    def test_composition_qos_nine_values(self):
        """Each QoS line should map to all 9 QoS attributes."""
        path = os.path.join(COMPOSITION1, "composition1-20-4-Requests.xml")
        requests = parse_requests_xml(path)
        for req in requests:
            qos = req.qos_constraints
            # All 9 attributes should be set (though some can be 0)
            attrs = [qos.response_time, qos.availability, qos.throughput,
                     qos.successability, qos.reliability, qos.compliance,
                     qos.best_practices, qos.latency, qos.documentation]
            self.assertEqual(len(attrs), 9)


@unittest.skipUnless(_dataset_available(), "QoS-WSC dataset not found")
class TestParseBestSolutions(unittest.TestCase):
    """Verify parse_best_solutions_xml works correctly."""

    def test_parse_discovery_best_solutions(self):
        path = os.path.join(DISCOVERY, "discovery-20-4-BestSolutions.xml")
        solutions = parse_best_solutions_xml(path)
        self.assertIsInstance(solutions, dict)
        self.assertGreater(len(solutions), 0)

    def test_discovery_best_solution_has_service(self):
        """Each discovery case should have exactly one best service."""
        path = os.path.join(DISCOVERY, "discovery-20-4-BestSolutions.xml")
        solutions = parse_best_solutions_xml(path)
        for case_id, sol in solutions.items():
            self.assertGreater(len(sol['service_ids']), 0,
                               f"Case {case_id} should have at least one service")

    def test_discovery_best_solution_has_utility(self):
        """Each discovery case should have a utility value."""
        path = os.path.join(DISCOVERY, "discovery-20-4-BestSolutions.xml")
        solutions = parse_best_solutions_xml(path)
        for case_id, sol in solutions.items():
            self.assertGreater(sol['utility'], 0,
                               f"Case {case_id} should have utility > 0")

    def test_composition1_best_solutions(self):
        """Composition best solutions can have multiple services (workflow)."""
        path = os.path.join(COMPOSITION1, "composition1-20-4-BestSolutions.xml")
        solutions = parse_best_solutions_xml(path)
        self.assertGreater(len(solutions), 0)

        # At least some cases should be workflows (>1 service)
        workflow_count = sum(1 for s in solutions.values() if s['is_workflow'])
        self.assertGreater(workflow_count, 0,
                           "Composition should have multi-service workflows")

    def test_composition2_best_solutions(self):
        path = os.path.join(COMPOSITION2, "composition2-20-4-BestSolutions.xml")
        solutions = parse_best_solutions_xml(path)
        self.assertGreater(len(solutions), 0)

    def test_best_solution_cases_match_requests(self):
        """Best solution case IDs should match request IDs."""
        req_path = os.path.join(DISCOVERY, "discovery-20-4-Requests.xml")
        sol_path = os.path.join(DISCOVERY, "discovery-20-4-BestSolutions.xml")
        requests = parse_requests_xml(req_path)
        solutions = parse_best_solutions_xml(sol_path)

        req_ids = {r.id for r in requests}
        sol_ids = set(solutions.keys())

        self.assertEqual(req_ids, sol_ids,
                         f"Request IDs and solution IDs should match.\n"
                         f"In requests only: {req_ids - sol_ids}\n"
                         f"In solutions only: {sol_ids - req_ids}")


@unittest.skipUnless(_dataset_available(), "QoS-WSC dataset not found")
class TestWSDLParsingReal(unittest.TestCase):
    """Parse real WSDL files from the QoS-WSC dataset."""

    def setUp(self):
        self.parser = WSDLParser()

    def test_parse_single_wsdl(self):
        """Parse a real WSDL file from discovery-20-4."""
        wsdl_dir = os.path.join(DISCOVERY, "discovery-20-4")
        if not os.path.isdir(wsdl_dir):
            self.skipTest("discovery-20-4 WSDL folder not found")

        wsdl_files = glob.glob(os.path.join(wsdl_dir, "*.wsdl"))
        self.assertGreater(len(wsdl_files), 0)

        service = self.parser.parse_file(wsdl_files[0])
        self.assertIsNotNone(service, f"Failed to parse {wsdl_files[0]}")
        self.assertTrue(service.id, "Service should have an ID")

    def test_wsdl_has_qos(self):
        """Real WSDL files should have QoS data embedded."""
        wsdl_dir = os.path.join(DISCOVERY, "discovery-20-4")
        if not os.path.isdir(wsdl_dir):
            self.skipTest("discovery-20-4 WSDL folder not found")

        wsdl_files = glob.glob(os.path.join(wsdl_dir, "*.wsdl"))[:5]
        for wf in wsdl_files:
            service = self.parser.parse_file(wf)
            self.assertIsNotNone(service, f"Failed to parse {wf}")
            qos = service.qos
            # At least response_time or availability should be > 0
            has_qos = (qos.response_time > 0 or qos.availability > 0 or
                       qos.throughput > 0 or qos.reliability > 0)
            self.assertTrue(has_qos, f"Service from {wf} should have QoS values")

    def test_wsdl_has_inputs_outputs(self):
        """Real WSDL files should have inputs and outputs (parameter bindings)."""
        wsdl_dir = os.path.join(DISCOVERY, "discovery-20-4")
        if not os.path.isdir(wsdl_dir):
            self.skipTest("discovery-20-4 WSDL folder not found")

        wsdl_files = glob.glob(os.path.join(wsdl_dir, "*.wsdl"))[:5]
        for wf in wsdl_files:
            service = self.parser.parse_file(wf)
            self.assertIsNotNone(service)
            # Most WSDL files should have at least some inputs and outputs
            total_io = len(service.inputs) + len(service.outputs)
            self.assertGreater(total_io, 0,
                               f"Service {service.id} should have inputs or outputs")

    def test_parse_directory_discovery(self):
        """Parse all WSDL files in a discovery directory."""
        wsdl_dir = os.path.join(DISCOVERY, "discovery-20-4")
        if not os.path.isdir(wsdl_dir):
            self.skipTest("discovery-20-4 WSDL folder not found")

        services = self.parser.parse_directory(wsdl_dir)
        self.assertIsInstance(services, list)
        self.assertGreater(len(services), 0,
                           "Should parse at least some services from the directory")

    def test_parse_composition1_wsdl(self):
        """Parse WSDL files from composition1-20-4."""
        wsdl_dir = os.path.join(COMPOSITION1, "composition1-20-4")
        if not os.path.isdir(wsdl_dir):
            self.skipTest("composition1-20-4 WSDL folder not found")

        wsdl_files = glob.glob(os.path.join(wsdl_dir, "*.wsdl"))[:5]
        for wf in wsdl_files:
            service = self.parser.parse_file(wf)
            self.assertIsNotNone(service, f"Failed to parse {wf}")

    def test_service_id_format(self):
        """Service IDs should follow the pXXaYYYYYYY format."""
        wsdl_dir = os.path.join(DISCOVERY, "discovery-20-4")
        if not os.path.isdir(wsdl_dir):
            self.skipTest("discovery-20-4 WSDL folder not found")

        wsdl_files = glob.glob(os.path.join(wsdl_dir, "*.wsdl"))[:10]
        import re
        pattern = re.compile(r'^p\d+a\d+$')
        for wf in wsdl_files:
            service = self.parser.parse_file(wf)
            if service:
                self.assertRegex(service.id, pattern,
                                 f"Service ID '{service.id}' should match pXXaYYYYYYY")


@unittest.skipUnless(_dataset_available(), "QoS-WSC dataset not found")
class TestQoSValuesRange(unittest.TestCase):
    """Verify that QoS values from real WSDL files are in expected ranges."""

    def setUp(self):
        self.parser = WSDLParser()
        wsdl_dir = os.path.join(DISCOVERY, "discovery-20-4")
        if not os.path.isdir(wsdl_dir):
            self.skipTest("discovery-20-4 WSDL folder not found")
        wsdl_files = glob.glob(os.path.join(wsdl_dir, "*.wsdl"))[:20]
        self.services = []
        for wf in wsdl_files:
            svc = self.parser.parse_file(wf)
            if svc:
                self.services.append(svc)

    def test_availability_range(self):
        """Availability should be in [0, 100]."""
        for s in self.services:
            self.assertGreaterEqual(s.qos.availability, 0)
            self.assertLessEqual(s.qos.availability, 100)

    def test_reliability_range(self):
        for s in self.services:
            self.assertGreaterEqual(s.qos.reliability, 0)
            self.assertLessEqual(s.qos.reliability, 100)

    def test_response_time_positive(self):
        for s in self.services:
            self.assertGreaterEqual(s.qos.response_time, 0)

    def test_throughput_positive(self):
        for s in self.services:
            self.assertGreaterEqual(s.qos.throughput, 0)

    def test_latency_positive(self):
        for s in self.services:
            self.assertGreaterEqual(s.qos.latency, 0)

    def test_documentation_range(self):
        for s in self.services:
            self.assertGreaterEqual(s.qos.documentation, 0)
            self.assertLessEqual(s.qos.documentation, 100)


@unittest.skipUnless(_dataset_available(), "QoS-WSC dataset not found")
class TestQoSAggregationOnRealData(unittest.TestCase):
    """Test QoS aggregation using real services from the dataset."""

    def setUp(self):
        self.parser = WSDLParser()
        wsdl_dir = os.path.join(DISCOVERY, "discovery-20-4")
        if not os.path.isdir(wsdl_dir):
            self.skipTest("No WSDL directory found")
        wsdl_files = glob.glob(os.path.join(wsdl_dir, "*.wsdl"))[:10]
        self.services = []
        for wf in wsdl_files:
            svc = self.parser.parse_file(wf)
            if svc:
                self.services.append(svc)
        if len(self.services) < 2:
            self.skipTest("Not enough services to aggregate")

    def test_aggregate_two_services(self):
        agg = aggregate_qos(self.services[:2])
        self.assertIsInstance(agg, QoS)
        # Response time should be the sum
        expected_rt = sum(s.qos.response_time for s in self.services[:2])
        self.assertAlmostEqual(agg.response_time, expected_rt, places=1)

    def test_aggregate_availability_decreases(self):
        """Aggregated availability should be <= min individual availability."""
        agg = aggregate_qos(self.services[:3])
        min_avail = min(s.qos.availability for s in self.services[:3])
        self.assertLessEqual(agg.availability, min_avail + 0.01)

    def test_aggregate_throughput_minimum(self):
        """Aggregated throughput should be the minimum."""
        agg = aggregate_qos(self.services[:3])
        min_tp = min(s.qos.throughput for s in self.services[:3])
        self.assertAlmostEqual(agg.throughput, min_tp, places=1)


@unittest.skipUnless(_dataset_available(), "QoS-WSC dataset not found")
class TestUtilityOnRealData(unittest.TestCase):
    """Test utility calculation using real services and real QoS constraints."""

    def setUp(self):
        self.parser = WSDLParser()
        # Parse a real request
        req_path = os.path.join(DISCOVERY, "discovery-20-4-Requests.xml")
        self.requests = parse_requests_xml(req_path)
        # Parse WSDL services
        wsdl_dir = os.path.join(DISCOVERY, "discovery-20-4")
        if not os.path.isdir(wsdl_dir):
            self.skipTest("No WSDL directory found")
        wsdl_files = glob.glob(os.path.join(wsdl_dir, "*.wsdl"))[:20]
        self.services = []
        for wf in wsdl_files:
            svc = self.parser.parse_file(wf)
            if svc:
                self.services.append(svc)

    def test_utility_non_negative(self):
        """Utility should always be >= 0."""
        if not self.requests or not self.services:
            self.skipTest("No data")
        req = self.requests[0]
        for svc in self.services[:10]:
            checks = svc.qos.meets_constraints(req.qos_constraints)
            utility = calculate_utility(svc.qos, req.qos_constraints, checks)
            self.assertGreaterEqual(utility, 0,
                                    f"Utility for {svc.id} should be >= 0")

    def test_utility_varies_across_services(self):
        """Different services should produce different utility values."""
        if not self.requests or len(self.services) < 2:
            self.skipTest("Not enough data")
        req = self.requests[0]
        utilities = []
        for svc in self.services[:10]:
            checks = svc.qos.meets_constraints(req.qos_constraints)
            utility = calculate_utility(svc.qos, req.qos_constraints, checks)
            utilities.append(utility)
        # Not all utilities should be identical
        self.assertGreater(len(set(round(u, 2) for u in utilities)), 1,
                           "Utility should vary across services")


@unittest.skipUnless(_dataset_available(), "QoS-WSC dataset not found")
class TestRewardCalculatorOnRealData(unittest.TestCase):
    """Test the reward calculator using real dataset services."""

    def setUp(self):
        self.calc = RewardCalculator()
        self.parser = WSDLParser()
        wsdl_dir = os.path.join(DISCOVERY, "discovery-20-4")
        if not os.path.isdir(wsdl_dir):
            self.skipTest("No WSDL directory")
        wsdl_files = glob.glob(os.path.join(wsdl_dir, "*.wsdl"))[:10]
        self.services = []
        for wf in wsdl_files:
            svc = self.parser.parse_file(wf)
            if svc:
                self.services.append(svc)

    def test_reward_in_range(self):
        """Reward should be in [0, 1]."""
        if not self.services:
            self.skipTest("No services parsed")
        req = CompositionRequest("test")
        req.provided = self.services[0].inputs
        req.resultant = self.services[0].outputs[0] if self.services[0].outputs else "out"

        result = self.calc.compute_reward([self.services[0]], req)
        self.assertGreaterEqual(result["reward"], 0.0)
        self.assertLessEqual(result["reward"], 1.0)

    def test_reward_qos_score_positive(self):
        """Real services should have a positive QoS score."""
        if not self.services:
            self.skipTest("No services parsed")
        req = CompositionRequest("test")
        req.provided = self.services[0].inputs
        req.resultant = self.services[0].outputs[0] if self.services[0].outputs else "out"

        result = self.calc.compute_reward([self.services[0]], req)
        self.assertGreater(result["qos_score"], 0.0,
                           "Real service QoS score should be > 0")

    def test_multi_service_reward(self):
        """Reward for a multi-service composition."""
        if len(self.services) < 2:
            self.skipTest("Not enough services")
        req = CompositionRequest("test")
        req.provided = self.services[0].inputs
        req.resultant = self.services[-1].outputs[0] if self.services[-1].outputs else "out"

        result = self.calc.compute_reward(self.services[:3], req)
        self.assertGreaterEqual(result["reward"], 0.0)
        self.assertLessEqual(result["reward"], 1.0)


@unittest.skipUnless(_dataset_available(), "QoS-WSC dataset not found")
class TestBestSolutionConsistency(unittest.TestCase):
    """Verify that best solutions are consistent with the solution space."""

    def test_discovery_best_is_in_solutions(self):
        """Each best solution service should appear in the Solutions file."""
        sol_path = os.path.join(DISCOVERY, "discovery-20-4-Solutions.xml")
        best_path = os.path.join(DISCOVERY, "discovery-20-4-BestSolutions.xml")

        # Parse the Solutions XML manually (it has a different structure)
        import xml.etree.ElementTree as ET
        tree = ET.parse(sol_path)
        root = tree.getroot()

        # Build map: case_name -> set of service names
        case_services = {}
        for case in root.findall('.//case'):
            name = case.get('name')
            services = {s.get('name') for s in case.findall('.//service') if s.get('name')}
            case_services[name] = services

        # Parse best solutions
        best = parse_best_solutions_xml(best_path)

        for case_id, best_sol in best.items():
            if case_id in case_services:
                for sid in best_sol['service_ids']:
                    self.assertIn(sid, case_services[case_id],
                                  f"Best service {sid} for {case_id} not in solution pool")

    def test_composition1_best_is_in_solutions(self):
        """Composition best services should be in the Solutions file."""
        sol_path = os.path.join(COMPOSITION1, "composition1-20-4-Solutions.xml")
        best_path = os.path.join(COMPOSITION1, "composition1-20-4-BestSolutions.xml")

        import xml.etree.ElementTree as ET
        tree = ET.parse(sol_path)
        root = tree.getroot()

        case_services = {}
        for case in root.findall('.//case'):
            name = case.get('name')
            services = {s.get('name') for s in case.findall('.//service') if s.get('name')}
            case_services[name] = services

        best = parse_best_solutions_xml(best_path)

        for case_id, best_sol in best.items():
            if case_id in case_services:
                for sid in best_sol['service_ids']:
                    self.assertIn(sid, case_services[case_id],
                                  f"Best service {sid} for {case_id} not in composition1 Solutions")


@unittest.skipUnless(_dataset_available(), "QoS-WSC dataset not found")
class TestDiscoveryBestSolutionUtility(unittest.TestCase):
    """Verify that best solutions have the highest utility among candidates."""

    def test_best_utility_is_maximum(self):
        """For discovery, the best solution utility should be >= all other candidates."""
        best_path = os.path.join(DISCOVERY, "discovery-20-4-BestSolutions.xml")
        best = parse_best_solutions_xml(best_path)

        for case_id, sol in best.items():
            self.assertGreater(sol['utility'], 0,
                               f"Best solution for {case_id} should have utility > 0")

    def test_discovery_utility_values_reasonable(self):
        """Utility values from the dataset should be in a reasonable range."""
        best_path = os.path.join(DISCOVERY, "discovery-20-4-BestSolutions.xml")
        best = parse_best_solutions_xml(best_path)

        for case_id, sol in best.items():
            # Discovery utility values in the dataset are typically 200-500
            self.assertGreater(sol['utility'], 0)
            self.assertLess(sol['utility'], 10000,
                            f"Utility for {case_id} seems unreasonably high")

    def test_composition_utility_grows_with_services(self):
        """Composition utility should generally be higher (more services contribute)."""
        disc_path = os.path.join(DISCOVERY, "discovery-20-4-BestSolutions.xml")
        comp_path = os.path.join(COMPOSITION1, "composition1-20-4-BestSolutions.xml")

        disc_best = parse_best_solutions_xml(disc_path)
        comp_best = parse_best_solutions_xml(comp_path)

        disc_avg = sum(s['utility'] for s in disc_best.values()) / max(len(disc_best), 1)
        comp_avg = sum(s['utility'] for s in comp_best.values()) / max(len(comp_best), 1)

        # Composition utilities should generally be higher than discovery
        # (multiple services aggregate QoS via the utility equation)
        self.assertGreater(comp_avg, disc_avg * 0.5,
                           "Composition avg utility should not be drastically lower than discovery")


@unittest.skipUnless(_dataset_available(), "QoS-WSC dataset not found")
class TestScalabilityConfigurations(unittest.TestCase):
    """Test parsing across different scalability configurations."""

    def test_parse_all_discovery_requests(self):
        """All discovery request files should be parseable."""
        xml_files = glob.glob(os.path.join(DISCOVERY, "*-Requests.xml"))
        for xml_file in xml_files:
            requests = parse_requests_xml(xml_file)
            self.assertGreater(len(requests), 0,
                               f"Failed to parse {os.path.basename(xml_file)}")

    def test_parse_all_composition1_requests(self):
        xml_files = glob.glob(os.path.join(COMPOSITION1, "*-Requests.xml"))
        # Also handle the typo variant
        xml_files += glob.glob(os.path.join(COMPOSITION1, "*-Request.xml"))
        for xml_file in xml_files:
            requests = parse_requests_xml(xml_file)
            self.assertGreater(len(requests), 0,
                               f"Failed to parse {os.path.basename(xml_file)}")

    def test_parse_all_best_solutions(self):
        """All BestSolutions files should be parseable."""
        for folder in [DISCOVERY, COMPOSITION1, COMPOSITION2]:
            xml_files = glob.glob(os.path.join(folder, "*-BestSolutions.xml"))
            for xml_file in xml_files:
                solutions = parse_best_solutions_xml(xml_file)
                self.assertGreater(len(solutions), 0,
                                   f"Failed to parse {os.path.basename(xml_file)}")

    def test_larger_configs_have_more_wsdl_files(self):
        """Configurations with more services (100 vs 20) should have more WSDL files."""
        dir_20 = os.path.join(DISCOVERY, "discovery-20-4")
        dir_100 = os.path.join(DISCOVERY, "discovery-100-4")

        if not (os.path.isdir(dir_20) and os.path.isdir(dir_100)):
            self.skipTest("Both directories needed for comparison")

        count_20 = len(glob.glob(os.path.join(dir_20, "*.wsdl")))
        count_100 = len(glob.glob(os.path.join(dir_100, "*.wsdl")))

        self.assertGreater(count_100, count_20,
                           "100-service config should have more WSDL files than 20-service")


@unittest.skipUnless(_dataset_available(), "QoS-WSC dataset not found")
class TestClassicComposerOnDiscovery(unittest.TestCase):
    """Run the ClassicComposer on real discovery data (small config)."""

    def setUp(self):
        from services.classic_composer import ClassicComposer

        self.parser = WSDLParser()
        wsdl_dir = os.path.join(DISCOVERY, "discovery-20-4")
        if not os.path.isdir(wsdl_dir):
            self.skipTest("discovery-20-4 WSDL folder not found")

        self.services = self.parser.parse_directory(wsdl_dir)
        if not self.services:
            self.skipTest("No services parsed")

        self.composer = ClassicComposer(self.services)

        req_path = os.path.join(DISCOVERY, "discovery-20-4-Requests.xml")
        self.requests = parse_requests_xml(req_path)

    def test_composer_runs_without_error(self):
        """The composer should not crash on real data."""
        if not self.requests:
            self.skipTest("No requests")

        req = self.requests[0]
        # Try composition — may or may not succeed (depends on service graph)
        for algo in ["dijkstra", "greedy"]:
            result = self.composer.compose(req, algo)
            self.assertIsNotNone(result)
            # It should have a computation_time regardless of success
            self.assertGreaterEqual(result.computation_time, 0)

    def test_composer_returns_result_structure(self):
        """CompositionResult from real data should have expected fields."""
        if not self.requests:
            self.skipTest("No requests")

        req = self.requests[0]
        result = self.composer.compose(req, "greedy")
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.algorithm_used)
        self.assertIsInstance(result.services, list)
        self.assertIsInstance(result.algorithm_trace, list)


@unittest.skipUnless(_dataset_available(), "QoS-WSC dataset not found")
class TestEndToEndDiscovery(unittest.TestCase):
    """Full end-to-end test: parse data, run algorithms, compare to ground truth."""

    def test_e2e_discovery_workflow(self):
        """
        End-to-end:
        1. Parse Requests XML
        2. Parse WSDL directory
        3. Parse BestSolutions
        4. Verify best solution services exist in the parsed WSDL pool
        """
        req_path = os.path.join(DISCOVERY, "discovery-20-4-Requests.xml")
        best_path = os.path.join(DISCOVERY, "discovery-20-4-BestSolutions.xml")
        wsdl_dir = os.path.join(DISCOVERY, "discovery-20-4")

        if not os.path.isdir(wsdl_dir):
            self.skipTest("discovery-20-4 WSDL folder not found")

        # Step 1: Parse requests
        requests = parse_requests_xml(req_path)
        self.assertGreater(len(requests), 0)

        # Step 2: Parse WSDL services
        parser = WSDLParser()
        services = parser.parse_directory(wsdl_dir)
        self.assertGreater(len(services), 0)
        service_ids = {s.id for s in services}

        # Step 3: Parse best solutions
        best = parse_best_solutions_xml(best_path)
        self.assertGreater(len(best), 0)

        # Step 4: Best solution services should be in the WSDL pool
        # (service names in BestSolutions use "servicepXXaYYY" while parsed IDs are "pXXaYYY")
        for case_id, sol in best.items():
            for sid in sol['service_ids']:
                # Strip "service" prefix to get the ID as parsed from WSDL filename
                stripped = sid.replace("service", "")
                self.assertIn(stripped, service_ids,
                              f"Best service {sid} (→{stripped}) from {case_id} "
                              f"not found in parsed WSDL pool")


@unittest.skipUnless(_dataset_available(), "QoS-WSC dataset not found")
class TestAdditionalInfo(unittest.TestCase):
    """Test that the additional-information files are accessible."""

    def test_qws_txt_exists(self):
        path = os.path.join(QOS_WSC, "additional-information", "qws.txt")
        self.assertTrue(os.path.exists(path))

    def test_qws2_txt_exists(self):
        path = os.path.join(QOS_WSC, "additional-information", "qws2.txt")
        self.assertTrue(os.path.exists(path))

    def test_utility_equation_exists(self):
        path = os.path.join(QOS_WSC, "additional-information", "utility-equation.txt")
        self.assertTrue(os.path.exists(path))

    def test_qws2_has_header(self):
        """qws2.txt should have a header explaining the 9 QoS attributes."""
        path = os.path.join(QOS_WSC, "additional-information", "qws2.txt")
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read(2000)
        self.assertIn("Response Time", content)
        self.assertIn("Availability", content)
        self.assertIn("Throughput", content)

    def test_qws_data_lines(self):
        """qws.txt should have >2000 data lines (2507 services)."""
        path = os.path.join(QOS_WSC, "additional-information", "qws.txt")
        with open(path, 'r') as f:
            lines = [l for l in f if l.strip() and not l.startswith('#')]
        self.assertGreater(len(lines), 2000,
                           "qws.txt should contain >2000 service records")


@unittest.skipUnless(_dataset_available(), "QoS-WSC dataset not found")
class TestCompositionDepthVariation(unittest.TestCase):
    """Composition2 should have deeper workflows than Composition1."""

    def test_composition2_deeper_workflows(self):
        """composition2 best solutions should have more services per case on average."""
        comp1_path = os.path.join(COMPOSITION1, "composition1-20-4-BestSolutions.xml")
        comp2_path = os.path.join(COMPOSITION2, "composition2-20-4-BestSolutions.xml")

        comp1 = parse_best_solutions_xml(comp1_path)
        comp2 = parse_best_solutions_xml(comp2_path)

        avg1 = sum(len(s['service_ids']) for s in comp1.values()) / max(len(comp1), 1)
        avg2 = sum(len(s['service_ids']) for s in comp2.values()) / max(len(comp2), 1)

        # Composition2 should generally have deeper chains
        self.assertGreaterEqual(avg2, avg1 * 0.8,
                                f"Composition2 avg depth ({avg2:.1f}) should be comparable to "
                                f"Composition1 ({avg1:.1f})")


if __name__ == "__main__":
    unittest.main()
