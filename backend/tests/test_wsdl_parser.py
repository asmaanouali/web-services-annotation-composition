"""
Unit tests for the WSDL parser.
"""
import unittest
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.wsdl_parser import WSDLParser, parse_requests_xml


SAMPLE_WSDL = """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://schemas.xmlsoap.org/wsdl/"
             name="TestService">
  <message name="getDataRequest">
    <part name="paramA" type="xsd:string"/>
  </message>
  <message name="getDataResponse">
    <part name="paramB" type="xsd:string"/>
  </message>
  <QoS>
    <ResponseTime Value="150"/>
    <Availability Value="99"/>
    <Throughput Value="500"/>
    <Successability Value="95"/>
    <Reliability Value="98"/>
    <Compliance Value="80"/>
    <BestPractices Value="70"/>
    <Latency Value="30"/>
    <Documentation Value="60"/>
  </QoS>
</definitions>
"""


class TestWSDLParser(unittest.TestCase):
    """Tests for the WSDLParser class."""

    def setUp(self):
        self.parser = WSDLParser()

    def test_parse_content_returns_service(self):
        service = self.parser.parse_content(SAMPLE_WSDL, "servicep1a1234567.wsdl")
        self.assertIsNotNone(service)
        self.assertEqual(service.id, "p1a1234567")

    def test_parse_content_extracts_parameters(self):
        service = self.parser.parse_content(SAMPLE_WSDL, "test.wsdl")
        self.assertIn("paramA", service.inputs)
        self.assertIn("paramB", service.outputs)

    def test_parse_content_extracts_qos(self):
        service = self.parser.parse_content(SAMPLE_WSDL, "test.wsdl")
        self.assertAlmostEqual(service.qos.response_time, 150.0)
        self.assertAlmostEqual(service.qos.availability, 99.0)
        self.assertAlmostEqual(service.qos.throughput, 500.0)

    def test_extract_service_id_standard(self):
        sid = self.parser._extract_service_id("servicep10a9876543.wsdl")
        self.assertEqual(sid, "p10a9876543")

    def test_extract_service_id_fallback(self):
        sid = self.parser._extract_service_id("custom_service.wsdl")
        self.assertEqual(sid, "custom_service")

    def test_parse_file_creates_temp(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".wsdl", delete=False, encoding="utf-8"
        ) as f:
            f.write(SAMPLE_WSDL)
            f.flush()
            service = self.parser.parse_file(f.name)
        os.unlink(f.name)
        self.assertIsNotNone(service)
        self.assertGreater(len(service.inputs), 0)

    def test_parse_invalid_returns_none(self):
        service = self.parser.parse_content("<invalid>xml", "bad.wsdl")
        self.assertIsNone(service)


class TestParseRequestsXml(unittest.TestCase):
    """Tests for parse_requests_xml."""

    def test_standard_format(self):
        xml_content = """<?xml version="1.0"?>
<Requests>
  <Request id="req1">
    <Provided>p1;p2</Provided>
    <Resultant>out1</Resultant>
    <QoS>
      <ResponseTime>200</ResponseTime>
      <Availability>90</Availability>
    </QoS>
  </Request>
</Requests>"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write(xml_content)
            f.flush()
            reqs = parse_requests_xml(f.name)
        os.unlink(f.name)
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0].id, "req1")
        self.assertEqual(reqs[0].resultant, "out1")

    def test_wschallenge_format(self):
        xml_content = """<?xml version="1.0"?>
<WSChallenge>
  <DiscoveryRoutine name="dr1">
    <Provided>a,b</Provided>
    <Resultant>c</Resultant>
    <QoS>100,90,500,95,98,80,70,30,60</QoS>
  </DiscoveryRoutine>
</WSChallenge>"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write(xml_content)
            f.flush()
            reqs = parse_requests_xml(f.name)
        os.unlink(f.name)
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0].id, "dr1")
        self.assertEqual(reqs[0].resultant, "c")

    def test_no_resultant_skips_request(self):
        xml_content = """<?xml version="1.0"?>
<Requests>
  <Request id="bad">
    <Provided>p1;p2</Provided>
  </Request>
</Requests>"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write(xml_content)
            f.flush()
            reqs = parse_requests_xml(f.name)
        os.unlink(f.name)
        self.assertEqual(len(reqs), 0)


if __name__ == "__main__":
    unittest.main()
