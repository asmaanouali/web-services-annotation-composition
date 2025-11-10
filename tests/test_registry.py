"""
Tests unitaires pour ServiceRegistry
"""

import pytest
from datetime import datetime


class TestServiceRegistry:
    
    def test_register_service(self, mock_registry, sample_wsdl_url):
        """Test enregistrement d'un service"""
        service_id = mock_registry.register_service(sample_wsdl_url)
        
        assert service_id is not None
        
        service = mock_registry.get_service(service_id)
        assert service is not None
        assert service['service_id'] == service_id
    
    def test_get_service(self, mock_registry, sample_wsdl_url):
        """Test récupération d'un service"""
        service_id = mock_registry.register_service(sample_wsdl_url)
        service = mock_registry.get_service(service_id)
        
        assert service is not None
        assert 'service_name' in service
        assert 'functional_annotations' in service
        assert 'metadata' in service
    
    def test_search_services_by_name(self, mock_registry, sample_wsdl_url):
        """Test recherche par nom"""
        service_id = mock_registry.register_service(sample_wsdl_url)
        service = mock_registry.get_service(service_id)
        service_name = service['service_name']
        
        results = mock_registry.search_services({'name': service_name[:5]})
        assert len(results) > 0
        assert any(r['service_id'] == service_id for r in results)
    
    def test_update_annotations(self, mock_registry, sample_wsdl_url):
        """Test mise à jour des annotations"""
        service_id = mock_registry.register_service(sample_wsdl_url)
        
        new_annotations = {
            'policy_annotations.security.authentication_required': True
        }
        
        success = mock_registry.update_annotations(service_id, new_annotations)
        assert success
        
        service = mock_registry.get_service(service_id)
        # Note: vérification selon la structure réelle
        assert service is not None
    
    def test_list_all_services(self, mock_registry, sample_wsdl_url):
        """Test listage de tous les services"""
        service_id = mock_registry.register_service(sample_wsdl_url)
        services = mock_registry.list_all_services()
        
        assert len(services) > 0
        assert any(s['service_id'] == service_id for s in services)