"""
Solution A: Composition classique de services web
Utilise des algorithmes de recherche classiques (Dijkstra, A*)
CORRECTED VERSION - Corrections des bugs uniquement
"""

import time
import heapq
from models.service import CompositionResult
from utils.qos_calculator import calculate_utility


class ClassicComposer:
    def __init__(self, services):
        self.services = services
        self.service_dict = {s.id: s for s in services}
    
    def compose(self, request, algorithm="dijkstra"):
        """
        Compose des services pour répondre à une requête
        
        Args:
            request: CompositionRequest
            algorithm: "dijkstra", "astar", ou "greedy"
        
        Returns:
            CompositionResult
        """
        start_time = time.time()
        result = CompositionResult()
        
        try:
            if algorithm == "dijkstra":
                result = self._dijkstra_compose(request)
            elif algorithm == "astar":
                result = self._astar_compose(request)
            else:
                result = self._greedy_compose(request)
            
            result.computation_time = time.time() - start_time
            result.success = len(result.services) > 0
        
        except Exception as e:
            print(f"Erreur de composition: {e}")
            result.success = False
            result.explanation = f"Erreur: {str(e)}"
            result.computation_time = time.time() - start_time
        
        return result
    
    def _dijkstra_compose(self, request):
        """
        Composition utilisant l'algorithme de Dijkstra pour trouver la solution optimale
        """
        result = CompositionResult()
        
        # Étape 1: Trouver tous les services qui peuvent produire le résultat désiré
        candidate_services = [
            s for s in self.services
            if request.resultant in s.outputs
        ]
        
        if not candidate_services:
            result.explanation = f"Aucun service ne peut produire '{request.resultant}'"
            return result
        
        # Étape 2: Filtrer les services qui ont tous leurs inputs disponibles
        valid_services = [
            s for s in candidate_services
            if s.has_required_inputs(request.provided)
        ]
        
        if not valid_services:
            result.explanation = f"Aucun service candidat n'a tous ses inputs disponibles parmi: {', '.join(request.provided)}"
            return result
        
        # Étape 3: Évaluer TOUS les services valides
        services_evaluated = []
        
        for service in valid_services:
            qos_checks = service.qos.meets_constraints(request.qos_constraints)
            constraints_met = sum(qos_checks.values())
            total_constraints = len(qos_checks)
            constraints_ratio = constraints_met / total_constraints if total_constraints > 0 else 0
            
            utility = calculate_utility(
                service.qos,
                request.qos_constraints,
                qos_checks
            )
            
            services_evaluated.append({
                'service': service,
                'utility': utility,
                'constraints_met': constraints_met,
                'total_constraints': total_constraints,
                'constraints_ratio': constraints_ratio,
                'qos_checks': qos_checks
            })
        
        if not services_evaluated:
            result.explanation = "Aucun service n'a pu être évalué"
            return result
        
        # CORRECTION: Trier par UTILITÉ en premier (critère principal), puis contraintes
        services_evaluated.sort(
            key=lambda x: (x['utility'], x['constraints_ratio']), 
            reverse=True
        )
        
        best_candidate = services_evaluated[0]
        best_service = best_candidate['service']
        
        result.services = [best_service]
        result.workflow = [best_service.id]
        result.utility_value = best_candidate['utility']
        result.qos_achieved = best_service.qos
        result.success = True
        
        result.explanation = (
            f"Dijkstra optimal: Service '{best_service.id}' sélectionné | "
            f"Utilité: {best_candidate['utility']:.2f} | "
            f"Contraintes: {best_candidate['constraints_met']}/{best_candidate['total_constraints']} "
            f"({best_candidate['constraints_ratio']*100:.1f}%)"
        )
        
        return result
    
    def _astar_compose(self, request):
        """
        A* avec heuristique basée sur la QoS
        """
        result = CompositionResult()
        
        candidate_services = [
            s for s in self.services
            if request.resultant in s.outputs
        ]
        
        if not candidate_services:
            result.explanation = f"Aucun service ne peut produire '{request.resultant}'"
            return result
        
        valid_services = [
            s for s in candidate_services
            if s.has_required_inputs(request.provided)
        ]
        
        if not valid_services:
            result.explanation = f"Aucun service n'a tous les inputs requis"
            return result
        
        services_evaluated = []
        
        for service in valid_services:
            qos_checks = service.qos.meets_constraints(request.qos_constraints)
            constraints_met = sum(qos_checks.values())
            total_constraints = len(qos_checks)
            constraints_ratio = constraints_met / total_constraints if total_constraints > 0 else 0
            
            utility = calculate_utility(
                service.qos,
                request.qos_constraints,
                qos_checks
            )
            
            # CORRECTION: Heuristique améliorée avec normalisation
            max_response = max((s.qos.response_time for s in valid_services), default=1)
            max_cost = max((s.qos.cost for s in valid_services), default=1)
            
            normalized_response = 1 - (service.qos.response_time / max_response) if max_response > 0 else 0
            normalized_cost = 1 - (service.qos.cost / max_cost) if max_cost > 0 else 0
            
            heuristic = (
                service.qos.reliability * 0.3 +
                service.qos.availability * 0.3 +
                normalized_response * 0.2 +
                normalized_cost * 0.2
            )
            
            astar_score = utility + heuristic
            
            services_evaluated.append({
                'service': service,
                'utility': utility,
                'heuristic': heuristic,
                'astar_score': astar_score,
                'constraints_met': constraints_met,
                'total_constraints': total_constraints,
                'constraints_ratio': constraints_ratio
            })
        
        if not services_evaluated:
            result.explanation = "Aucun service n'a pu être évalué"
            return result
        
        # CORRECTION: Trier par score A* en premier
        services_evaluated.sort(
            key=lambda x: (x['astar_score'], x['utility']), 
            reverse=True
        )
        
        best_candidate = services_evaluated[0]
        best_service = best_candidate['service']
        
        result.services = [best_service]
        result.workflow = [best_service.id]
        result.utility_value = best_candidate['utility']
        result.qos_achieved = best_service.qos
        result.success = True
        
        result.explanation = (
            f"A* optimal: Service '{best_service.id}' | "
            f"Utilité: {best_candidate['utility']:.2f} | "
            f"Heuristique: {best_candidate['heuristic']:.2f} | "
            f"Score A*: {best_candidate['astar_score']:.2f} | "
            f"Contraintes: {best_candidate['constraints_met']}/{best_candidate['total_constraints']}"
        )
        
        return result
    
    def _greedy_compose(self, request):
        """
        CORRECTION: Composition gloutonne basée sur l'utilité maximale
        """
        result = CompositionResult()
        
        candidate_services = [
            s for s in self.services
            if request.resultant in s.outputs and s.has_required_inputs(request.provided)
        ]
        
        if not candidate_services:
            result.explanation = "Aucun service candidat trouvé (greedy)"
            return result
        
        # Évaluer tous les candidats
        services_with_utility = []
        
        for service in candidate_services:
            qos_checks = service.qos.meets_constraints(request.qos_constraints)
            utility = calculate_utility(
                service.qos,
                request.qos_constraints,
                qos_checks
            )
            
            constraints_met = sum(qos_checks.values())
            total_constraints = len(qos_checks)
            
            services_with_utility.append({
                'service': service,
                'utility': utility,
                'constraints_met': constraints_met,
                'total_constraints': total_constraints
            })
        
        # CORRECTION: Prendre le service avec la MEILLEURE UTILITÉ (pas juste reliability)
        best = max(services_with_utility, key=lambda x: x['utility'])
        best_service = best['service']
        
        result.services = [best_service]
        result.workflow = [best_service.id]
        result.utility_value = best['utility']
        result.qos_achieved = best_service.qos
        result.success = True
        
        result.explanation = (
            f"Greedy: Service '{best_service.id}' (meilleure utilité: {best['utility']:.2f}) | "
            f"Reliability: {best_service.qos.reliability:.2f} | "
            f"Contraintes: {best['constraints_met']}/{best['total_constraints']}"
        )
        
        return result
    
    def compose_sequential(self, request):
        """
        CORRECTION: Composition séquentielle avec agrégation correcte
        """
        result = CompositionResult()
        start_time = time.time()
        
        available_params = set(request.provided)
        used_services = []
        utilities = []
        
        # CORRECTION: Variables pour agréger les QoS
        total_response_time = 0
        total_cost = 0
        min_reliability = 1.0
        min_availability = 1.0
        
        max_iterations = 10
        iterations = 0
        
        while request.resultant not in available_params and iterations < max_iterations:
            iterations += 1
            
            next_service = None
            best_contribution = -1
            
            for service in self.services:
                if service.id in [s.id for s in used_services]:
                    continue
                
                if service.has_required_inputs(available_params):
                    new_outputs = set(service.outputs) - available_params
                    contribution = len(new_outputs)
                    
                    if request.resultant in service.outputs:
                        contribution += 100
                    
                    if contribution > best_contribution:
                        best_contribution = contribution
                        next_service = service
            
            if next_service is None:
                break
            
            used_services.append(next_service)
            available_params.update(next_service.outputs)
            
            # Calculer l'utilité
            qos_checks = next_service.qos.meets_constraints(request.qos_constraints)
            utility = calculate_utility(
                next_service.qos,
                request.qos_constraints,
                qos_checks
            )
            utilities.append(utility)
            
            # CORRECTION: Agréger les QoS correctement
            total_response_time += next_service.qos.response_time
            total_cost += next_service.qos.cost
            min_reliability = min(min_reliability, next_service.qos.reliability)
            min_availability = min(min_availability, next_service.qos.availability)
        
        if request.resultant in available_params:
            result.services = used_services
            result.workflow = [s.id for s in used_services]
            
            # CORRECTION: Utilité = MINIMUM (une chaîne = son maillon le plus faible)
            result.utility_value = min(utilities) if utilities else 0
            
            # CORRECTION: Créer/mettre à jour QoS agrégée
            from models.service import QoS
            result.qos_achieved = QoS(
                response_time=total_response_time,
                cost=total_cost,
                reliability=min_reliability,
                availability=min_availability
            )
            
            result.success = True
            result.explanation = (
                f"Composition séquentielle de {len(used_services)} service(s) | "
                f"Utilité minimale: {result.utility_value:.2f}"
            )
        else:
            result.explanation = "Impossible de produire le résultat désiré"
        
        result.computation_time = time.time() - start_time
        
        return result