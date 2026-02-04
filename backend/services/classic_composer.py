"""
Solution A: Composition classique de services web
Utilise des algorithmes de recherche classiques (Dijkstra, A*)
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
            # FIX: Success if we found at least one service, not based on utility
            result.success = len(result.services) > 0
        
        except Exception as e:
            print(f"Erreur de composition: {e}")
            result.success = False
            result.explanation = f"Erreur: {str(e)}"
            result.computation_time = time.time() - start_time
        
        return result
    
    def _dijkstra_compose(self, request):
        """Composition utilisant l'algorithme de Dijkstra modifié"""
        result = CompositionResult()
        
        # Trouver tous les services qui peuvent produire le résultat désiré
        candidate_services = [
            s for s in self.services
            if request.resultant in s.outputs
        ]
        
        if not candidate_services:
            result.explanation = f"Aucun service ne peut produire {request.resultant}"
            return result
        
        # Filtrer les services qui ont tous leurs inputs disponibles
        valid_services = [
            s for s in candidate_services
            if s.has_required_inputs(request.provided)
        ]
        
        if not valid_services:
            result.explanation = f"Aucun service n'a tous les inputs requis"
            return result
        
        # Calculer l'utilité pour chaque service valide
        best_service = None
        best_utility = -float('inf')
        
        for service in valid_services:
            # Vérifier les contraintes QoS
            qos_checks = service.qos.meets_constraints(request.qos_constraints)
            
            # Calculer l'utilité
            utility = calculate_utility(
                service.qos,
                request.qos_constraints,
                qos_checks
            )
            
            if utility > best_utility:
                best_utility = utility
                best_service = service
        
        if best_service:
            result.services = [best_service]
            result.workflow = [best_service.id]
            result.utility_value = best_utility
            result.qos_achieved = best_service.qos
            result.success = True
            result.explanation = f"Service {best_service.id} sélectionné avec utilité {best_utility:.2f}"
        else:
            result.explanation = "Aucun service ne satisfait les contraintes"
        
        return result
    
    def _astar_compose(self, request):
        """Composition utilisant A* (similaire à Dijkstra pour ce cas)"""
        # Pour cette version simplifiée, A* est similaire à Dijkstra
        # avec une heuristique basée sur la QoS
        result = self._dijkstra_compose(request)
        result.explanation = result.explanation.replace("Dijkstra", "A*")
        return result
    
    def _greedy_compose(self, request):
        """Composition gloutonne - sélectionne le meilleur service directement"""
        result = CompositionResult()
        
        # Trouver le service avec la meilleure QoS qui peut produire le résultat
        candidate_services = [
            s for s in self.services
            if request.resultant in s.outputs and s.has_required_inputs(request.provided)
        ]
        
        if not candidate_services:
            result.explanation = "Aucun service candidat trouvé"
            return result
        
        # Trier par reliability (approche gloutonne)
        candidate_services.sort(key=lambda s: s.qos.reliability, reverse=True)
        
        best_service = candidate_services[0]
        
        # Calculer l'utilité
        qos_checks = best_service.qos.meets_constraints(request.qos_constraints)
        utility = calculate_utility(
            best_service.qos,
            request.qos_constraints,
            qos_checks
        )
        
        result.services = [best_service]
        result.workflow = [best_service.id]
        result.utility_value = utility
        result.qos_achieved = best_service.qos
        result.success = True
        result.explanation = f"Approche gloutonne: {best_service.id} (reliability: {best_service.qos.reliability:.2f})"
        
        return result
    
    def _build_service_graph(self):
        """Construit un graphe de dépendances entre services"""
        graph = {}
        
        for service in self.services:
            neighbors = []
            
            # Trouver les services qui peuvent suivre ce service
            for other in self.services:
                if other.id == service.id:
                    continue
                
                # Si les outputs de service matchent les inputs de other
                if any(out in other.inputs for out in service.outputs):
                    neighbors.append(other.id)
            
            graph[service.id] = neighbors
        
        return graph
    
    def compose_sequential(self, request):
        """
        Composition séquentielle - construit une chaîne de services
        (plus complexe, pour des requêtes nécessitant plusieurs services)
        """
        result = CompositionResult()
        start_time = time.time()
        
        # État initial
        available_params = set(request.provided)
        used_services = []
        total_utility = 0
        
        # Tant qu'on n'a pas le résultat désiré
        max_iterations = 10
        iterations = 0
        
        while request.resultant not in available_params and iterations < max_iterations:
            iterations += 1
            
            # Trouver un service qui peut s'exécuter avec les paramètres disponibles
            next_service = None
            best_contribution = -1
            
            for service in self.services:
                if service.id in [s.id for s in used_services]:
                    continue
                
                if service.has_required_inputs(available_params):
                    # Calculer la contribution (nouveaux outputs produits)
                    new_outputs = set(service.outputs) - available_params
                    contribution = len(new_outputs)
                    
                    # Bonus si produit le résultat désiré
                    if request.resultant in service.outputs:
                        contribution += 100
                    
                    if contribution > best_contribution:
                        best_contribution = contribution
                        next_service = service
            
            if next_service is None:
                break
            
            # Ajouter le service
            used_services.append(next_service)
            available_params.update(next_service.outputs)
            
            # Calculer l'utilité
            qos_checks = next_service.qos.meets_constraints(request.qos_constraints)
            utility = calculate_utility(
                next_service.qos,
                request.qos_constraints,
                qos_checks
            )
            total_utility += utility
        
        # Construire le résultat
        if request.resultant in available_params:
            result.services = used_services
            result.workflow = [s.id for s in used_services]
            result.utility_value = total_utility / len(used_services) if used_services else 0
            result.success = True
            result.explanation = f"Composition séquentielle de {len(used_services)} service(s)"
        else:
            result.explanation = "Impossible de produire le résultat désiré"
        
        result.computation_time = time.time() - start_time
        
        return result