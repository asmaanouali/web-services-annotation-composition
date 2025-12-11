"""
annotation_system/annotation_enricher.py
Enrichissement des annotations basé sur l'historique d'exécution
"""
import sys
import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@dataclass
class ExecutionFeedback:
    """Feedback d'une exécution de service"""
    timestamp: datetime
    service_name: str
    operation_name: str
    success: bool
    execution_time_ms: int
    parameters_used: Dict[str, Any]
    error_message: Optional[str] = None
    retry_count: int = 0
    workflow_id: Optional[str] = None


class AnnotationEnricher:
    """
    Enrichit les annotations LLM avec des données d'exécution réelles
    
    Fonctionnalités :
    - Mise à jour des métriques de qualité (temps de réponse, taux de succès)
    - Apprentissage des meilleurs mappings de paramètres
    - Historique des compositions réussies/échouées
    - Détection des services fiables/problématiques
    """
    
    def __init__(self, annotations_dir: str = "services/wsdl/annotated"):
        """
        Initialise l'enrichisseur
        
        Args:
            annotations_dir: Répertoire contenant les annotations JSON
        """
        self.annotations_dir = annotations_dir
        self.feedback_history: List[ExecutionFeedback] = []
        self.load_feedback_history()
    
    def load_feedback_history(self):
        """Charge l'historique des feedbacks depuis le disque"""
        history_file = os.path.join(self.annotations_dir, "feedback_history.json")
        
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                for item in data:
                    feedback = ExecutionFeedback(
                        timestamp=datetime.fromisoformat(item['timestamp']),
                        service_name=item['service_name'],
                        operation_name=item['operation_name'],
                        success=item['success'],
                        execution_time_ms=item['execution_time_ms'],
                        parameters_used=item['parameters_used'],
                        error_message=item.get('error_message'),
                        retry_count=item.get('retry_count', 0),
                        workflow_id=item.get('workflow_id')
                    )
                    self.feedback_history.append(feedback)
                
                print(f"{len(self.feedback_history)} feedbacks chargés depuis l'historique")
            except Exception as e:
                print(f"Erreur lors du chargement de l'historique: {e}")
    
    def save_feedback_history(self):
        """Sauvegarde l'historique des feedbacks"""
        history_file = os.path.join(self.annotations_dir, "feedback_history.json")
        
        data = [
            {
                'timestamp': fb.timestamp.isoformat(),
                'service_name': fb.service_name,
                'operation_name': fb.operation_name,
                'success': fb.success,
                'execution_time_ms': fb.execution_time_ms,
                'parameters_used': fb.parameters_used,
                'error_message': fb.error_message,
                'retry_count': fb.retry_count,
                'workflow_id': fb.workflow_id
            }
            for fb in self.feedback_history
        ]
        
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Historique sauvegardé: {len(data)} feedbacks")
    
    def record_execution_feedback(self, 
                                  execution_result,
                                  workflow_id: Optional[str] = None):
        """
        Enregistre le feedback d'une exécution
        
        Args:
            execution_result: Résultat d'exécution (ExecutionResult)
            workflow_id: ID du workflow (optionnel)
        """
        feedback = ExecutionFeedback(
            timestamp=datetime.now(),
            service_name=execution_result.service_name,
            operation_name=execution_result.operation_name,
            success=execution_result.success,
            execution_time_ms=execution_result.execution_time_ms,
            parameters_used=execution_result.outputs if execution_result.success else {},
            error_message=execution_result.error_message,
            retry_count=execution_result.retry_count,
            workflow_id=workflow_id
        )
        
        self.feedback_history.append(feedback)
        print(f"Feedback enregistré pour {execution_result.service_name}")
    
    def enrich_annotation(self, service_name: str) -> bool:
        """
        Enrichit l'annotation d'un service avec les données d'exécution
        
        Args:
            service_name: Nom du service à enrichir
            
        Returns:
            True si l'enrichissement a réussi
        """
        print(f"\n{'='*80}")
        print(f"ENRICHISSEMENT DE L'ANNOTATION : {service_name}")
        print(f"{'='*80}")
        
        # Trouver le fichier d'annotation
        annotation_file = self._find_annotation_file(service_name)
        
        if not annotation_file:
            print(f"Annotation introuvable pour {service_name}")
            return False
        
        # Charger l'annotation
        try:
            with open(annotation_file, 'r', encoding='utf-8') as f:
                annotation = json.load(f)
        except Exception as e:
            print(f"Erreur lors du chargement: {e}")
            return False
        
        # Filtrer les feedbacks pour ce service
        service_feedbacks = [
            fb for fb in self.feedback_history 
            if fb.service_name == service_name
        ]
        
        if not service_feedbacks:
            print(f"Aucun feedback disponible pour {service_name}")
            return False
        
        print(f"\n{len(service_feedbacks)} feedbacks trouvés")
        
        # 1. Mettre à jour les métriques de qualité
        self._update_quality_metrics(annotation, service_feedbacks)
        
        # 2. Mettre à jour l'historique des compositions
        self._update_composition_history(annotation, service_feedbacks)
        
        # 3. Analyser les paramètres fréquemment utilisés
        self._analyze_parameter_patterns(annotation, service_feedbacks)
        
        # 4. Mettre à jour la date de modification
        annotation['updated_at'] = datetime.now().isoformat()
        
        # Sauvegarder l'annotation enrichie
        try:
            with open(annotation_file, 'w', encoding='utf-8') as f:
                json.dump(annotation, f, indent=2, ensure_ascii=False)
            
            print(f"\nAnnotation enrichie et sauvegardée")
            return True
            
        except Exception as e:
            print(f"Erreur lors de la sauvegarde: {e}")
            return False
    
    def _find_annotation_file(self, service_name: str) -> Optional[str]:
        """Trouve le fichier d'annotation pour un service"""
        # Chercher un fichier contenant le nom du service
        if not os.path.exists(self.annotations_dir):
            return None
        
        for filename in os.listdir(self.annotations_dir):
            if filename.endswith('_annotated.json'):
                filepath = os.path.join(self.annotations_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data.get('service_name') == service_name:
                            return filepath
                except:
                    continue
        
        return None
    
    def _update_quality_metrics(self, 
                                annotation: Dict, 
                                feedbacks: List[ExecutionFeedback]):
        """Met à jour les métriques de qualité basées sur les feedbacks réels"""
        print(f"\nMise à jour des métriques de qualité...")
        
        # Calculer les métriques réelles
        successful = [fb for fb in feedbacks if fb.success]
        success_rate = len(successful) / len(feedbacks) if feedbacks else 0
        
        # Temps de réponse moyen (uniquement sur les succès)
        if successful:
            avg_response_time = sum(fb.execution_time_ms for fb in successful) / len(successful)
        else:
            avg_response_time = annotation['interaction']['quality_metrics'].get('response_time_ms', 1000)
        
        # Nombre total de retries
        total_retries = sum(fb.retry_count for fb in feedbacks)
        
        # Mettre à jour l'annotation
        old_metrics = annotation['interaction']['quality_metrics'].copy()
        
        annotation['interaction']['quality_metrics']['success_rate'] = round(success_rate, 4)
        annotation['interaction']['quality_metrics']['response_time_ms'] = int(avg_response_time)
        
        # Ajouter des métriques supplémentaires
        if 'total_executions' not in annotation['interaction']['quality_metrics']:
            annotation['interaction']['quality_metrics']['total_executions'] = 0
        annotation['interaction']['quality_metrics']['total_executions'] += len(feedbacks)
        
        if 'total_retries' not in annotation['interaction']['quality_metrics']:
            annotation['interaction']['quality_metrics']['total_retries'] = 0
        annotation['interaction']['quality_metrics']['total_retries'] += total_retries
        
        # Afficher les changements
        print(f"   • Taux de succès: {old_metrics.get('success_rate', 0):.2%} → {success_rate:.2%}")
        print(f"   • Temps de réponse: {old_metrics.get('response_time_ms', 0)}ms → {int(avg_response_time)}ms")
        print(f"   • Exécutions totales: {annotation['interaction']['quality_metrics']['total_executions']}")
    
    def _update_composition_history(self, 
                                    annotation: Dict, 
                                    feedbacks: List[ExecutionFeedback]):
        """Met à jour l'historique des compositions réussies/échouées"""
        print(f"\nMise à jour de l'historique des compositions...")
        
        successful_workflows = set()
        failed_workflows = set()
        
        for fb in feedbacks:
            if fb.workflow_id:
                if fb.success:
                    successful_workflows.add(fb.workflow_id)
                else:
                    failed_workflows.add(fb.workflow_id)
        
        # Mettre à jour les listes
        if successful_workflows:
            existing = set(annotation['interaction'].get('successful_compositions', []))
            existing.update(successful_workflows)
            annotation['interaction']['successful_compositions'] = list(existing)
        
        if failed_workflows:
            existing = set(annotation['interaction'].get('failed_compositions', []))
            existing.update(failed_workflows)
            annotation['interaction']['failed_compositions'] = list(existing)
        
        print(f"   • Compositions réussies: {len(annotation['interaction'].get('successful_compositions', []))}")
        print(f"   • Compositions échouées: {len(annotation['interaction'].get('failed_compositions', []))}")
    
    def _analyze_parameter_patterns(self, 
                                    annotation: Dict, 
                                    feedbacks: List[ExecutionFeedback]):
        """Analyse les patterns d'utilisation des paramètres"""
        print(f"\nAnalyse des patterns de paramètres...")
        
        # Compter la fréquence d'utilisation de chaque paramètre
        param_frequency: Dict[str, int] = {}
        param_values: Dict[str, List[Any]] = {}
        
        for fb in feedbacks:
            if fb.success and fb.parameters_used:
                for param, value in fb.parameters_used.items():
                    if not param.startswith('_'):  # Ignorer les paramètres internes
                        param_frequency[param] = param_frequency.get(param, 0) + 1
                        
                        if param not in param_values:
                            param_values[param] = []
                        param_values[param].append(value)
        
        # Identifier les paramètres les plus utilisés
        if param_frequency:
            most_used = sorted(param_frequency.items(), key=lambda x: x[1], reverse=True)[:5]
            
            print(f"   • Paramètres les plus utilisés:")
            for param, count in most_used:
                freq = count / len(feedbacks) * 100
                print(f"      - {param}: {count} fois ({freq:.1f}%)")
            
            # Ajouter à l'annotation
            if 'parameter_usage_stats' not in annotation['interaction']:
                annotation['interaction']['parameter_usage_stats'] = {}
            
            for param, count in param_frequency.items():
                annotation['interaction']['parameter_usage_stats'][param] = count
    
    def enrich_all_annotations(self):
        """Enrichit toutes les annotations avec les feedbacks disponibles"""
        print("\n" + "="*80)
        print("ENRICHISSEMENT DE TOUTES LES ANNOTATIONS")
        print("="*80)
        
        # Trouver tous les services avec feedback
        services_with_feedback = set(fb.service_name for fb in self.feedback_history)
        
        print(f"\n{len(services_with_feedback)} services avec feedback:")
        for service in sorted(services_with_feedback):
            print(f"   • {service}")
        
        # Enrichir chaque service
        enriched_count = 0
        for service_name in services_with_feedback:
            if self.enrich_annotation(service_name):
                enriched_count += 1
        
        print(f"\n{'='*80}")
        print(f"RÉSUMÉ: {enriched_count}/{len(services_with_feedback)} annotations enrichies")
        print(f"{'='*80}")
    
    def get_service_statistics(self, service_name: str) -> Dict[str, Any]:
        """Récupère les statistiques d'un service depuis les feedbacks"""
        service_feedbacks = [
            fb for fb in self.feedback_history 
            if fb.service_name == service_name
        ]
        
        if not service_feedbacks:
            return {
                'total_executions': 0,
                'success_rate': 0.0,
                'avg_response_time_ms': 0,
                'total_retries': 0
            }
        
        successful = [fb for fb in service_feedbacks if fb.success]
        
        return {
            'total_executions': len(service_feedbacks),
            'success_rate': len(successful) / len(service_feedbacks),
            'avg_response_time_ms': sum(fb.execution_time_ms for fb in successful) / len(successful) if successful else 0,
            'total_retries': sum(fb.retry_count for fb in service_feedbacks),
            'last_execution': max(fb.timestamp for fb in service_feedbacks).isoformat()
        }
    
    def generate_enrichment_report(self, output_file: str = None):
        """Génère un rapport d'enrichissement"""
        if output_file is None:
            output_file = os.path.join(
                self.annotations_dir, 
                f"enrichment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
        
        # Calculer les statistiques par service
        services = set(fb.service_name for fb in self.feedback_history)
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'total_feedbacks': len(self.feedback_history),
            'services_count': len(services),
            'services': {}
        }
        
        for service in services:
            report['services'][service] = self.get_service_statistics(service)
        
        # Sauvegarder
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\nRapport d'enrichissement généré: {output_file}")
        return report


# Test de l'enrichisseur
if __name__ == "__main__":
    print("TEST DE L'ENRICHISSEUR D'ANNOTATIONS\n")
    
    # Créer un enrichisseur
    enricher = AnnotationEnricher()
    
    # Simuler des feedbacks
    print("Simulation de feedbacks d'exécution...")
    
    from dataclasses import dataclass
    from typing import Dict, Any, Optional
    
    @dataclass
    class MockExecutionResult:
        success: bool
        service_name: str
        operation_name: str
        outputs: Dict[str, Any]
        execution_time_ms: int
        error_message: Optional[str] = None
        retry_count: int = 0
        used_fallback: bool = False
    
    # Simuler 10 exécutions pour SkyscannerFlightService
    for i in range(10):
        result = MockExecutionResult(
            success=i < 8,  # 80% de succès
            service_name="SkyscannerFlightService",
            operation_name="FindFlights",
            outputs={"price": 450.00 + i*10} if i < 8 else {},
            execution_time_ms=1000 + i*100,
            error_message="Service indisponible" if i >= 8 else None,
            retry_count=0 if i < 8 else 2
        )
        enricher.record_execution_feedback(result, workflow_id=f"wf_{i}")
    
    # Simuler 10 exécutions pour StripePaymentService
    for i in range(10):
        result = MockExecutionResult(
            success=i < 9,  # 90% de succès
            service_name="StripePaymentService",
            operation_name="ProcessPayment",
            outputs={"transactionId": f"TXN_{i}"} if i < 9 else {},
            execution_time_ms=500 + i*50,
            retry_count=0 if i < 9 else 1
        )
        enricher.record_execution_feedback(result, workflow_id=f"wf_{i}")
    
    print(f"\n{len(enricher.feedback_history)} feedbacks enregistrés")
    
    # Sauvegarder l'historique
    enricher.save_feedback_history()
    
    # Enrichir toutes les annotations
    enricher.enrich_all_annotations()
    
    # Générer un rapport
    report = enricher.generate_enrichment_report()
    
    print("\nStatistiques des services:")
    for service, stats in report['services'].items():
        print(f"\n   {service}:")
        print(f"      • Exécutions: {stats['total_executions']}")
        print(f"      • Taux de succès: {stats['success_rate']:.1%}")
        print(f"      • Temps moyen: {stats['avg_response_time_ms']:.0f}ms")
    
    print("\nTest terminé!")