"""
composition_system/classic_service_selector.py
Sélecteur de services basé sur des règles simples (pas d'annotations LLM)
"""
import sys
import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from composition_system.classic_wsdl_parser import ClassicServiceRegistry, ServiceInfo


@dataclass
class SelectionResult:
    """Résultat de la sélection d'un service"""
    service: ServiceInfo
    reason: str
    alternatives: List[str]


class ClassicServiceSelector:
    """
    Sélecteur de services avec règles simples et déterministes
    AUCUNE intelligence artificielle - juste des règles hardcodées
    """
    
    # Règles de priorité hardcodées
    PRIORITY_RULES = {
        "flight": {
            # Ordre de préférence pour les services de vols
            "preferences": ["AmadeusFlightService", "SkyscannerFlightService"],
            "reason": "Amadeus a une couverture mondiale supérieure"
        },
        "hotel": {
            "preferences": ["BookingHotelService", "ExpediaHotelService"],
            "reason": "Booking.com a le plus grand inventaire d'hôtels"
        },
        "payment": {
            "preferences": ["StripePaymentService", "PayPalPaymentService"],
            "reason": "Stripe a des frais de transaction plus bas"
        },
        "weather": {
            "preferences": ["WeatherService"],
            "reason": "Service météo unique disponible"
        }
    }
    
    def __init__(self, registry: ClassicServiceRegistry):
        """
        Initialise le sélecteur
        
        Args:
            registry: Registre de services chargés
        """
        self.registry = registry
    
    def select_service(self, category: str, user_constraints: Optional[Dict[str, Any]] = None) -> Optional[SelectionResult]:
        """
        Sélectionne un service pour une catégorie donnée
        
        Args:
            category: Catégorie recherchée (flight, hotel, payment, etc.)
            user_constraints: Contraintes utilisateur (non utilisées dans version classique)
            
        Returns:
            SelectionResult avec le service sélectionné
        """
        print(f"\nSélection d'un service pour catégorie: {category}")
        
        # 1. Trouver tous les services de cette catégorie
        candidates = self.registry.find_by_category(category)
        
        if not candidates:
            print(f"   Aucun service trouvé pour la catégorie '{category}'")
            return None
        
        candidate_names = [s.name for s in candidates]
        print(f"   Services candidats: {', '.join(candidate_names)}")
        
        # 2. Appliquer les règles de priorité
        if category in self.PRIORITY_RULES:
            preferences = self.PRIORITY_RULES[category]["preferences"]
            reason = self.PRIORITY_RULES[category]["reason"]
            
            # Chercher le premier service préféré disponible
            for preferred_name in preferences:
                for candidate in candidates:
                    if candidate.name == preferred_name:
                        alternatives = [s.name for s in candidates if s.name != preferred_name]
                        
                        result = SelectionResult(
                            service=candidate,
                            reason=reason,
                            alternatives=alternatives
                        )
                        
                        print(f"   Service sélectionné: {candidate.name}")
                        print(f"   Raison: {reason}")
                        if alternatives:
                            print(f"   Alternatives non retenues: {', '.join(alternatives)}")
                        
                        return result
        
        # 3. Si pas de règle, prendre le premier (ordre alphabétique)
        selected = sorted(candidates, key=lambda s: s.name)[0]
        alternatives = [s.name for s in candidates if s.name != selected.name]
        
        result = SelectionResult(
            service=selected,
            reason="Sélection par défaut (ordre alphabétique)",
            alternatives=alternatives
        )
        
        print(f"   Service sélectionné: {selected.name}")
        print(f"   Raison: {result.reason}")
        
        return result
    
    def select_operation(self, service: ServiceInfo, required_function: str) -> Optional[str]:
        """
        Sélectionne une opération dans un service
        
        Args:
            service: Service dans lequel chercher
            required_function: Fonction recherchée (ex: "search", "book", "pay")
            
        Returns:
            Nom de l'opération ou None
        """
        required_lower = required_function.lower()
        
        # Chercher une opération qui contient le mot-clé
        for operation in service.operations:
            if required_lower in operation.name.lower():
                return operation.name
        
        # Si pas trouvé, retourner la première opération
        if service.operations:
            return service.operations[0].name
        
        return None
    
    def get_operation_details(self, service: ServiceInfo, operation_name: str) -> Optional[Dict]:
        """Récupère les détails d'une opération"""
        for op in service.operations:
            if op.name == operation_name:
                return {
                    "name": op.name,
                    "input_params": op.input_params,
                    "output_params": op.output_params,
                    "documentation": op.documentation
                }
        return None


