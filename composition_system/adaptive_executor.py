"""
composition_system/adaptive_executor.py
Exécuteur adaptatif avec self-configuration, self-adaptation et self-protection
"""
import sys
import os
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@dataclass
class ExecutionResult:
    """Résultat d'une exécution de service"""
    success: bool
    service_name: str
    operation_name: str
    outputs: Dict[str, Any]
    execution_time_ms: int
    error_message: Optional[str] = None
    retry_count: int = 0
    used_fallback: bool = False


@dataclass
class AdaptationEvent:
    """Événement d'adaptation enregistré"""
    timestamp: datetime
    step_number: int
    original_service: str
    adapted_to: Optional[str]
    reason: str
    success: bool


class AdaptiveExecutor:
    """
    Exécuteur adaptatif qui implémente :
    - Self-configuration : ajustement automatique des paramètres
    - Self-adaptation : changement de service en cas d'échec
    - Self-protection : retry, timeout, fallback
    """
    
    def __init__(self, max_retries: int = 3, timeout_seconds: int = 30):
        """
        Initialise l'exécuteur adaptatif
        
        Args:
            max_retries: Nombre maximum de tentatives
            timeout_seconds: Timeout par défaut pour chaque appel
        """
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.adaptation_history: List[AdaptationEvent] = []
        
    def execute_workflow_with_adaptation(self, 
                                        workflow_result,
                                        context: Dict[str, Any],
                                        registry) -> Dict[str, Any]:
        """
        Exécute un workflow avec adaptation automatique
        
        Args:
            workflow_result: Résultat de composition (classique ou intelligent)
            context: Contexte d'exécution initial
            registry: Registre des services (pour trouver alternatives)
            
        Returns:
            Dictionnaire avec résultats d'exécution et historique d'adaptation
        """
        print("\n" + "="*80)
        print("EXÉCUTION ADAPTATIVE DU WORKFLOW")
        print("="*80)
        
        execution_results = []
        current_context = context.copy()
        
        for step in workflow_result.steps:
            print(f"\n{'─'*80}")
            print(f"ÉTAPE {step.step_number}: {step.category.upper()}")
            print(f"{'─'*80}")
            print(f"Service sélectionné: {step.selected_service}")
            print(f"Opération: {step.selected_operation}")
            
            # Exécuter l'étape avec adaptation
            result = self._execute_step_with_adaptation(
                step, 
                current_context, 
                registry
            )
            
            execution_results.append(result)
            
            # Enrichir le contexte avec les sorties
            if result.success:
                current_context.update(result.outputs)
                print(f"\nÉtape {step.step_number} réussie en {result.execution_time_ms}ms")
            else:
                print(f"\nÉtape {step.step_number} échouée: {result.error_message}")
                # En production, on pourrait arrêter ou continuer selon la criticité
        
        # Résumé de l'exécution
        self._print_execution_summary(execution_results)
        
        return {
            "execution_results": execution_results,
            "adaptation_history": self.adaptation_history,
            "final_context": current_context,
            "workflow_success": all(r.success for r in execution_results)
        }
    
    def _execute_step_with_adaptation(self, 
                                     step, 
                                     context: Dict[str, Any],
                                     registry) -> ExecutionResult:
        """
        Exécute une étape avec self-adaptation et self-protection
        
        Stratégie :
        1. Self-configuration : ajuster les paramètres automatiquement
        2. Essayer le service principal avec retry
        3. Self-adaptation : essayer les alternatives si échec
        4. Self-protection : fallback graceful
        """
        
        # 1. SELF-CONFIGURATION : Ajuster les paramètres
        print(f"\nSelf-configuration des paramètres...")
        configured_params = self._self_configure_parameters(
            step.input_parameters, 
            context
        )
        print(f"   Paramètres configurés: {len(configured_params)} sur {len(step.input_parameters) + len(step.missing_parameters)}")
        
        # 2. Essayer le service principal avec RETRY (self-protection)
        print(f"\nTentative d'exécution du service principal...")
        result = self._execute_with_retry(
            step.selected_service,
            step.selected_operation,
            configured_params
        )
        
        if result.success:
            self._record_adaptation(
                step.step_number,
                step.selected_service,
                None,
                "Service principal réussi",
                True
            )
            return result
        
        # 3. SELF-ADAPTATION : Essayer les alternatives
        print(f"\nÉchec du service principal: {result.error_message}")
        print(f"Self-adaptation : recherche d'alternatives...")
        
        alternatives = self._find_alternatives(step, registry)
        
        if alternatives:
            print(f"   Alternatives trouvées: {len(alternatives)}")
            
            for i, alt_service in enumerate(alternatives, 1):
                print(f"\n   Tentative {i}/{len(alternatives)}: {alt_service}")
                
                alt_result = self._execute_with_retry(
                    alt_service,
                    step.selected_operation,
                    configured_params
                )
                
                if alt_result.success:
                    print(f"   Alternative {alt_service} a réussi!")
                    self._record_adaptation(
                        step.step_number,
                        step.selected_service,
                        alt_service,
                        f"Basculement vers alternative après échec du service principal",
                        True
                    )
                    return alt_result
                else:
                    print(f"   Alternative {alt_service} a échoué")
        
        # 4. SELF-PROTECTION : Fallback graceful
        print(f"\nSelf-protection : stratégie de fallback...")
        fallback_result = self._fallback_strategy(
            step.step_number,
            step.selected_service,
            step.selected_operation,
            configured_params
        )
        
        self._record_adaptation(
            step.step_number,
            step.selected_service,
            None,
            "Fallback activé après échec de toutes les alternatives",
            False
        )
        
        return fallback_result
    
    def _self_configure_parameters(self, 
                                   provided_params: Dict[str, Any],
                                   context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Self-configuration : ajuste automatiquement les paramètres
        
        Stratégies :
        - Compléter avec des valeurs par défaut raisonnables
        - Enrichir depuis le contexte
        - Convertir les types si nécessaire
        """
        configured = provided_params.copy()
        
        # Valeurs par défaut raisonnables
        defaults = {
            "cabinClass": "economy",
            "directFlightsOnly": False,
            "children": 0,
            "infants": 0,
            "rooms": 1,
            "minStars": 3,
            "amenities": "wifi,parking"
        }
        
        for param, default_value in defaults.items():
            if param not in configured:
                configured[param] = default_value
                print(f"   ✓ {param} = {default_value} (valeur par défaut)")
        
        # Enrichir depuis le contexte
        for key, value in context.items():
            if key not in configured and not key.startswith("<"):
                configured[key] = value
                print(f"   ✓ {key} = {value} (depuis contexte)")
        
        return configured
    
    def _execute_with_retry(self,
                           service_name: str,
                           operation_name: str,
                           parameters: Dict[str, Any]) -> ExecutionResult:
        """
        Exécute un service avec retry automatique (self-protection)
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    print(f"   Retry {attempt}/{self.max_retries-1}...")
                    time.sleep(0.5 * attempt)  # Backoff exponentiel
                
                # SIMULATION : Appel du service réel
                # Dans une vraie implémentation, on ferait un appel SOAP/REST
                start_time = time.time()
                
                # Simuler un succès avec 80% de probabilité
                import random
                if random.random() < 0.8:
                    execution_time = int((time.time() - start_time) * 1000)
                    
                    # Simuler des sorties
                    outputs = self._simulate_service_outputs(service_name, operation_name)
                    
                    return ExecutionResult(
                        success=True,
                        service_name=service_name,
                        operation_name=operation_name,
                        outputs=outputs,
                        execution_time_ms=execution_time,
                        retry_count=attempt
                    )
                else:
                    raise Exception(f"Service {service_name} temporairement indisponible")
                    
            except Exception as e:
                last_error = str(e)
                print(f"   Tentative {attempt+1} échouée: {last_error}")
        
        # Toutes les tentatives ont échoué
        return ExecutionResult(
            success=False,
            service_name=service_name,
            operation_name=operation_name,
            outputs={},
            execution_time_ms=0,
            error_message=last_error,
            retry_count=self.max_retries
        )
    
    def _simulate_service_outputs(self, 
                                  service_name: str, 
                                  operation_name: str) -> Dict[str, Any]:
        """Simule les sorties d'un service (pour la démo)"""
        
        if "Flight" in service_name:
            return {
                "flightId": f"FL_{int(time.time())}",
                "price": 450.00,
                "currency": "EUR",
                "departureTime": "2025-08-10T10:00:00",
                "arrivalTime": "2025-08-10T18:00:00"
            }
        elif "Hotel" in service_name:
            return {
                "hotelId": f"HT_{int(time.time())}",
                "hotelName": "Tokyo Grand Hotel",
                "pricePerNight": 120.00,
                "totalPrice": 840.00,
                "currency": "EUR"
            }
        elif "Payment" in service_name:
            return {
                "transactionId": f"TXN_{int(time.time())}",
                "status": "completed",
                "amount": 1290.00,
                "currency": "EUR"
            }
        else:
            return {"result": "success"}
    
    def _find_alternatives(self, step, registry) -> List[str]:
        """Trouve les services alternatifs pour une étape"""
        
        # Si le workflow contient déjà des alternatives
        if hasattr(step, 'alternatives_rejected') and step.alternatives_rejected:
            return step.alternatives_rejected
        
        # Sinon, chercher dans le registre
        if hasattr(registry, 'find_by_category'):
            candidates = registry.find_by_category(step.category)
            alternatives = [s.name for s in candidates if s.name != step.selected_service]
            return alternatives
        
        return []
    
    def _fallback_strategy(self,
                          step_number: int,
                          service_name: str,
                          operation_name: str,
                          parameters: Dict[str, Any]) -> ExecutionResult:
        """
        Stratégie de fallback graceful (self-protection)
        
        Options :
        - Retourner des données mock/cached
        - Retourner un résultat partiel
        - Marquer comme échec mais continuer le workflow
        """
        print(f"   Activation du mode fallback...")
        print(f"   → Retour de données simulées pour permettre la continuation")
        
        # Retourner des données simulées pour ne pas bloquer le workflow
        fallback_outputs = self._simulate_service_outputs(service_name, operation_name)
        fallback_outputs["_fallback"] = True  # Marquer comme fallback
        
        return ExecutionResult(
            success=True,  # On marque comme succès pour permettre la continuation
            service_name=service_name,
            operation_name=operation_name,
            outputs=fallback_outputs,
            execution_time_ms=0,
            error_message="Fallback activé",
            used_fallback=True
        )
    
    def _record_adaptation(self,
                          step_number: int,
                          original_service: str,
                          adapted_to: Optional[str],
                          reason: str,
                          success: bool):
        """Enregistre un événement d'adaptation"""
        event = AdaptationEvent(
            timestamp=datetime.now(),
            step_number=step_number,
            original_service=original_service,
            adapted_to=adapted_to,
            reason=reason,
            success=success
        )
        self.adaptation_history.append(event)
    
    def _print_execution_summary(self, results: List[ExecutionResult]):
        """Affiche un résumé de l'exécution"""
        print("\n" + "="*80)
        print("RÉSUMÉ DE L'EXÉCUTION ADAPTATIVE")
        print("="*80)
        
        total_time = sum(r.execution_time_ms for r in results)
        successful = sum(1 for r in results if r.success)
        total_retries = sum(r.retry_count for r in results)
        fallbacks_used = sum(1 for r in results if r.used_fallback)
        
        print(f"\nStatistiques:")
        print(f"   • Étapes réussies: {successful}/{len(results)}")
        print(f"   • Temps total: {total_time}ms")
        print(f"   • Tentatives de retry: {total_retries}")
        print(f"   • Fallbacks utilisés: {fallbacks_used}")
        
        if self.adaptation_history:
            print(f"\nAdaptations effectuées: {len(self.adaptation_history)}")
            for event in self.adaptation_history:
                status = "✅" if event.success else "⚠️"
                print(f"   {status} Étape {event.step_number}: {event.reason}")
                if event.adapted_to:
                    print(f"      {event.original_service} → {event.adapted_to}")
    
    def save_execution_report(self, 
                             execution_data: Dict[str, Any],
                             output_dir: str = "composition_system/results"):
        """Sauvegarde le rapport d'exécution"""
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"execution_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        # Convertir en format sérialisable
        report = {
            "timestamp": datetime.now().isoformat(),
            "workflow_success": execution_data["workflow_success"],
            "execution_results": [
                {
                    "success": r.success,
                    "service_name": r.service_name,
                    "operation_name": r.operation_name,
                    "execution_time_ms": r.execution_time_ms,
                    "retry_count": r.retry_count,
                    "used_fallback": r.used_fallback,
                    "error_message": r.error_message
                }
                for r in execution_data["execution_results"]
            ],
            "adaptation_history": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "step_number": e.step_number,
                    "original_service": e.original_service,
                    "adapted_to": e.adapted_to,
                    "reason": e.reason,
                    "success": e.success
                }
                for e in execution_data["adaptation_history"]
            ]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\nRapport d'exécution sauvegardé: {filepath}")


