"""
Tests unitaires pour WSDLParser
"""

import pytest
from src.core.wsdl_parser import WSDLParser


class TestWSDLParser:
    
    def test_parser_initialization(self, sample_wsdl_url):
        """Test que le parser s'initialise correctement"""
        parser = WSDLParser(sample_wsdl_url)
        assert parser.wsdl_url == sample_wsdl_url
        assert parser.client is not None
    
    def test_extract_service_name(self, sample_wsdl_url):
        """Test extraction du nom du service"""
        parser = WSDLParser(sample_wsdl_url)
        service_name = parser.get_service_name()
        assert service_name is not None
        assert len(service_name) > 0
    
    def test_extract_operations(self, sample_wsdl_url):
        """Test extraction des opérations"""
        parser = WSDLParser(sample_wsdl_url)
        operations = parser.extract_operations()
        
        assert len(operations) > 0
        assert all('name' in op for op in operations)
        assert all('input' in op for op in operations)
        assert all('output' in op for op in operations)
    
    def test_generate_functional_annotations(self, sample_wsdl_url):
        """Test génération complète des annotations"""
        parser = WSDLParser(sample_wsdl_url)
        annotations = parser.generate_functional_annotations()
        
        assert 'service_id' in annotations
        assert 'service_name' in annotations
        assert 'functional_annotations' in annotations
        assert 'operations' in annotations['functional_annotations']