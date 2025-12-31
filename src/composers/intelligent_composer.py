from typing import List, Dict, Tuple
from src.models.service import Service
from src.models.composition import CompositionStep
from src.scorers.intelligent_scorer import IntelligentScorer

class IntelligentComposer:
    """Composition intelligente - UTILISE les annotations enrichies pour scorer"""
    
    def __init__(self, services: List[Service]):
        self.services = {s.name: s for s in services}
        self.scorer = IntelligentScorer()
    
    def select_best_service(
        self, 
        step: CompositionStep, 
        previous_services: List[str]
    ) -> Tuple[str, str, float, Dict]:
        """
        Sélectionne automatiquement le meilleur service
        Basé sur le scoring des annotations
        """
        
        best_service = None
        best_operation = None
        best_score = -1
        best_annotations = None
        
        for svc_info in step.available_services:
            service = self.services.get(svc_info['service_name'])
            
            if not service or not service.is_annotated or not service.annotations:
                continue
            
            for operation in svc_info['operations']:
                # Calculer le score avec les annotations
                score = self.scorer.calculate_score(
                    service.annotations,
                    operation,
                    previous_services
                )
                
                if score > best_score:
                    best_score = score
                    best_service = service.name
                    best_operation = operation
                    best_annotations = service.annotations
        
        return best_service, best_operation, best_score, best_annotations
    
    def execute_step(
        self, 
        step: CompositionStep, 
        previous_services: List[str]
    ) -> Dict:
        """Exécute une étape avec sélection automatique intelligente"""
        
        service_name, operation, score, annotations = self.select_best_service(step, previous_services)
        
        if not service_name:
            return None
        
        # Récupérer le temps d'exécution depuis les annotations
        execution_time = 300  # default
        if annotations:
            for ann in annotations['interaction_annotations']:
                if ann['operation'] == operation:
                    execution_time = ann['avg_response_time_ms']
                    break
        
        # Mettre à jour les annotations (augmenter interactions)
        if annotations and step.source_service:
            service = self.services[service_name]
            service.annotations = self.scorer.update_annotations_after_interaction(
                service.annotations,
                operation,
                step.source_service
            )
        
        return {
            'step': step.step_number,
            'source_service': step.source_service,
            'needed_function': step.needed_function,
            'selected_service': service_name,
            'selected_operation': operation,
            'method': 'intelligent',
            'score': score,
            'execution_time': execution_time,
            'annotations_used': annotations
        }
