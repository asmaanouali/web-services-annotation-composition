import random
from typing import List, Dict, Tuple
from src.models.service import Service
from src.models.composition import CompositionStep

class ClassicComposer:
    """
    Composition classique - Approche traditionnelle automatique
    N'UTILISE PAS les annotations sémantiques enrichies
    Sélection basée sur des critères simples: ordre alphabétique, disponibilité
    """
    
    def __init__(self, services: List[Service]):
        self.services = {s.name: s for s in services}
    
    def select_service_traditional(
        self, 
        step: CompositionStep
    ) -> Tuple[str, str]:
        """
        Sélection traditionnelle automatique basée sur des critères simples:
        1. Ordre alphabétique (déterministe)
        2. Première opération disponible
        
        Cette approche NE considère PAS:
        - Les annotations sémantiques
        - L'historique d'interactions
        - Les scores de qualité
        - Le contexte
        """
        
        if not step.available_services:
            return None, None
        
        # Trier par ordre alphabétique (approche traditionnelle déterministe)
        sorted_services = sorted(
            step.available_services, 
            key=lambda x: x['service_name']
        )
        
        # Prendre le premier service alphabétiquement
        selected = sorted_services[0]
        selected_service = selected['service_name']
        
        # Prendre la première opération disponible
        selected_operation = selected['operations'][0] if selected['operations'] else None
        
        return selected_service, selected_operation
    
    def execute_step(self, step: CompositionStep) -> Dict:
        """
        Exécute une étape de composition classique avec sélection automatique
        Basée uniquement sur l'ordre alphabétique et la disponibilité
        """
        
        service_name, operation = self.select_service_traditional(step)
        
        if not service_name or not operation:
            return None
        
        # Temps d'exécution simulé (valeur par défaut sans optimisation)
        # Dans l'approche classique, on n'a pas d'info sur les performances
        execution_time = random.randint(200, 400)
        
        return {
            'step': step.step_number,
            'source_service': step.source_service,
            'needed_function': step.needed_function,
            'selected_service': service_name,
            'selected_operation': operation,
            'method': 'classic',
            'score': None,  # Pas de scoring dans l'approche classique
            'execution_time': execution_time,
            'annotations_used': None,  # N'utilise pas les annotations
            'selection_criteria': 'alphabetical_order'  # Critère utilisé
        }