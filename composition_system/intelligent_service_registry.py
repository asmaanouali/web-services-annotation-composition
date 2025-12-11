"""
composition_system/intelligent_service_registry.py
Registre intelligent utilisant les annotations LLM pour découverte et sélection
"""
import json
import os
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@dataclass
class ServiceScore:
    """Score détaillé d'un service pour une requête donnée"""
    service_name: str
    total_score: float
    functional_score: float
    quality_score: float
    cost_score: float
    context_score: float
    details: Dict[str, Any]
    reasons: List[str]


class IntelligentServiceRegistry:
    """
    Registre intelligent qui utilise les annotations LLM
    pour découvrir et sélectionner les meilleurs services
    """
    
    def __init__(self, annotations_dir: str = "services/wsdl/annotated"):
        """
        Initialise le registre intelligent
        
        Args:
            annotations_dir: Répertoire contenant les annotations JSON
        """
        self.annotations_dir = annotations_dir
        self.services: Dict[str, Dict] = {}
        self.load_annotations()
    
    def load_annotations(self) -> None:
        """Charge toutes les annotations générées par le LLM"""
        print(f"Chargement des annotations depuis {self.annotations_dir}...")
        
        if not os.path.exists(self.annotations_dir):
            print(f"Répertoire non trouvé: {self.annotations_dir}")
            return
        
        annotation_files = [f for f in os.listdir(self.annotations_dir) 
                          if f.endswith('_annotated.json')]
        
        for filename in annotation_files:
            filepath = os.path.join(self.annotations_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    annotation_data = json.load(f)
                    service_name = annotation_data['service_name']
                    self.services[service_name] = annotation_data
                    
                    category = annotation_data['functional']['service_category']
                    print(f"   {service_name} (catégorie: {category})")
            except Exception as e:
                print(f"   Erreur lors du chargement de {filename}: {e}")
        
        print(f"\n{len(self.services)} services chargés avec annotations LLM\n")
    
    def discover_by_category(self, category: str) -> List[str]:
        """
        Découvre les services par catégorie (depuis annotations)
        
        Args:
            category: Catégorie recherchée (search, booking, payment, etc.)
            
        Returns:
            Liste des noms de services correspondants
        """
        results = []
        for service_name, annotation in self.services.items():
            service_category = annotation['functional']['service_category']
            if service_category == category:
                results.append(service_name)
        return results
    
    def discover_by_capability(self, capability: str) -> List[str]:
        """
        Découvre les services par capacité (depuis annotations)
        
        Args:
            capability: Capacité recherchée (ex: "search_flights")
            
        Returns:
            Liste des noms de services correspondants
        """
        results = []
        capability_lower = capability.lower()
        
        for service_name, annotation in self.services.items():
            capabilities = annotation['functional']['capabilities']
            for cap in capabilities:
                if capability_lower in cap.lower():
                    results.append(service_name)
                    break
        
        return results
    
    def select_best_service(self, 
                           category: str,
                           user_context: Dict[str, Any],
                           constraints: Optional[Dict[str, Any]] = None) -> Optional[ServiceScore]:
        """
        Sélectionne le MEILLEUR service basé sur les annotations LLM
        et le contexte utilisateur
        
        Args:
            category: Catégorie de service recherchée
            user_context: Contexte utilisateur (location, budget, preferences, etc.)
            constraints: Contraintes (max_cost, min_quality, etc.)
            
        Returns:
            ServiceScore du meilleur service ou None
        """
        print(f"\nSélection intelligente pour catégorie: {category}")
        
        # 1. Découvrir les candidats
        candidates = self.discover_by_category(category)
        
        if not candidates:
            print(f"   Aucun service trouvé pour '{category}'")
            return None
        
        print(f"   Candidats: {', '.join(candidates)}")
        
        constraints = constraints or {}
        max_cost = constraints.get('max_cost', float('inf'))
        min_quality = constraints.get('min_quality', 0.0)
        
        scores = []
        
        # 2. Calculer le score de chaque candidat
        for service_name in candidates:
            annotation = self.services[service_name]
            
            # Calculer les 4 dimensions de score
            func_score = self._calculate_functional_score(annotation, user_context)
            quality_score = self._calculate_quality_score(annotation)
            cost_score = self._calculate_cost_score(annotation, max_cost)
            context_score = self._calculate_context_score(annotation, user_context)
            
            # Score total pondéré (adaptatif selon le contexte)
            weights = self._determine_weights(user_context)
            total_score = (
                func_score * weights['functional'] +
                quality_score * weights['quality'] +
                cost_score * weights['cost'] +
                context_score * weights['context']
            )
            
            # Vérifier les contraintes
            service_cost = annotation['policy']['usage_policy']['cost_per_request']
            service_quality = annotation['interaction']['quality_metrics']['success_rate']
            
            if service_cost <= max_cost and service_quality >= min_quality:
                reasons = self._generate_selection_reasons(
                    annotation, func_score, quality_score, cost_score, context_score
                )
                
                scores.append(ServiceScore(
                    service_name=service_name,
                    total_score=total_score,
                    functional_score=func_score,
                    quality_score=quality_score,
                    cost_score=cost_score,
                    context_score=context_score,
                    details={
                        'cost': service_cost,
                        'quality': service_quality,
                        'weights': weights
                    },
                    reasons=reasons
                ))
        
        if not scores:
            print(f"   Aucun service ne satisfait les contraintes")
            return None
        
        # 3. Retourner le meilleur
        best = max(scores, key=lambda s: s.total_score)
        
        print(f"   Service sélectionné: {best.service_name}")
        print(f"   Score total: {best.total_score:.3f}")
        print(f"      • Fonctionnel: {best.functional_score:.3f}")
        print(f"      • Qualité: {best.quality_score:.3f}")
        print(f"      • Coût: {best.cost_score:.3f}")
        print(f"      • Contexte: {best.context_score:.3f}")
        
        return best
    
    def _determine_weights(self, user_context: Dict[str, Any]) -> Dict[str, float]:
        """
        Détermine les poids adaptatifs selon le contexte utilisateur
        """
        # Par défaut : équilibré
        weights = {
            'functional': 0.25,
            'quality': 0.25,
            'cost': 0.25,
            'context': 0.25
        }
        
        # Si budget serré → privilégier le coût
        if user_context.get('budget_conscious', False):
            weights['cost'] = 0.4
            weights['functional'] = 0.2
            weights['quality'] = 0.2
            weights['context'] = 0.2
        
        # Si mission critique → privilégier la qualité
        if user_context.get('mission_critical', False):
            weights['quality'] = 0.4
            weights['functional'] = 0.3
            weights['cost'] = 0.1
            weights['context'] = 0.2
        
        # Si besoins spécifiques → privilégier les capacités
        if user_context.get('specific_features_needed', False):
            weights['functional'] = 0.4
            weights['quality'] = 0.2
            weights['cost'] = 0.2
            weights['context'] = 0.2
        
        return weights
    
    def _calculate_functional_score(self, annotation: Dict, context: Dict) -> float:
        """Calcule le score fonctionnel depuis les annotations"""
        score = 0.5  # Base
        
        # Capacités du service
        capabilities = annotation['functional'].get('capabilities', [])
        score += min(len(capabilities) * 0.05, 0.2)  # Bonus pour nombre de capacités
        
        # Features spéciales
        special_features = annotation['functional'].get('special_features', {})
        
        # Correspondance avec besoins utilisateur
        if context.get('needs_multi_currency') and special_features.get('supports_multi_currency'):
            score += 0.15
        
        if context.get('needs_loyalty_points') and special_features.get('loyalty_points'):
            score += 0.1
        
        if context.get('needs_buyer_protection') and special_features.get('buyer_protection'):
            score += 0.1
        
        # Keywords matching
        keywords = annotation['functional'].get('keywords', [])
        user_keywords = context.get('keywords', [])
        if user_keywords:
            keyword_match = len(set(keywords) & set(user_keywords)) / len(user_keywords)
            score += keyword_match * 0.15
        
        return min(score, 1.0)
    
    def _calculate_quality_score(self, annotation: Dict) -> float:
        """Calcule le score de qualité depuis les annotations"""
        metrics = annotation['interaction']['quality_metrics']
        
        success_rate = metrics.get('success_rate', 0.95)
        response_time = metrics.get('response_time_ms', 1000)
        
        # Score success rate (0-0.5)
        success_score = success_rate * 0.5
        
        # Score response time (0-0.5)
        if response_time < 500:
            time_score = 0.5
        elif response_time < 1000:
            time_score = 0.4
        elif response_time < 2000:
            time_score = 0.3
        elif response_time < 3000:
            time_score = 0.2
        else:
            time_score = 0.1
        
        return success_score + time_score
    
    def _calculate_cost_score(self, annotation: Dict, max_cost: float) -> float:
        """Calcule le score de coût (inversé - moins cher = mieux)"""
        cost = annotation['policy']['usage_policy']['cost_per_request']
        
        if cost == 0:
            return 1.0
        
        if max_cost == float('inf'):
            # Normaliser sur une échelle raisonnable
            return max(0, 1.0 - (cost / 0.1))
        
        # Score inversé
        return max(0, 1.0 - (cost / max_cost))
    
    def _calculate_context_score(self, annotation: Dict, context: Dict) -> float:
        """Calcule le score contextuel depuis les annotations"""
        score = 0.3  # Base
        
        # Couverture géographique
        user_location = context.get('location', 'GLOBAL')
        coverage = annotation['context'].get('geographic_coverage', ['GLOBAL'])
        
        if user_location in coverage or 'GLOBAL' in coverage:
            score += 0.3
        
        # Disponibilité temporelle
        temporal = annotation['context'].get('temporal_constraints', [])
        if '24/7_available' in temporal:
            score += 0.2
        elif context.get('needs_24_7', False):
            score += 0.0  # Pénalité si besoin mais pas disponible
        else:
            score += 0.1
        
        # Location-aware
        if context.get('needs_location_aware', False):
            if annotation['context'].get('location_aware', False):
                score += 0.2
        
        return min(score, 1.0)
    
    def _generate_selection_reasons(self, annotation: Dict, 
                                    func_score: float, quality_score: float,
                                    cost_score: float, context_score: float) -> List[str]:
        """Génère les raisons de sélection basées sur les annotations"""
        reasons = []
        
        if func_score > 0.7:
            capabilities = annotation['functional'].get('capabilities', [])
            reasons.append(f"Excellentes capacités fonctionnelles ({len(capabilities)} capacités)")
        
        if quality_score > 0.8:
            success_rate = annotation['interaction']['quality_metrics']['success_rate']
            reasons.append(f"Haute qualité de service (taux de succès: {success_rate*100:.0f}%)")
        
        cost = annotation['policy']['usage_policy']['cost_per_request']
        if cost == 0:
            reasons.append("Service gratuit")
        elif cost_score > 0.8:
            reasons.append(f"Coût très compétitif (${cost:.4f} par appel)")
        
        if context_score > 0.8:
            coverage = annotation['context'].get('geographic_coverage', [])
            reasons.append(f"Parfaitement adapté au contexte (couverture: {', '.join(coverage)})")
        
        # Features spéciales
        features = annotation['functional'].get('special_features', {})
        if features.get('buyer_protection'):
            reasons.append("Protection acheteur incluse")
        if features.get('loyalty_points'):
            reasons.append("Programme de fidélité disponible")
        if features.get('supports_multi_currency'):
            reasons.append("Support multi-devises")
        
        # Compliance
        compliance = annotation['policy'].get('compliance_standards', [])
        if 'GDPR' in compliance:
            reasons.append("Conforme RGPD")
        if 'PCI-DSS' in compliance:
            reasons.append("Certifié PCI-DSS (sécurité paiement)")
        
        return reasons[:5]  # Max 5 raisons
    
    def get_service_annotation(self, service_name: str) -> Optional[Dict]:
        """Récupère l'annotation complète d'un service"""
        return self.services.get(service_name)
    
    def list_all_services(self) -> List[str]:
        """Liste tous les services disponibles"""
        return list(self.services.keys())
    
    def compare_services(self, service_names: List[str], 
                        user_context: Dict[str, Any]) -> List[ServiceScore]:
        """Compare plusieurs services et retourne leurs scores"""
        scores = []
        
        for service_name in service_names:
            if service_name not in self.services:
                continue
            
            annotation = self.services[service_name]
            
            func_score = self._calculate_functional_score(annotation, user_context)
            quality_score = self._calculate_quality_score(annotation)
            cost_score = self._calculate_cost_score(annotation, float('inf'))
            context_score = self._calculate_context_score(annotation, user_context)
            
            weights = self._determine_weights(user_context)
            total_score = (
                func_score * weights['functional'] +
                quality_score * weights['quality'] +
                cost_score * weights['cost'] +
                context_score * weights['context']
            )
            
            reasons = self._generate_selection_reasons(
                annotation, func_score, quality_score, cost_score, context_score
            )
            
            scores.append(ServiceScore(
                service_name=service_name,
                total_score=total_score,
                functional_score=func_score,
                quality_score=quality_score,
                cost_score=cost_score,
                context_score=context_score,
                details={'weights': weights},
                reasons=reasons
            ))
        
        return sorted(scores, key=lambda s: s.total_score, reverse=True)


# Test
if __name__ == "__main__":
    print("Test du Intelligent Service Registry\n")
    
    # Créer le registre
    registry = IntelligentServiceRegistry()
    
    if not registry.services:
        print("Aucune annotation chargée")
        print("   Exécutez d'abord: python annotation_system/batch_annotate.py")
        exit(1)
    
    # Test 1: Sélection intelligente
    print("="*80)
    print("TEST 1: Sélection Intelligente avec Contexte")
    print("="*80)
    
    # Contexte: Voyage d'affaires, budget limité
    context = {
        "location": "EU",
        "budget_conscious": True,
        "needs_multi_currency": True,
        "needs_24_7": False
    }
    
    constraints = {
        "max_cost": 0.05,
        "min_quality": 0.90
    }
    
    best = registry.select_best_service("search", context, constraints)
    
    if best:
        print(f"\nRaisons de sélection:")
        for reason in best.reasons:
            print(f"   • {reason}")