class SimpleParameterMapper:
    """
    Mapper de paramètres simple basé sur correspondance exacte ou règles fixes
    AUCUNE intelligence - juste des mappings prédéfinis
    """
    
    # Mappings prédéfinis (hardcodés)
    KNOWN_MAPPINGS = {
        # Origine/Départ
        "origin": ["from", "departure", "departureAirport"],
        "from": ["origin", "departure"],
        "departure": ["origin", "from"],
        
        # Destination/Arrivée
        "destination": ["to", "arrival", "arrivalAirport", "city"],
        "to": ["destination", "arrival"],
        "arrival": ["destination", "to"],
        "city": ["destination", "location"],
        
        # Dates
        "departureDate": ["outboundDate", "checkInDate", "arrivalDate", "startDate"],
        "outboundDate": ["departureDate", "checkInDate"],
        "checkInDate": ["departureDate", "outboundDate", "arrivalDate"],
        "arrivalDate": ["checkInDate", "departureDate"],
        
        "returnDate": ["inboundDate", "checkOutDate", "departureDate", "endDate"],
        "inboundDate": ["returnDate", "checkOutDate"],
        "checkOutDate": ["returnDate", "inboundDate", "departureDate"],
        "departureDate": ["checkOutDate", "returnDate"],
        
        # Personnes
        "passengers": ["adults", "guests", "numberOfGuests"],
        "adults": ["passengers", "guests"],
        "guests": ["passengers", "adults", "numberOfGuests"],
        "numberOfGuests": ["passengers", "guests"],
        
        # Prix
        "price": ["amount", "totalPrice", "totalAmount"],
        "amount": ["price", "totalAmount"],
        "totalPrice": ["price", "amount"],
        "totalAmount": ["price", "amount"],
        
        # Devise
        "currency": ["currencyCode", "currency_code"],
        "currencyCode": ["currency"],
    }
    
    def map_parameters(self, source_data: Dict[str, Any], target_params: List[str]) -> Dict[str, Any]:
        """
        Mappe les paramètres source vers target
        
        Args:
            source_data: Données disponibles (du service précédent ou utilisateur)
            target_params: Paramètres attendus par le service cible
            
        Returns:
            Dictionnaire des paramètres mappés
        """
        mapped = {}
        
        for target_param in target_params:
            # 1. Correspondance exacte
            if target_param in source_data:
                mapped[target_param] = source_data[target_param]
                continue
            
            # 2. Correspondance case-insensitive
            for source_key, source_value in source_data.items():
                if source_key.lower() == target_param.lower():
                    mapped[target_param] = source_value
                    break
            
            if target_param in mapped:
                continue
            
            # 3. Utiliser les mappings connus
            if target_param in self.KNOWN_MAPPINGS:
                possible_sources = self.KNOWN_MAPPINGS[target_param]
                for possible in possible_sources:
                    if possible in source_data:
                        mapped[target_param] = source_data[possible]
                        break
        
        return mapped
    
    def find_missing_params(self, source_data: Dict[str, Any], target_params: List[str]) -> List[str]:
        """Identifie les paramètres qui ne peuvent pas être mappés"""
        mapped = self.map_parameters(source_data, target_params)
        missing = [p for p in target_params if p not in mapped]
        return missing


# Tests
if __name__ == "__main__":
    print("Test du Classic Service Selector\n")
    
    # Charger le registre
    registry = ClassicServiceRegistry()
    
    if not registry.services:
        print("Aucun service chargé")
        exit(1)
    
    # Créer le sélecteur
    selector = ClassicServiceSelector(registry)
    
    # Test 1: Sélection pour chaque catégorie
    print("="*80)
    print("TEST 1: Sélection de services par catégorie")
    print("="*80)
    
    categories = ["flight", "hotel", "payment"]
    
    for category in categories:
        result = selector.select_service(category)
        if result:
            print(f"\nRésultat pour {category}:")
            print(f"   Service: {result.service.name}")
            print(f"   Endpoint: {result.service.endpoint}")
            print(f"   Opérations disponibles: {[op.name for op in result.service.operations]}")
    
    # Test 2: Mapping de paramètres
    print("\n\n" + "="*80)
    print("TEST 2: Mapping de paramètres")
    print("="*80)
    
    mapper = SimpleParameterMapper()
    
    # Données du service de vol (sortie)
    flight_data = {
        "origin": "CDG",
        "destination": "JFK",
        "departureDate": "2025-07-15",
        "passengers": 2,
        "price": 450.00,
        "currency": "EUR"
    }
    
    # Paramètres attendus par service d'hôtel
    hotel_params = ["city", "checkInDate", "guests", "currency", "maxPrice"]
    
    print("\nDonnées disponibles (vol):")
    for key, value in flight_data.items():
        print(f"   {key}: {value}")
    
    print(f"\nParamètres attendus (hôtel): {hotel_params}")
    
    mapped = mapper.map_parameters(flight_data, hotel_params)
    
    print("\nMapping résultant:")
    for key, value in mapped.items():
        print(f"   {key} = {value}")
    
    missing = mapper.find_missing_params(flight_data, hotel_params)
    if missing:
        print(f"\nParamètres manquants: {missing}")
        print("   → Doivent être fournis par l'utilisateur")