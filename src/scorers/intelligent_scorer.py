from typing import Dict, Any, List
import yaml
from pathlib import Path

class IntelligentScorer:
    def __init__(self):
        config_path = Path(__file__).parent.parent.parent / 'config.yaml'
        if config_path.exists():
            with open(config_path) as f:
                config = yaml.safe_load(f)
                weights = config.get('scoring', {})
        else:
            weights = {}
        
        self.interaction_weight = weights.get('interaction_weight', 0.3)
        self.success_weight = weights.get('success_rate_weight', 0.3)
        self.response_time_weight = weights.get('response_time_weight', 0.2)
        self.context_weight = weights.get('context_weight', 0.2)
    
    def calculate_score(
        self, 
        annotations: Dict[str, Any], 
        operation: str,
        previous_services: List[str]
    ) -> float:
        """
        Calcule le score d'un service pour une composition
        Basé sur les annotations enrichies
        """
        
        score = 0.0
        
        # 1. Score d'interaction (30%)
        interaction_ann = next(
            (ann for ann in annotations['interaction_annotations'] 
             if ann['operation'] == operation),
            None
        )
        
        if interaction_ann:
            # Normaliser le nombre d'interactions (0-500 -> 0-1)
            interaction_score = min(interaction_ann['number_of_interactions'] / 500, 1.0)
            score += interaction_score * self.interaction_weight * 100
            
            # Bonus si interagit avec services précédents
            for prev_svc in previous_services:
                if prev_svc in interaction_ann.get('interacts_with_services', []):
                    score += 5
            
            # 2. Score de taux de succès (30%)
            score += interaction_ann['success_rate'] * self.success_weight * 100
            
            # 3. Score de temps de réponse (20%)
            # Meilleur score pour temps < 200ms, décroît jusqu'à 500ms
            time_score = max(0, (500 - interaction_ann['avg_response_time_ms']) / 500)
            score += time_score * self.response_time_weight * 100
        
        # 4. Score de contexte (20%)
        context_ann = annotations.get('context_annotations', {})
        context_score = 0
        if context_ann.get('location_dependent'): context_score += 5
        if context_ann.get('time_sensitive'): context_score += 5
        if context_ann.get('user_preference_based'): context_score += 5
        if context_ann.get('requires_session'): context_score += 5
        score += (context_score / 20) * self.context_weight * 100
        
        # Pénalité pour coût élevé
        policy_ann = annotations.get('policy_annotations', {})
        if policy_ann.get('usage_cost') == 'HIGH':
            score -= 5
        
        return min(round(score, 2), 100.0)
    
    def update_annotations_after_interaction(
        self, 
        annotations: Dict[str, Any], 
        operation: str,
        interacted_with_service: str
    ) -> Dict[str, Any]:
        """
        Met à jour les annotations après une interaction
        Augmente le nombre d'interactions
        """
        
        for ann in annotations['interaction_annotations']:
            if ann['operation'] == operation:
                # Augmenter le nombre d'interactions
                ann['number_of_interactions'] += 1
                
                # Ajouter le service interagi si pas déjà présent
                if interacted_with_service not in ann['interacts_with_services']:
                    ann['interacts_with_services'].append(interacted_with_service)
        
        return annotations
