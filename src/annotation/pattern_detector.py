"""
CompositionPatternDetector - Détection de patterns de composition
"""

from collections import defaultdict, Counter
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import logging

from src.core.registry import ServiceRegistry

logger = logging.getLogger(__name__)


class CompositionPatternDetector:
    """Détecte les patterns de composition à partir de l'historique"""
    
    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
    
    def detect_patterns(self, time_window_days: int = 30, min_frequency: int = 3):
        """Détecte les patterns de composition pour tous les services"""
        all_services = self.registry.list_all_services()
        
        for service in all_services:
            patterns = self._find_service_patterns(service['service_id'], time_window_days, min_frequency)
            
            if patterns:
                self.registry.update_annotations(
                    service['service_id'],
                    {'interaction_annotations.composition_patterns': patterns}
                )
                
                logger.info(f"Detected {len(patterns)} patterns for service {service['service_name']}")
    
    def _find_service_patterns(self, service_id: str, time_window_days: int, min_frequency: int) -> List[Dict]:
        """Trouve les patterns pour un service spécifique"""
        cutoff_date = datetime.utcnow() - timedelta(days=time_window_days)
        
        history = list(self.registry.execution_history.find({
            'service_id': service_id,
            'timestamp': {'$gte': cutoff_date},
            'status': 'success'
        }).sort('timestamp', 1))
        
        if len(history) < 2:
            return []
        
        sequences = self._find_sequences(history, max_delay_seconds=300)
        pattern_counts = Counter(sequences)
        
        patterns = []
        for (successor_service_id, context_sig), count in pattern_counts.items():
            if count >= min_frequency:
                pattern_stats = self._compute_pattern_stats(service_id, successor_service_id, context_sig, history)
                
                patterns.append({
                    'successor_service_id': successor_service_id,
                    'frequency': count,
                    'success_rate': pattern_stats['success_rate'],
                    'avg_delay_ms': pattern_stats['avg_delay_ms'],
                    'context_conditions': pattern_stats['context_conditions']
                })
        
        return patterns
    
    def _find_sequences(self, history: List[Dict], max_delay_seconds: int) -> List[Tuple[str, str]]:
        """Trouve les séquences de services"""
        sequences = []
        
        sessions = defaultdict(list)
        for record in history:
            user_id = record.get('context', {}).get('user', {}).get('id', 'anonymous')
            sessions[user_id].append(record)
        
        for user_id, user_history in sessions.items():
            for i in range(len(user_history) - 1):
                current = user_history[i]
                next_record = user_history[i + 1]
                
                time_diff = (next_record['timestamp'] - current['timestamp']).total_seconds()
                
                if time_diff <= max_delay_seconds:
                    context_sig = self._extract_context_signature(current['context'])
                    successor_service = self._identify_successor_service(current, next_record)
                    
                    if successor_service:
                        sequences.append((successor_service, context_sig))
        
        return sequences
    
    def _identify_successor_service(self, current: Dict, next_record: Dict) -> str:
        """Identifie le service successeur"""
        return next_record.get('service_id', '')
    
    def _extract_context_signature(self, context: Dict) -> str:
        """Extrait une signature du contexte"""
        location = context.get('user', {}).get('location', {}).get('country', 'unknown')
        timestamp = context.get('temporal', {}).get('timestamp', '')
        
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                day_of_week = dt.strftime('%A')
                return f"{location}_{day_of_week}"
            except:
                pass
        
        return location
    
    def _compute_pattern_stats(self, service_id: str, successor_id: str, context_sig: str, history: List[Dict]) -> Dict:
        """Calcule les statistiques pour un pattern"""
        pattern_records = [
            r for r in history
            if self._extract_context_signature(r['context']) == context_sig
        ]
        
        if not pattern_records:
            return {
                'success_rate': 0.0,
                'avg_delay_ms': 0,
                'context_conditions': {}
            }
        
        success_count = sum(1 for r in pattern_records if r['status'] == 'success')
        avg_delay = sum(r.get('execution_time_ms', 0) for r in pattern_records) / len(pattern_records)
        
        return {
            'success_rate': success_count / len(pattern_records),
            'avg_delay_ms': int(avg_delay),
            'context_conditions': {'context_signature': context_sig}
        }