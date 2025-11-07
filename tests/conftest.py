"""
Configuration pytest - Fixtures globales
"""

import pytest
import mongomock
from src.core.registry import ServiceRegistry


@pytest.fixture
def mock_registry():
    """Fixture avec une base MongoDB mockée"""
    client = mongomock.MongoClient()
    db = client['test_db']
    
    registry = ServiceRegistry.__new__(ServiceRegistry)
    registry.client = client
    registry.db = db
    registry.services = db['services']
    registry.execution_history = db['execution_history']
    
    return registry


@pytest.fixture
def sample_wsdl_url():
    """URL WSDL de test"""
    return "http://webservices.oorsprong.org/websamples.countryinfo/CountryInfoService.wso?WSDL"


@pytest.fixture
def sample_context():
    """Contexte de test"""
    return {
        'user': {
            'id': 'test_user',
            'location': {'country': 'DZ'},
            'authenticated': True
        },
        'temporal': {'timestamp': '2025-11-06T10:00:00Z'},
        'environmental': {'network_quality': 'good'},
        'application': {'goal': 'test'}
    }