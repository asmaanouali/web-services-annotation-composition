#!/usr/bin/env python3
"""
Script pour analyse quotidienne (à exécuter via cron)
Usage: python analyze_daily.py
"""

import logging
from datetime import datetime
from src.main import ServiceAnnotationSystem

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/analysis_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def daily_analysis():
    """Exécute l'analyse quotidienne"""
    
    logger.info("=" * 60)
    logger.info("Starting daily analysis")
    logger.info("=" * 60)
    
    # Initialiser le système
    system = ServiceAnnotationSystem()
    
    try:
        # Analyser et enrichir les annotations
        system.analyze_and_enrich()
        
        # Générer un rapport
        services = system.registry.list_all_services()
        
        logger.info(f"\nAnalysis Summary:")
        logger.info(f"Total services: {len(services)}")
        
        for service in services:
            stats = service.get('interaction_annotations', {}).get('statistics', {})
            logger.info(f"\n{service['service_name']}:")
            logger.info(f"  - Invocations: {stats.get('total_invocations', 0)}")
            logger.info(f"  - Success rate: {stats.get('success_rate', 0)*100:.1f}%")
            logger.info(f"  - Avg response: {stats.get('avg_response_time_ms', 0):.0f}ms")
        
        logger.info("\nDaily analysis completed successfully")
        
    except Exception as e:
        logger.error(f"Error during analysis: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    daily_analysis()