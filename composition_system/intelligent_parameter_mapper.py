"""
composition_system/intelligent_parameter_mapper.py
Mapper intelligent de paramètres utilisant les annotations LLM
et l'analyse sémantique
"""
from typing import Dict, List, Optional, Any, Tuple
import re
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class IntelligentParameterMapper:
    """
    Mapper intelligent qui utilise:
    - Les annotations LLM pour comprendre la sémantique
    - Les mappings d'interaction entre services
    - L'analyse de similarité avancée
    """
    
    # Mappings sémantiques enrichis (plus que la version classique)
    SEMANTIC_GROUPS = {
        'location_origin': {
            'keywords': ['origin', 'from', 'departure', 'departureairport', 'source', 'start'],
            'type': 'location',
            'description': 'Point de départ du voyage'
        },
        'location_destination': {
            'keywords': ['destination', 'to', 'arrival', 'arrivalairport', 'target', 'end', 'city'],
            'type': 'location',
            'description': 'Point d\'arrivée du voyage'
        },
        'date_start': {
            'keywords': ['departuredate', 'outbounddate', 'checkindate', 'arrivaldate', 'startdate', 'from'],
            'type': 'date',
            'description': 'Date de début'
        },
        'date_end': {
            'keywords': ['returndate', 'inbounddate', 'checkoutdate', 'departuredate', 'enddate', 'to'],
            'type': 'date',
            'description': 'Date de fin'
        },
        'number_people': {
            'keywords': ['passengers', 'adults', 'guests', 'numberofguests', 'travelers', 'people'],
            'type': 'integer',
            'description': 'Nombre de personnes'
        },
        'price_value': {
            'keywords': ['price', 'totalprice', 'amount', 'cost', 'totalamount', 'total_cost', 'pricepernight'],
            'type': 'decimal',
            'description': 'Montant monétaire'
        },
        'currency': {
            'keywords': ['currency', 'currencycode', 'currency_code'],
            'type': 'string',
            'description': 'Code devise'
        },
        'identifier': {
            'keywords': ['id', 'reference', 'number', 'confirmation', 'booking', 'reservation', 'order'],
            'type': 'string',
            'description': 'Identifiant'
        },
        'contact_email': {
            'keywords': ['email', 'contactemail', 'useremail', 'mail'],
            'type': 'email',
            'description': 'Adresse email'
        }
    }
    
    def __init__(self, registry=None):
        """
        Initialise le mapper intelligent
        
        Args:
            registry: IntelligentServiceRegistry optionnel pour accéder aux annotations
        """
        self.registry = registry
        
        # Créer un index inversé pour recherche rapide
        self.keyword_to_semantic = {}
        for semantic, info in self.SEMANTIC_GROUPS.items():
            for keyword in info['keywords']:
                self.keyword_to_semantic[keyword] = semantic
    
    def map_parameters(self, 
                      source_data: Dict[str, Any],
                      target_params: List[str],
                      source_service: Optional[str] = None,
                      target_service: Optional[str] = None) -> Dict[str, Any]:
        """
        Mappe les paramètres de manière intelligente
        
        Args:
            source_data: Données disponibles
            target_params: Paramètres attendus
            source_service: Nom du service source (optionnel, pour annotations)
            target_service: Nom du service cible (optionnel, pour annotations)
            
        Returns:
            Dictionnaire des paramètres mappés
        """
        mapped = {}
        mapping_confidence = {}
        
        # Si on a accès aux services, utiliser les mappings d'interaction
        interaction_mappings = {}
        if self.registry and source_service and target_service:
            interaction_mappings = self._get_interaction_mappings(source_service, target_service)
        
        for target_param in target_params:
            # 1. Vérifier les mappings d'interaction d'abord (annotations LLM)
            if target_param in interaction_mappings:
                source_param = interaction_mappings[target_param]
                if source_param in source_data:
                    mapped[target_param] = source_data[source_param]
                    mapping_confidence[target_param] = 1.0  # Haute confiance
                    continue
            
            # 2. Correspondance exacte
            if target_param in source_data:
                mapped[target_param] = source_data[target_param]
                mapping_confidence[target_param] = 1.0
                continue
            
            # 3. Correspondance case-insensitive
            for source_key, source_value in source_data.items():
                if source_key.lower() == target_param.lower():
                    mapped[target_param] = source_value
                    mapping_confidence[target_param] = 0.95
                    break
            
            if target_param in mapped:
                continue
            
            # 4. Mapping sémantique (LLM-enhanced)
            result = self._find_semantic_match(source_data, target_param)
            if result:
                value, confidence = result
                mapped[target_param] = value
                mapping_confidence[target_param] = confidence
                continue
            
            # 5. Similarité avancée
            result = self._find_by_similarity(source_data, target_param)
            if result:
                value, confidence = result
                mapped[target_param] = value
                mapping_confidence[target_param] = confidence
        
        return mapped
    
    def _get_interaction_mappings(self, source_service: str, target_service: str) -> Dict[str, str]:
        """
        Récupère les mappings d'interaction depuis les annotations LLM
        """
        mappings = {}
        
        if not self.registry:
            return mappings
        
        source_annotation = self.registry.get_service_annotation(source_service)
        if not source_annotation:
            return mappings
        
        # Les annotations d'interaction peuvent contenir des mappings prédéfinis
        parameter_mappings = source_annotation.get('interaction', {}).get('parameter_mappings', [])
        
        for mapping in parameter_mappings:
            if isinstance(mapping, dict):
                source_param = mapping.get('source_param')
                target_param = mapping.get('target_param')
                if source_param and target_param:
                    mappings[target_param] = source_param
        
        return mappings
    
    def _find_semantic_match(self, source_data: Dict[str, Any], 
                            target_param: str) -> Optional[Tuple[Any, float]]:
        """
        Trouve une correspondance sémantique en utilisant les groupes sémantiques
        
        Returns:
            Tuple (valeur, confiance) ou None
        """
        target_normalized = self._normalize_param_name(target_param)
        target_semantic = self.keyword_to_semantic.get(target_normalized)
        
        if not target_semantic:
            return None
        
        # Chercher une source avec le même groupe sémantique
        for source_key, source_value in source_data.items():
            source_normalized = self._normalize_param_name(source_key)
            source_semantic = self.keyword_to_semantic.get(source_normalized)
            
            if source_semantic == target_semantic:
                return (source_value, 0.85)  # Haute confiance pour match sémantique
        
        return None
    
    def _find_by_similarity(self, source_data: Dict[str, Any], 
                           target_param: str) -> Optional[Tuple[Any, float]]:
        """
        Trouve une correspondance par similarité de nom
        
        Returns:
            Tuple (valeur, confiance) ou None
        """
        target_normalized = self._normalize_param_name(target_param)
        target_words = set(target_normalized.split())
        
        best_match = None
        best_similarity = 0.0
        
        for source_key, source_value in source_data.items():
            source_normalized = self._normalize_param_name(source_key)
            source_words = set(source_normalized.split())
            
            # Calcul de similarité (Jaccard)
            if not target_words or not source_words:
                continue
            
            intersection = len(target_words & source_words)
            union = len(target_words | source_words)
            similarity = intersection / union if union > 0 else 0
            
            if similarity > best_similarity and similarity >= 0.5:
                best_similarity = similarity
                best_match = source_value
        
        if best_match is not None:
            confidence = best_similarity * 0.7  # Confiance modérée
            return (best_match, confidence)
        
        return None
    
    def _normalize_param_name(self, param: str) -> str:
        """Normalise un nom de paramètre"""
        # Convertir camelCase et snake_case en mots séparés
        words = re.sub('([A-Z])', r' \1', param).split()
        words = ' '.join(words).replace('_', ' ').lower().split()
        return ' '.join(words)
    
    def get_mapping_plan(self,
                        source_data: Dict[str, Any],
                        target_params: List[str],
                        source_service: Optional[str] = None,
                        target_service: Optional[str] = None) -> Dict[str, Any]:
        """
        Crée un plan de mapping détaillé avec explications
        
        Returns:
            Plan complet avec mappings, confiance, et paramètres manquants
        """
        mapped = self.map_parameters(source_data, target_params, source_service, target_service)
        missing = [p for p in target_params if p not in mapped]
        
        # Analyser chaque mapping
        mapping_details = []
        for target_param, value in mapped.items():
            # Trouver la source
            source_param = None
            method = "unknown"
            
            # Exact match
            if target_param in source_data:
                source_param = target_param
                method = "exact_match"
            else:
                # Chercher dans source_data
                for key, val in source_data.items():
                    if val == value:
                        source_param = key
                        # Déterminer la méthode
                        if key.lower() == target_param.lower():
                            method = "case_insensitive"
                        else:
                            # Vérifier sémantique
                            source_norm = self._normalize_param_name(key)
                            target_norm = self._normalize_param_name(target_param)
                            
                            source_sem = self.keyword_to_semantic.get(source_norm)
                            target_sem = self.keyword_to_semantic.get(target_norm)
                            
                            if source_sem and source_sem == target_sem:
                                method = "semantic_match"
                            else:
                                method = "similarity_match"
                        break
            
            mapping_details.append({
                "target_param": target_param,
                "source_param": source_param,
                "value": value,
                "method": method
            })
        
        coverage = len(mapped) / len(target_params) if target_params else 1.0
        
        return {
            "mappings": mapping_details,
            "missing_parameters": missing,
            "coverage": coverage,
            "total_params": len(target_params),
            "mapped_params": len(mapped)
        }
    
    def suggest_missing_parameters(self, 
                                   missing_params: List[str],
                                   context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Suggère des valeurs pour les paramètres manquants basées sur le contexte
        
        Returns:
            Dictionnaire de suggestions
        """
        suggestions = {}
        
        for param in missing_params:
            normalized = self._normalize_param_name(param)
            semantic_group = self.keyword_to_semantic.get(normalized)
            
            if semantic_group:
                semantic_info = self.SEMANTIC_GROUPS[semantic_group]
                param_type = semantic_info['type']
                
                # Suggérer des valeurs par défaut selon le type
                if param_type == 'integer':
                    suggestions[param] = {
                        'suggested_value': 1,
                        'type': param_type,
                        'description': semantic_info['description']
                    }
                elif param_type == 'boolean':
                    suggestions[param] = {
                        'suggested_value': False,
                        'type': param_type,
                        'description': semantic_info['description']
                    }
                elif param_type == 'string':
                    suggestions[param] = {
                        'suggested_value': '',
                        'type': param_type,
                        'description': semantic_info['description'],
                        'note': 'Requis de l\'utilisateur'
                    }
            else:
                suggestions[param] = {
                    'suggested_value': None,
                    'type': 'unknown',
                    'description': 'Paramètre non reconnu',
                    'note': 'Requis de l\'utilisateur'
                }
        
        return suggestions


# Tests
if __name__ == "__main__":
    print("Test du Intelligent Parameter Mapper\n")
    
    mapper = IntelligentParameterMapper()
    
    # Test 1: Mapping sémantique avancé
    print("="*80)
    print("TEST 1: Mapping Sémantique Intelligent")
    print("="*80)
    
    source = {
        "origin": "Paris",
        "destination": "Tokyo",
        "departureDate": "2025-08-10",
        "returnDate": "2025-08-17",
        "passengers": 2,
        "totalPrice": 1500.00,
        "currency": "EUR"
    }
    
    target = ["from", "to", "outboundDate", "inboundDate", "adults", "amount", "currencyCode"]
    
    print("\nSource (service de vol):")
    for key, value in source.items():
        print(f"   {key}: {value}")
    
    print(f"\nTarget (service d'hôtel): {target}")
    
    mapped = mapper.map_parameters(source, target)
    
    print("\nMapping résultant:")
    for key, value in mapped.items():
        print(f"   {key} ← {value}")
    
    # Test 2: Plan de mapping détaillé
    print("\n\n" + "="*80)
    print("TEST 2: Plan de Mapping Détaillé")
    print("="*80)
    
    plan = mapper.get_mapping_plan(source, target)
    
    print(f"\nStatistiques:")
    print(f"   Coverage: {plan['coverage']*100:.0f}%")
    print(f"   Mappés: {plan['mapped_params']}/{plan['total_params']}")
    
    print(f"\nDétails des mappings:")
    for mapping in plan['mappings']:
        print(f"   • {mapping['target_param']} ← {mapping['source_param']}")
        print(f"     Méthode: {mapping['method']}")
        print(f"     Valeur: {mapping['value']}")
    
    if plan['missing_parameters']:
        print(f"\nParamètres manquants:")
        suggestions = mapper.suggest_missing_parameters(plan['missing_parameters'], {})
        for param in plan['missing_parameters']:
            print(f"   • {param}")
            if param in suggestions:
                sug = suggestions[param]
                print(f"     Type: {sug['type']}")
                print(f"     Description: {sug['description']}")