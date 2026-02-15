"""
Solution A: Classic Web Service Composition
Real implementations of Dijkstra, A*, and Greedy algorithms
WITH full algorithm trace for step-by-step visualization
"""

import time
import heapq
from models.service import CompositionResult, QoS
from utils.qos_calculator import calculate_utility


class ClassicComposer:
    def __init__(self, services):
        self.services = services
        self.service_dict = {s.id: s for s in services}
    
    def compose(self, request, algorithm="dijkstra"):
        """
        Compose services to satisfy a request.
        Returns CompositionResult with algorithm trace and graph data.
        """
        start_time = time.time()
        result = CompositionResult()
        result.algorithm_used = algorithm
        
        try:
            # Build the service dependency graph for visualization
            graph_data = self._build_service_graph(request)
            
            if algorithm == "dijkstra":
                result = self._dijkstra_compose(request)
            elif algorithm == "astar":
                result = self._astar_compose(request)
            else:
                result = self._greedy_compose(request)
            
            result.computation_time = time.time() - start_time
            result.success = len(result.services) > 0
            result.algorithm_used = algorithm
            
            # Attach graph data with path info
            if result.workflow:
                graph_data['path'] = result.workflow
                # Mark nodes/edges that are in the final path
                path_set = set(result.workflow)
                for node in graph_data['nodes']:
                    node['in_path'] = node['id'] in path_set
                for edge in graph_data['edges']:
                    src_in = edge['from'] in path_set or edge['from'] == 'START'
                    tgt_in = edge['to'] in path_set or edge['to'] == 'END'
                    edge['in_path'] = src_in and tgt_in
            
            result.graph_data = graph_data
        
        except Exception as e:
            print(f"Composition error: {e}")
            import traceback
            traceback.print_exc()
            result.success = False
            result.explanation = f"Error: {str(e)}"
            result.computation_time = time.time() - start_time
        
        return result
    
    def _build_service_graph(self, request):
        """
        Build the service dependency graph for a given request.
        Returns nodes and edges for SVG visualization.
        """
        # Find all candidate services
        candidates = []
        for s in self.services:
            if s.has_required_inputs(request.provided) or request.resultant in s.outputs:
                candidates.append(s)
        
        # Also find chaining candidates (services whose inputs come from other candidates' outputs)
        candidate_ids = set(c.id for c in candidates)
        all_outputs = set()
        for c in candidates:
            all_outputs.update(c.outputs)
        
        for s in self.services:
            if s.id not in candidate_ids and s.has_required_inputs(all_outputs | set(request.provided)):
                candidates.append(s)
                candidate_ids.add(s.id)
        
        # Limit for visualization (top 40 by reliability)
        candidates = sorted(candidates, key=lambda s: s.qos.reliability, reverse=True)[:40]
        
        # Build nodes
        nodes = [{'id': 'START', 'type': 'start', 'label': 'START', 'params': request.provided[:5]}]
        
        for s in candidates:
            qos_checks = s.qos.meets_constraints(request.qos_constraints)
            utility = calculate_utility(s.qos, request.qos_constraints, qos_checks)
            nodes.append({
                'id': s.id,
                'type': 'service',
                'label': s.id,
                'inputs': s.inputs[:3],
                'outputs': s.outputs[:3],
                'utility': round(utility, 2),
                'reliability': round(s.qos.reliability, 1),
                'response_time': round(s.qos.response_time, 1),
                'explored': False,
                'in_path': False
            })
        
        nodes.append({'id': 'END', 'type': 'end', 'label': 'END', 'param': request.resultant})
        
        # Build edges
        edges = []
        for s in candidates:
            # START -> service (if service can use provided params)
            if s.has_required_inputs(request.provided):
                edges.append({
                    'from': 'START', 'to': s.id,
                    'type': 'input', 'in_path': False
                })
            
            # service -> END (if service produces the resultant)
            if request.resultant in s.outputs:
                edges.append({
                    'from': s.id, 'to': 'END',
                    'type': 'output', 'in_path': False
                })
            
            # service -> service (chaining through I/O)
            for s2 in candidates:
                if s.id != s2.id:
                    common = set(s.outputs) & set(s2.inputs)
                    if common:
                        edges.append({
                            'from': s.id, 'to': s2.id,
                            'type': 'chain', 'in_path': False,
                            'shared_params': list(common)[:2]
                        })
        
        return {'nodes': nodes, 'edges': edges, 'path': []}
    
    # ================================================================
    # DIJKSTRA ALGORITHM - Full implementation with trace
    # ================================================================
    
    def _dijkstra_compose(self, request):
        """
        Real Dijkstra algorithm: explores the service graph to find
        the optimal path (best utility) from initial state to goal state.
        Records every exploration step for visualization.
        """
        result = CompositionResult()
        trace = []
        
        # Initial state: (negative_utility, path, available_params)
        initial_state = (0, [], set(request.provided))
        
        counter = 0
        priority_queue = [(0, counter, initial_state)]
        
        # Best utilities for each parameter set
        best_utilities = {}
        best_utilities[frozenset(request.provided)] = 0
        
        best_solution = None
        best_solution_utility = -float('inf')
        
        max_iterations = 10000000
        iterations = 0
        explored_services = set()
        
        # Record initial state
        trace.append({
            'step': 0,
            'action': 'init',
            'description': f'Initialize with {len(request.provided)} provided parameters',
            'available_params': list(request.provided)[:5],
            'queue_size': 1,
            'best_utility': 0
        })
        
        while priority_queue and iterations < max_iterations:
            iterations += 1
            
            neg_utility, _, (current_utility, path, available_params) = heapq.heappop(priority_queue)
            
            params_key = frozenset(available_params)
            if params_key in best_utilities and best_utilities[params_key] > current_utility:
                continue
            
            # Goal reached
            if request.resultant in available_params:
                if current_utility > best_solution_utility:
                    best_solution_utility = current_utility
                    best_solution = path
                    
                    trace.append({
                        'step': iterations,
                        'action': 'goal_found',
                        'description': f'Goal reached! Path: {" → ".join(path)}',
                        'path': path.copy(),
                        'utility': round(current_utility, 3),
                        'service_id': path[-1] if path else None
                    })
                continue
            
            # Explore applicable services
            applicable = []
            for service in self.services:
                if service.id in path:
                    continue
                if not service.has_required_inputs(available_params):
                    continue
                applicable.append(service)
            
            if applicable and iterations <= 50:  # Trace first 50 steps
                trace.append({
                    'step': iterations,
                    'action': 'explore',
                    'description': f'Exploring from state with {len(available_params)} params, {len(applicable)} candidates',
                    'current_path': path.copy(),
                    'candidates_count': len(applicable),
                    'queue_size': len(priority_queue)
                })
            
            for service in applicable:
                explored_services.add(service.id)
                
                qos_checks = service.qos.meets_constraints(request.qos_constraints)
                service_utility = calculate_utility(
                    service.qos, request.qos_constraints, qos_checks
                )
                
                new_path = path + [service.id]
                new_params = available_params | set(service.outputs)
                new_params_key = frozenset(new_params)
                
                new_utility = min(current_utility, service_utility) if path else service_utility
                
                if new_params_key in best_utilities and best_utilities[new_params_key] >= new_utility:
                    continue
                
                best_utilities[new_params_key] = new_utility
                
                counter += 1
                new_state = (new_utility, new_path, new_params)
                heapq.heappush(priority_queue, (-new_utility, counter, new_state))
                
                # Record significant expansions
                if iterations <= 30 and request.resultant in service.outputs:
                    trace.append({
                        'step': iterations,
                        'action': 'expand',
                        'service_id': service.id,
                        'description': f'Service {service.id} can produce target! Utility: {service_utility:.2f}',
                        'utility': round(service_utility, 3),
                        'new_params': list(set(service.outputs) - available_params)[:3],
                        'produces_goal': True
                    })
        
        # Build result
        if best_solution:
            result.services = [self.service_dict[sid] for sid in best_solution]
            result.workflow = best_solution
            result.utility_value = best_solution_utility
            result.success = True
            result.states_explored = iterations
            
            total_rt = sum(s.qos.response_time for s in result.services)
            min_rel = min(s.qos.reliability for s in result.services)
            min_avail = min(s.qos.availability for s in result.services)
            
            result.qos_achieved = QoS(
                response_time=total_rt,
                reliability=min_rel,
                availability=min_avail
            )
            
            # Record final summary
            trace.append({
                'step': iterations,
                'action': 'complete',
                'description': f'Dijkstra complete: {len(best_solution)} service(s), utility={best_solution_utility:.3f}',
                'final_path': best_solution,
                'total_explored': iterations,
                'unique_services_seen': len(explored_services)
            })
            
            result.explanation = (
                f"Dijkstra Algorithm: {len(best_solution)} service(s) selected\n"
                f"Path: {' → '.join(best_solution)}\n"
                f"Utility Score: {best_solution_utility:.3f}\n"
                f"States Explored: {iterations} | Services Evaluated: {len(explored_services)}"
            )
        else:
            trace.append({
                'step': iterations,
                'action': 'failed',
                'description': f'No composition found after {iterations} iterations',
                'total_explored': iterations
            })
            result.explanation = f"No composition found after {iterations} iterations"
        
        result.algorithm_trace = trace
        return result
    
    # ================================================================
    # A* ALGORITHM - Full implementation with trace
    # ================================================================
    
    def _astar_compose(self, request):
        """
        Real A* algorithm: Dijkstra + heuristic to guide search.
        f(n) = g(n) + h(n)
        - g(n) = utility of current path
        - h(n) = heuristic estimating remaining potential
        Records every step for visualization.
        """
        result = CompositionResult()
        trace = []
        
        def calculate_heuristic(service, available_params):
            """Heuristic: estimates how promising a service is"""
            # Big bonus if service directly produces the goal
            goal_bonus = 1.0 if request.resultant in service.outputs else 0.0
            
            # How many new parameters does it add?
            new_params = set(service.outputs) - available_params
            novelty = len(new_params) / max(len(service.outputs), 1)
            
            # QoS quality
            max_rt = max((s.qos.response_time for s in self.services), default=1)
            norm_rt = 1 - (service.qos.response_time / max_rt) if max_rt > 0 else 0
            
            h = (
                goal_bonus * 0.5 +
                service.qos.reliability / 100 * 0.2 +
                service.qos.availability / 100 * 0.2 +
                norm_rt * 0.05 +
                novelty * 0.05
            )
            return h
        
        initial_state = (0, 0, [], set(request.provided))
        counter = 0
        priority_queue = [(0, counter, initial_state)]
        best_g_scores = {}
        best_g_scores[frozenset(request.provided)] = 0
        
        best_solution = None
        best_solution_utility = -float('inf')
        explored_services = set()
        
        max_iterations = 10000000
        iterations = 0
        
        trace.append({
            'step': 0,
            'action': 'init',
            'description': f'A* initialized with heuristic guidance. {len(request.provided)} initial params.',
            'available_params': list(request.provided)[:5]
        })
        
        while priority_queue and iterations < max_iterations:
            iterations += 1
            
            f_score, _, (g_score, h_score, path, available_params) = heapq.heappop(priority_queue)
            
            params_key = frozenset(available_params)
            if params_key in best_g_scores and best_g_scores[params_key] > g_score:
                continue
            
            if request.resultant in available_params:
                if g_score > best_solution_utility:
                    best_solution_utility = g_score
                    best_solution = path
                    
                    trace.append({
                        'step': iterations,
                        'action': 'goal_found',
                        'description': f'Goal reached via A*! f={-f_score:.3f} (g={g_score:.3f}, h={h_score:.3f})',
                        'path': path.copy(),
                        'utility': round(g_score, 3),
                        'f_score': round(-f_score, 3),
                        'g_score': round(g_score, 3),
                        'h_score': round(h_score, 3),
                        'service_id': path[-1] if path else None
                    })
                continue
            
            applicable = [
                s for s in self.services
                if s.id not in path and s.has_required_inputs(available_params)
            ]
            
            if applicable and iterations <= 50:
                trace.append({
                    'step': iterations,
                    'action': 'explore',
                    'description': f'A* expanding: {len(applicable)} candidates, f={-f_score:.3f}',
                    'current_path': path.copy(),
                    'candidates_count': len(applicable),
                    'f_score': round(-f_score, 3)
                })
            
            for service in applicable:
                explored_services.add(service.id)
                
                qos_checks = service.qos.meets_constraints(request.qos_constraints)
                service_utility = calculate_utility(
                    service.qos, request.qos_constraints, qos_checks
                )
                
                new_path = path + [service.id]
                new_params = available_params | set(service.outputs)
                new_params_key = frozenset(new_params)
                
                new_g = min(g_score, service_utility) if path else service_utility
                new_h = calculate_heuristic(service, new_params)
                new_f = new_g + new_h
                
                if new_params_key in best_g_scores and best_g_scores[new_params_key] >= new_g:
                    continue
                
                best_g_scores[new_params_key] = new_g
                
                counter += 1
                new_state = (new_g, new_h, new_path, new_params)
                heapq.heappush(priority_queue, (-new_f, counter, new_state))
                
                if iterations <= 30 and request.resultant in service.outputs:
                    trace.append({
                        'step': iterations,
                        'action': 'heuristic_boost',
                        'service_id': service.id,
                        'description': f'A* heuristic boost: {service.id} produces goal! h={new_h:.3f}',
                        'utility': round(service_utility, 3),
                        'heuristic': round(new_h, 3),
                        'f_score': round(new_f, 3),
                        'produces_goal': True
                    })
        
        if best_solution:
            result.services = [self.service_dict[sid] for sid in best_solution]
            result.workflow = best_solution
            result.utility_value = best_solution_utility
            result.success = True
            result.states_explored = iterations
            
            total_rt = sum(s.qos.response_time for s in result.services)
            min_rel = min(s.qos.reliability for s in result.services)
            min_avail = min(s.qos.availability for s in result.services)
            
            result.qos_achieved = QoS(
                response_time=total_rt,
                reliability=min_rel,
                availability=min_avail
            )
            
            trace.append({
                'step': iterations,
                'action': 'complete',
                'description': f'A* complete: {len(best_solution)} service(s), guided by heuristic',
                'final_path': best_solution,
                'total_explored': iterations,
                'unique_services_seen': len(explored_services)
            })
            
            result.explanation = (
                f"A* Algorithm (heuristic-guided): {len(best_solution)} service(s) selected\n"
                f"Path: {' → '.join(best_solution)}\n"
                f"Utility Score: {best_solution_utility:.3f}\n"
                f"States Explored: {iterations} | Heuristic-guided exploration"
            )
        else:
            trace.append({
                'step': iterations,
                'action': 'failed',
                'description': f'A* found no composition after {iterations} iterations'
            })
            result.explanation = f"No A* composition found after {iterations} iterations"
        
        result.algorithm_trace = trace
        return result
    
    # ================================================================
    # GREEDY ALGORITHM - Full implementation with trace
    # ================================================================
    
    def _greedy_compose(self, request):
        """
        Greedy algorithm: at each step, picks the locally best service.
        Fast but not guaranteed optimal.
        Records each greedy decision for visualization.
        """
        result = CompositionResult()
        trace = []
        
        available_params = set(request.provided)
        path = []
        utilities = []
        explored_services = set()
        
        max_steps = 10
        steps = 0
        
        trace.append({
            'step': 0,
            'action': 'init',
            'description': f'Greedy initialized: looking for {request.resultant}',
            'available_params': list(request.provided)[:5],
            'target': request.resultant
        })
        
        while request.resultant not in available_params and steps < max_steps:
            steps += 1
            
            # Find all applicable services
            applicable = [
                s for s in self.services
                if s.id not in path and s.has_required_inputs(available_params)
            ]
            
            if not applicable:
                trace.append({
                    'step': steps,
                    'action': 'dead_end',
                    'description': f'No applicable services found. Dead end at step {steps}.'
                })
                break
            
            explored_services.update(s.id for s in applicable)
            
            # Evaluate all candidates
            candidates_eval = []
            for service in applicable:
                qos_checks = service.qos.meets_constraints(request.qos_constraints)
                utility = calculate_utility(
                    service.qos, request.qos_constraints, qos_checks
                )
                
                # Bonus if produces the target
                bonus = 100 if request.resultant in service.outputs else 0
                
                candidates_eval.append({
                    'service': service,
                    'utility': utility,
                    'score': utility + bonus,
                    'produces_goal': request.resultant in service.outputs,
                    'new_params': list(set(service.outputs) - available_params)
                })
            
            # Sort by score (greedy: pick the best)
            candidates_eval.sort(key=lambda x: x['score'], reverse=True)
            
            best = candidates_eval[0]
            best_service = best['service']
            
            # Record the greedy decision with alternatives
            trace.append({
                'step': steps,
                'action': 'greedy_choice',
                'service_id': best_service.id,
                'description': (
                    f'Step {steps}: Selected {best_service.id} '
                    f'(utility={best["utility"]:.2f}) from {len(applicable)} candidates'
                ),
                'utility': round(best['utility'], 3),
                'candidates_count': len(applicable),
                'produces_goal': best['produces_goal'],
                'new_params': best['new_params'][:3],
                'top_3': [
                    {'id': c['service'].id, 'utility': round(c['utility'], 2), 'produces_goal': c['produces_goal']}
                    for c in candidates_eval[:3]
                ],
                'rejected_count': len(applicable) - 1
            })
            
            # Apply the greedy choice
            path.append(best_service.id)
            available_params.update(best_service.outputs)
            
            qos_checks = best_service.qos.meets_constraints(request.qos_constraints)
            real_utility = calculate_utility(
                best_service.qos, request.qos_constraints, qos_checks
            )
            utilities.append(real_utility)
            
            if request.resultant in available_params:
                trace.append({
                    'step': steps,
                    'action': 'goal_found',
                    'description': f'Goal reached after {steps} greedy steps!',
                    'path': path.copy(),
                    'utility': round(min(utilities), 3),
                    'service_id': best_service.id
                })
                break
        
        # Build result
        if request.resultant in available_params:
            result.services = [self.service_dict[sid] for sid in path]
            result.workflow = path
            result.utility_value = min(utilities) if utilities else 0
            result.success = True
            result.states_explored = steps
            
            total_rt = sum(s.qos.response_time for s in result.services)
            min_rel = min(s.qos.reliability for s in result.services)
            min_avail = min(s.qos.availability for s in result.services)
            
            result.qos_achieved = QoS(
                response_time=total_rt,
                reliability=min_rel,
                availability=min_avail
            )
            
            trace.append({
                'step': steps,
                'action': 'complete',
                'description': f'Greedy complete: {len(path)} service(s) in {steps} steps',
                'final_path': path,
                'total_explored': len(explored_services)
            })
            
            result.explanation = (
                f"Greedy Algorithm: {len(path)} service(s) selected in {steps} steps\n"
                f"Path: {' → '.join(path)}\n"
                f"Utility Score: {result.utility_value:.3f}\n"
                f"Greedy decisions: {steps} | Total candidates seen: {len(explored_services)}"
            )
        else:
            trace.append({
                'step': steps,
                'action': 'failed',
                'description': f'Greedy failed after {steps} steps'
            })
            result.explanation = f"Greedy did not find a composition after {steps} steps"
        
        result.algorithm_trace = trace
        return result
    
    # ================================================================
    # MULTI-ALGORITHM COMPARISON
    # ================================================================
    
    def compose_all_algorithms(self, request):
        """
        Run all three algorithms on the same request and return comparative results.
        Used by the comparison tab.
        """
        results = {}
        
        for algo in ['dijkstra', 'astar', 'greedy']:
            try:
                result = self.compose(request, algo)
                results[algo] = result.to_dict()
            except Exception as e:
                results[algo] = {
                    'success': False,
                    'explanation': f'Error: {str(e)}',
                    'utility_value': 0,
                    'computation_time': 0,
                    'states_explored': 0,
                    'services': [],
                    'workflow': []
                }
        
        return results
