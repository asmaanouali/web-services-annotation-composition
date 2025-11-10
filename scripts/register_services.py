#!/usr/bin/env python3
"""
Script pour enregistrer des services en batch
Usage: python register_services.py --config services_list.json
"""

import argparse
import json
import logging
from src.main import ServiceAnnotationSystem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def register_services_from_file(config_file: str):
    """Enregistre des services depuis un fichier de configuration"""
    
    # Charger la configuration
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Initialiser le système
    system = ServiceAnnotationSystem()
    
    # Enregistrer chaque service
    for service_config in config['services']:
        wsdl_url = service_config['wsdl_url']
        policies = service_config.get('policies', {})
        
        try:
            service_id = system.register_and_annotate_service(wsdl_url, policies)
            logger.info(f"✓ Registered: {wsdl_url} -> {service_id}")
        except Exception as e:
            logger.error(f"✗ Failed to register {wsdl_url}: {e}")
    
    logger.info("Registration complete")

def main():
    parser = argparse.ArgumentParser(description='Register services in batch')
    parser.add_argument('--config', required=True, help='Path to services configuration file')
    
    args = parser.parse_args()
    register_services_from_file(args.config)

if __name__ == "__main__":
    main()