from collections import defaultdict
from datetime import datetime
from typing import Dict, List
import statistics
from collections import Counter
import logging
from src.core.registry import ServiceRegistry

class ContextualPerformanceAnalyzer:
    """Analyse les performances selon différentes dimensions contextuelles"""
    
    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
        self.logger = logging.getLogger(__name__)
    
    def analyze_all_services(self):
        """Analyse les performances contextuelles pour tous les services"""
        services = self.registry.list_all_services()
        
        for service in services:
            contextual_perf = self.analyze_service(service['service_id'])
            
            if contextual_perf:
                self.registry.update_annotations(
                    service['service_id'],
                    {'interaction_annotations.contextual_performance': contextual_perf}
                )
    
    def analyze_service(self, service_id: str) -> Dict:
        """Analyse les performances d'un service selon le contexte"""
        # Récupérer l'historique
        history = list(self.registry.execution_history.find({
            'service_id': service_id,
            'status': 'success'
        }))
        
        if len(history) < 10:  # Pas assez de données
            return {}
        
        return {
            'by_location': self._analyze_by_location(history),
            'by_time_of_day': self._analyze_by_time_of_day(history),
            'by_day_of_week': self._analyze_by_day_of_week(history),
            'by_network_quality': self._analyze_by_network_quality(history),
            'optimal_conditions': self._find_optimal_conditions(history)
        }
    
    def _analyze_by_location(self, history: List[Dict]) -> Dict:
        """Analyse par localisation géographique"""
        location_data = defaultdict(list)
        
        for record in history:
            location = record.get('context', {}).get('user', {}).get('location', {}).get('country', 'unknown')
            exec_time = record.get('execution_time_ms', 0)
            location_data[location].append(exec_time)
        
        results = {}
        for location, times in location_data.items():
            if len(times) >= 3:
                results[location] = {
                    'avg_response_ms': int(statistics.mean(times)),
                    'median_response_ms': int(statistics.median(times)),
                    'std_dev': int(statistics.stdev(times)) if len(times) > 1 else 0,
                    'sample_size': len(times),
                    'success_rate': 1.0  # Tous sont en succès déjà
                }
        
        return results
    
    def _analyze_by_time_of_day(self, history: List[Dict]) -> Dict:
        """Analyse par période de la journée"""
        time_periods = {
            'night': (0, 6),
            'morning': (6, 12),
            'afternoon': (12, 18),
            'evening': (18, 24)
        }
        
        period_data = defaultdict(list)
        
        for record in history:
            timestamp = record.get('timestamp')
            if timestamp:
                hour = timestamp.hour
                
                for period, (start, end) in time_periods.items():
                    if start <= hour < end:
                        exec_time = record.get('execution_time_ms', 0)
                        period_data[period].append(exec_time)
                        break
        
        results = {}
        for period, times in period_data.items():
            if len(times) >= 3:
                results[period] = {
                    'avg_response_ms': int(statistics.mean(times)),
                    'sample_size': len(times)
                }
        
        return results
    
    def _analyze_by_day_of_week(self, history: List[Dict]) -> Dict:
        """Analyse par jour de la semaine"""
        day_data = defaultdict(list)
        
        for record in history:
            timestamp = record.get('timestamp')
            if timestamp:
                day = timestamp.strftime('%A')
                exec_time = record.get('execution_time_ms', 0)
                day_data[day].append(exec_time)
        
        results = {}
        for day, times in day_data.items():
            if len(times) >= 2:
                results[day] = {
                    'avg_response_ms': int(statistics.mean(times)),
                    'sample_size': len(times)
                }
        
        return results
    
    def _analyze_by_network_quality(self, history: List[Dict]) -> Dict:
        """Analyse par qualité réseau"""
        network_data = defaultdict(list)
        
        for record in history:
            quality = record.get('context', {}).get('environmental', {}).get('network_quality', 'unknown')
            exec_time = record.get('execution_time_ms', 0)
            network_data[quality].append(exec_time)
        
        results = {}
        for quality, times in network_data.items():
            if len(times) >= 3:
                results[quality] = {
                    'avg_response_ms': int(statistics.mean(times)),
                    'sample_size': len(times)
                }
        
        return results
    
    def _find_optimal_conditions(self, history: List[Dict]) -> Dict:
        """Identifie les conditions optimales d'exécution"""
        # Trouver les 10% d'exécutions les plus rapides
        sorted_history = sorted(history, key=lambda x: x.get('execution_time_ms', float('inf')))
        top_10_percent = sorted_history[:max(1, len(sorted_history) // 10)]
        
        if not top_10_percent:
            return {}
        
        # Analyser les caractéristiques communes
        locations = [r.get('context', {}).get('user', {}).get('location', {}).get('country') 
                    for r in top_10_percent]
        
        times_of_day = []
        for r in top_10_percent:
            ts = r.get('timestamp')
            if ts:
                times_of_day.append(ts.hour)
        
        network_qualities = [r.get('context', {}).get('environmental', {}).get('network_quality') 
                            for r in top_10_percent]
        
        return {
            'best_avg_response_ms': int(statistics.mean([r.get('execution_time_ms', 0) for r in top_10_percent])),
            'common_locations': [loc for loc, count in Counter(locations).most_common(3) if loc],
            'common_hours': list(set(times_of_day)) if times_of_day else [],
            'common_network_quality': Counter(network_qualities).most_common(1)[0][0] if network_qualities else 'unknown'
        }