# Test de l'exécuteur adaptatif
if __name__ == "__main__":
    print("TEST DE L'EXÉCUTEUR ADAPTATIF\n")
    
    # Simuler un workflow simple
    from dataclasses import dataclass
    
    @dataclass
    class MockStep:
        step_number: int
        category: str
        selected_service: str
        selected_operation: str
        input_parameters: Dict
        missing_parameters: List
        alternatives_rejected: List
    
    @dataclass
    class MockWorkflow:
        steps: List
    
    # Créer un workflow de test
    workflow = MockWorkflow(steps=[
        MockStep(
            step_number=1,
            category="flight",
            selected_service="AmadeusFlightService",
            selected_operation="SearchFlights",
            input_parameters={"origin": "Paris", "destination": "Tokyo"},
            missing_parameters=["cabinClass", "directFlightsOnly"],
            alternatives_rejected=["SkyscannerFlightService"]
        )
    ])
    
    context = {
        "origin": "Paris",
        "destination": "Tokyo",
        "departureDate": "2025-08-10",
        "passengers": 1
    }
    
    # Exécuter avec adaptation
    executor = AdaptiveExecutor(max_retries=2)
    result = executor.execute_workflow_with_adaptation(workflow, context, None)
    
    # Sauvegarder le rapport
    executor.save_execution_report(result)
    
    print("\nTest terminé")