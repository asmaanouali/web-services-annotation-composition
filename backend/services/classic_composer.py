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
        VRAI algorithme de Dijkstra : Explore le graphe de services pour trouver
        le chemin optimal (meilleure utilité) de l'état initial à l'état final
        """
        result = CompositionResult()
        
        # État initial : (utilité_négative, chemin_services, paramètres_disponibles)
        # On utilise -utilité car heapq est un min-heap et on veut maximiser
        initial_state = (0, [], set(request.provided))
        
        # File de priorité : heap avec (priorité, compteur, état)
        # Le compteur évite les erreurs de comparaison entre sets
        counter = 0
        priority_queue = [(0, counter, initial_state)]
        
        # Dictionnaire des meilleures utilités atteintes pour chaque ensemble de paramètres
        best_utilities = {}
        best_utilities[frozenset(request.provided)] = 0
        
        # Meilleure solution trouvée
        best_solution = None
        best_solution_utility = -float('inf')
        
        # Exploration
        max_iterations = 1000
        iterations = 0
        
        while priority_queue and iterations < max_iterations:
            iterations += 1
            
            # Extraire l'état avec la meilleure utilité cumulée
            neg_utility, _, (current_utility, path, available_params) = heapq.heappop(priority_queue)
            
            # Si on a déjà trouvé mieux pour cet ensemble de paramètres, passer
            params_key = frozenset(available_params)
            if params_key in best_utilities and best_utilities[params_key] > current_utility:
                continue
            
            # Si on a atteint le but (résultat désiré disponible)
            if request.resultant in available_params:
                if current_utility > best_solution_utility:
                    best_solution_utility = current_utility
                    best_solution = path
                continue  # Continue pour voir s'il y a mieux
            
            # Explorer tous les services applicables
            for service in self.services:
                # Éviter les cycles
                if service.id in path:
                    continue
                
                # Le service peut-il s'exécuter ?
                if not service.has_required_inputs(available_params):
                    continue
                
                # Calculer l'utilité de ce service
                qos_checks = service.qos.meets_constraints(request.qos_constraints)
                service_utility = calculate_utility(
                    service.qos,
                    request.qos_constraints,
                    qos_checks
                )
                
                # Nouveau chemin et paramètres
                new_path = path + [service.id]
                new_params = available_params | set(service.outputs)
                new_params_key = frozenset(new_params)
                
                # Calculer l'utilité cumulée (minimum du chemin = maillon le plus faible)
                if path:
                    new_utility = min(current_utility, service_utility)
                else:
                    new_utility = service_utility
                
                # Si on a déjà trouvé mieux pour cet ensemble de paramètres, passer
                if new_params_key in best_utilities and best_utilities[new_params_key] >= new_utility:
                    continue
                
                # Enregistrer cette nouvelle meilleure utilité pour cet ensemble
                best_utilities[new_params_key] = new_utility
                
                # Ajouter à la file de priorité
                counter += 1
                new_state = (new_utility, new_path, new_params)
                heapq.heappush(priority_queue, (-new_utility, counter, new_state))
        
        # Construire le résultat
        if best_solution:
            result.services = [self.service_dict[sid] for sid in best_solution]
            result.workflow = best_solution
            result.utility_value = best_solution_utility
            result.success = True
            
            # Calculer QoS agrégée
            total_response_time = sum(s.qos.response_time for s in result.services)
            min_reliability = min(s.qos.reliability for s in result.services)
            min_availability = min(s.qos.availability for s in result.services)
            
            from models.service import QoS
            result.qos_achieved = QoS(
                response_time=total_response_time,
                reliability=min_reliability,
                availability=min_availability
            )
            
            result.explanation = (
                f"Dijkstra: {len(best_solution)} service(s) - "
                f"{' → '.join(best_solution)} | "
                f"Utilité: {best_solution_utility:.3f} | "
                f"Exploré {iterations} états"
            )
        else:
            result.explanation = f"Aucune composition trouvée après {iterations} itérations"
        
        return result
    
    def _astar_compose(self, request):
        """
        VRAI algorithme A* : Dijkstra + heuristique pour guider la recherche
        f(n) = g(n) + h(n) où:
        - g(n) = utilité du chemin actuel (ce qu'on a déjà)
        - h(n) = heuristique estimant l'utilité potentielle restante
        """
        result = CompositionResult()
        
        # Calculer une heuristique pour chaque service
        # L'heuristique estime la "qualité" potentielle d'un service
        def calculate_heuristic(service, available_params):
            # Heuristique basée sur :
            # 1. La proximité du but (est-ce que ce service produit le résultat ?)
            # 2. La qualité QoS du service
            
            goal_bonus = 1.0 if request.resultant in service.outputs else 0.0
            
            # Normalisation de response_time
            max_response = max((s.qos.response_time for s in self.services), default=1)
            normalized_response = 1 - (service.qos.response_time / max_response) if max_response > 0 else 0
            
            # Heuristique combinée
            h = (
                goal_bonus * 0.5 +  # Bonus important si produit le but
                service.qos.reliability * 0.2 +
                service.qos.availability * 0.2 +
                normalized_response * 0.1
            )
            
            return h
        
        # État initial
        initial_state = (0, 0, [], set(request.provided))  # (g, h, path, params)
        
        counter = 0
        # File de priorité : (f=g+h, compteur, (g, h, path, params))
        priority_queue = [(0, counter, initial_state)]
        
        # Meilleurs scores g pour chaque ensemble de paramètres
        best_g_scores = {}
        best_g_scores[frozenset(request.provided)] = 0
        
        best_solution = None
        best_solution_utility = -float('inf')
        
        max_iterations = 1000
        iterations = 0
        
        while priority_queue and iterations < max_iterations:
            iterations += 1
            
            f_score, _, (g_score, h_score, path, available_params) = heapq.heappop(priority_queue)
            
            # Vérifier si on a déjà mieux pour ces paramètres
            params_key = frozenset(available_params)
            if params_key in best_g_scores and best_g_scores[params_key] > g_score:
                continue
            
            # But atteint ?
            if request.resultant in available_params:
                if g_score > best_solution_utility:
                    best_solution_utility = g_score
                    best_solution = path
                continue
            
            # Explorer les services applicables
            for service in self.services:
                if service.id in path:
                    continue
                
                if not service.has_required_inputs(available_params):
                    continue
                
                # Calculer g(n) - utilité du chemin
                qos_checks = service.qos.meets_constraints(request.qos_constraints)
                service_utility = calculate_utility(
                    service.qos,
                    request.qos_constraints,
                    qos_checks
                )
                
                new_path = path + [service.id]
                new_params = available_params | set(service.outputs)
                new_params_key = frozenset(new_params)
                
                # g(n) = utilité cumulée (minimum)
                new_g = min(g_score, service_utility) if path else service_utility
                
                # h(n) = heuristique
                new_h = calculate_heuristic(service, new_params)
                
                # f(n) = g(n) + h(n)
                new_f = new_g + new_h
                
                # Vérifier si c'est mieux
                if new_params_key in best_g_scores and best_g_scores[new_params_key] >= new_g:
                    continue
                
                best_g_scores[new_params_key] = new_g
                
                # Ajouter à la file (on veut maximiser, donc -f)
                counter += 1
                new_state = (new_g, new_h, new_path, new_params)
                heapq.heappush(priority_queue, (-new_f, counter, new_state))
        
        # Construire le résultat
        if best_solution:
            result.services = [self.service_dict[sid] for sid in best_solution]
            result.workflow = best_solution
            result.utility_value = best_solution_utility
            result.success = True
            
            # QoS agrégée
            total_response_time = sum(s.qos.response_time for s in result.services)
            min_reliability = min(s.qos.reliability for s in result.services)
            min_availability = min(s.qos.availability for s in result.services)
            
            from models.service import QoS
            result.qos_achieved = QoS(
                response_time=total_response_time,
                reliability=min_reliability,
                availability=min_availability
            )
            
            result.explanation = (
                f"A*: {len(best_solution)} service(s) - "
                f"{' → '.join(best_solution)} | "
                f"Utilité: {best_solution_utility:.3f} | "
                f"Exploré {iterations} états (guidé par heuristique)"
            )
        else:
            result.explanation = f"Aucune composition A* trouvée après {iterations} itérations"
        
        return result
    
    def _greedy_compose(self, request):
        """
        Algorithme GLOUTON : Prend la meilleure décision locale à chaque étape
        sans explorer complètement - rapide mais pas optimal
        """
        result = CompositionResult()
        
        available_params = set(request.provided)
        path = []
        utilities = []
        
        max_steps = 10
        steps = 0
        
        while request.resultant not in available_params and steps < max_steps:
            steps += 1
            
            # Trouver tous les services applicables maintenant
            applicable_services = [
                s for s in self.services
                if s.id not in path and s.has_required_inputs(available_params)
            ]
            
            if not applicable_services:
                # Aucun service applicable, échec
                break
            
            # GREEDY: Choisir le service avec la MEILLEURE utilité locale
            best_service = None
            best_local_utility = -float('inf')
            
            for service in applicable_services:
                qos_checks = service.qos.meets_constraints(request.qos_constraints)
                service_utility = calculate_utility(
                    service.qos,
                    request.qos_constraints,
                    qos_checks
                )
                
                # Bonus si ce service produit le résultat désiré
                if request.resultant in service.outputs:
                    service_utility += 10  # Bonus important
                
                if service_utility > best_local_utility:
                    best_local_utility = service_utility
                    best_service = service
            
            if best_service is None:
                break
            
            # Ajouter le service choisi
            path.append(best_service.id)
            available_params.update(best_service.outputs)
            
            # Calculer l'utilité réelle (sans bonus)
            qos_checks = best_service.qos.meets_constraints(request.qos_constraints)
            real_utility = calculate_utility(
                best_service.qos,
                request.qos_constraints,
                qos_checks
            )
            utilities.append(real_utility)
            
            # Si on a atteint le but, arrêter
            if request.resultant in available_params:
                break
        
        # Construire le résultat
        if request.resultant in available_params:
            result.services = [self.service_dict[sid] for sid in path]
            result.workflow = path
            result.utility_value = min(utilities) if utilities else 0
            result.success = True
            
            # QoS agrégée
            total_response_time = sum(s.qos.response_time for s in result.services)
            min_reliability = min(s.qos.reliability for s in result.services)
            min_availability = min(s.qos.availability for s in result.services)
            
            from models.service import QoS
            result.qos_achieved = QoS(
                response_time=total_response_time,
                reliability=min_reliability,
                availability=min_availability
            )
            
            result.explanation = (
                f"Greedy: {len(path)} service(s) - "
                f"{' → '.join(path)} | "
                f"Utilité: {result.utility_value:.3f} | "
                f"{steps} décisions locales"
            )
        else:
            result.explanation = f"Greedy n'a pas trouvé de composition après {steps} étapes"
        
        return result
    
    def compose_sequential(self, request):
        """
        Composition séquentielle simple - construit une chaîne de services
        en minimisant le nombre d'étapes
        """
        result = CompositionResult()
        start_time = time.time()
        
        available_params = set(request.provided)
        used_services = []
        utilities = []
        
        total_response_time = 0
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
            
            qos_checks = next_service.qos.meets_constraints(request.qos_constraints)
            utility = calculate_utility(
                next_service.qos,
                request.qos_constraints,
                qos_checks
            )
            utilities.append(utility)
            
            total_response_time += next_service.qos.response_time
            min_reliability = min(min_reliability, next_service.qos.reliability)
            min_availability = min(min_availability, next_service.qos.availability)
        
        if request.resultant in available_params:
            result.services = used_services
            result.workflow = [s.id for s in used_services]
            result.utility_value = min(utilities) if utilities else 0
            
            from models.service import QoS
            result.qos_achieved = QoS(
                response_time=total_response_time,
                reliability=min_reliability,
                availability=min_availability
            )
            
            result.success = True
            result.explanation = (
                f"Séquentiel: {len(used_services)} service(s) | "
                f"Utilité: {result.utility_value:.3f}"
            )
        else:
            result.explanation = f"Séquentiel impossible après {iterations} itérations"
        
        result.computation_time = time.time() - start_time
        
        return result