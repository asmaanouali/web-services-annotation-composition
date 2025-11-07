"""
ContextualServiceRecommender - Recommandation intelligente de services
"""

from typing import List, Dict, Tuple
from datetime import datetime
import math
import logging

from src.core.registry import ServiceRegistry

logger = logging.getLogger(__name__)


class ContextualServiceRecommender:
    """Recommande les meilleurs services selon le contexte"""
    
    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
    
    def recommend_services(self, query: Dict, context: Dict, top_k: int = 5) -> List[Dict]:
        """Recommande les meilleurs services pour une requête donnée"""
        
        candidates = self.registry.search_services(query, context)
        
        if not candidates:
            return []
        
        scored_services = []
        for service in candidates:
            score = self._compute_recommendation_score(service, context, query)
            scored_services.append((service, score))
        
        scored_services.sort(key=lambda x: x[1], reverse=True)
        
        return [
            {
                **service,
                'recommendation_score': score,
                'recommendation_reasons': self._explain_recommendation(service, context)
            }
            for service, score in scored_services[:top_k]
        ]
    
    def _compute_recommendation_score(self, service: Dict, context: Dict, query: Dict) -> float:
        """Calcule un score de recommandation multi-critères"""
        
        scores = {
            'contextual_performance': self._score_contextual_performance(service, context),
            'reliability': self._score_reliability(service),
            'qos': self._score_qos(service, context),
            'privacy_compliance': self._score_privacy_compliance(service, context),
            'cost': self._score_cost(service, context)
        }
        
        weights = {
            'contextual_performance': 0.30,
            'reliability': 0.25,
            'qos': 0.20,
            'privacy_compliance': 0.15,
            'cost': 0.10
        }
        
        total_score = sum(scores[k] * weights[k] for k in scores)
        
        return total_score
    
    def _score_contextual_performance(self, service: Dict, context: Dict) -> float:
        """Score basé sur les performances dans le contexte actuel"""
        contextual_perf = service.get('interaction_annotations', {}).get('contextual_performance', {})
        
        if not contextual_perf:
            return 0.5
        
        score = 0.0
        
        user_location = context.get('user', {}).get('location', {}).get('country')
        if user_location:
            location_perf = contextual_perf.get('by_location', {}).get(user_location, {})
            if location_perf:
                avg_time = location_perf.get('avg_response_ms', 1000)
                score += max(0, 1 - (avg_time / 5000))
        
        current_hour = datetime.utcnow().hour
        time_period = self._get_time_period(current_hour)
        time_perf = contextual_perf.get('by_time_of_day', {}).get(time_period, {})
        if time_perf:
            avg_time = time_perf.get('avg_response_ms', 1000)
            score += max(0, 1 - (avg_time / 5000))
        
        network_quality = context.get('environmental', {}).get('network_quality', 'unknown')
        network_perf = contextual_perf.get('by_network_quality', {}).get(network_quality, {})
        if network_perf:
            avg_time = network_perf.get('avg_response_ms', 1000)
            score += max(0, 1 - (avg_time / 5000))
        
        return min(1.0, score / 3)
    
    def _score_reliability(self, service: Dict) -> float:
        """Score de fiabilité basé sur le taux de succès"""
        stats = service.get('interaction_annotations', {}).get('statistics', {})
        success_rate = stats.get('success_rate', 0.0)
        total_invocations = stats.get('total_invocations', 0)
        
        confidence = min(1.0, total_invocations / 100)
        
        return success_rate * confidence
    
    def _score_qos(self, service: Dict, context: Dict) -> float:
        """Score basé sur la qualité de service"""
        stats = service.get('interaction_annotations', {}).get('statistics', {})
        avg_response_time = stats.get('avg_response_time_ms', 1000)
        
        max_response_time = context.get('application', {}).get('constraints', {}).get('max_response_time', 5000)
        
        if avg_response_time > max_response_time:
            return 0.0
        
        return 1 - (avg_response_time / max_response_time)
    
    def _score_privacy_compliance(self, service: Dict, context: Dict) -> float:
        """Score de conformité aux exigences de confidentialité"""
        privacy_policy = service.get('policy_annotations', {}).get('privacy', {})
        user_privacy_level = context.get('user', {}).get('preferences', {}).get('privacy_level', 'medium')
        
        data_sensitivity = privacy_policy.get('data_sensitivity', 'unknown')
        
        sensitivity_scores = {
            'public': 1.0,
            'internal': 0.7,
            'confidential': 0.3,
            'unknown': 0.5
        }
        
        score = sensitivity_scores.get(data_sensitivity, 0.5)
        
        if user_privacy_level == 'high' and data_sensitivity in ['confidential', 'internal']:
            score *= 0.5
        
        return score
    
    def _score_cost(self, service: Dict, context: Dict) -> float:
        """Score basé sur le coût"""
        usage_policy = service.get('policy_annotations', {}).get('usage', {})
        cost_per_call = usage_policy.get('cost_per_call', 0.0)
        
        max_cost = context.get('application', {}).get('constraints', {}).get('max_cost', 1.0)
        
        if cost_per_call > max_cost:
            return 0.0
        
        if cost_per_call == 0:
            return 1.0
        
        return 1 - (cost_per_call / max_cost)
    
    def _get_time_period(self, hour: int) -> str:
        """Détermine la période de la journée"""
        if 0 <= hour < 6:
            return 'night'
        elif 6 <= hour < 12:
            return 'morning'
        elif 12 <= hour < 18:
            return 'afternoon'
        else:
            return 'evening'
    
    def _explain_recommendation(self, service: Dict, context: Dict) -> List[str]:
        """Génère des explications pour la recommandation"""
        reasons = []
        
        contextual_perf = service.get('interaction_annotations', {}).get('contextual_performance', {})
        user_location = context.get('user', {}).get('location', {}).get('country')
        
        if user_location and contextual_perf.get('by_location', {}).get(user_location):
            loc_perf = contextual_perf['by_location'][user_location]
            reasons.append(f"Performances optimales dans votre région ({loc_perf.get('avg_response_ms')}ms en moyenne)")
        
        stats = service.get('interaction_annotations', {}).get('statistics', {})
        success_rate = stats.get('success_rate', 0.0)
        if success_rate >= 0.95:
            reasons.append(f"Très fiable ({success_rate*100:.1f}% de succès)")
        
        usage_policy = service.get('policy_annotations', {}).get('usage', {})
        if usage_policy.get('free_tier', False):
            reasons.append("Niveau gratuit disponible")
        
        privacy_policy = service.get('policy_annotations', {}).get('privacy', {})
        if privacy_policy.get('data_sensitivity') == 'public':
            reasons.append("Aucune donnée sensible traitée")
        
        return reasons