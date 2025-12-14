"""
services/implementations/llm_recommendation_service.py
Service intelligent utilisant LLM pour recommander des destinations
"""
import sys
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from annotation_system.ollama_client import OllamaClient


@dataclass
class TravelRecommendation:
    """Recommandation de voyage générée par le LLM"""
    destination: str
    reason: str
    best_season: str
    estimated_budget: float
    activities: List[str]
    tips: List[str]
    confidence_score: float


@dataclass
class ItineraryDay:
    """Journée d'un itinéraire"""
    day_number: int
    date: str
    morning: str
    afternoon: str
    evening: str
    meals: Dict[str, str]
    estimated_cost: float


class IntelligentRecommendationService:
    """
    Service LLM-based pour recommander des destinations de voyage
    
    Ce service utilise un LLM pour :
    - Analyser les préférences utilisateur
    - Recommander des destinations adaptées
    - Générer des itinéraires personnalisés
    - Donner des conseils contextuels
    """
    
    def __init__(self, ollama_model: str = "llama3.2:3b"):
        """
        Initialise le service de recommandation
        
        Args:
            ollama_model: Modèle LLM à utiliser
        """
        self.llm_client = OllamaClient(model=ollama_model)
        self.service_name = "IntelligentRecommendationService"
    
    def recommend_destination(self, 
                             user_preferences: Dict[str, Any],
                             budget: float,
                             duration_days: int,
                             season: str = "any") -> Optional[TravelRecommendation]:
        """
        Recommande une destination basée sur les préférences utilisateur
        
        Args:
            user_preferences: Préférences (interests, travel_style, etc.)
            budget: Budget disponible
            duration_days: Durée du voyage
            season: Saison souhaitée
            
        Returns:
            TravelRecommendation ou None
        """
        print(f"\n🤖 {self.service_name}: Analyse des préférences...")
        
        prompt = f"""You are a professional travel advisor. Analyze these preferences and recommend ONE ideal destination.

User Preferences:
- Interests: {user_preferences.get('interests', [])}
- Travel Style: {user_preferences.get('travel_style', 'balanced')}
- Budget: ${budget:.2f}
- Duration: {duration_days} days
- Season: {season}
- Other preferences: {user_preferences.get('other', 'none')}

Respond with a JSON object containing:
{{
  "destination": "City, Country",
  "reason": "Why this destination matches their preferences (2-3 sentences)",
  "best_season": "Best time to visit",
  "estimated_budget": estimated total budget needed,
  "activities": ["activity1", "activity2", "activity3", "activity4"],
  "tips": ["practical tip1", "practical tip2", "practical tip3"],
  "confidence_score": 0.85
}}

Be specific, practical, and match the budget. Respond ONLY with valid JSON."""

        result = self.llm_client.generate_with_retry(prompt)
        
        if not result:
            print("   ✗ Échec de génération")
            return None
        
        try:
            recommendation = TravelRecommendation(
                destination=result['destination'],
                reason=result['reason'],
                best_season=result['best_season'],
                estimated_budget=result['estimated_budget'],
                activities=result['activities'],
                tips=result['tips'],
                confidence_score=result.get('confidence_score', 0.8)
            )
            
            print(f"   ✓ Recommandation: {recommendation.destination}")
            print(f"   Confiance: {recommendation.confidence_score:.0%}")
            
            return recommendation
            
        except Exception as e:
            print(f"   ✗ Erreur de parsing: {e}")
            return None
    
    def generate_personalized_itinerary(self,
                                       destination: str,
                                       duration_days: int,
                                       interests: List[str],
                                       budget_per_day: float) -> List[ItineraryDay]:
        """
        Génère un itinéraire jour par jour personnalisé
        
        Args:
            destination: Destination du voyage
            duration_days: Nombre de jours
            interests: Liste d'intérêts
            budget_per_day: Budget par jour
            
        Returns:
            Liste de ItineraryDay
        """
        print(f"\n🤖 {self.service_name}: Génération d'itinéraire pour {destination}...")
        
        prompt = f"""Create a detailed {duration_days}-day itinerary for {destination}.

Traveler interests: {', '.join(interests)}
Budget per day: ${budget_per_day:.2f}

For each day, provide a JSON object with:
{{
  "day_number": 1,
  "date": "Day 1",
  "morning": "Detailed morning activity",
  "afternoon": "Detailed afternoon activity", 
  "evening": "Detailed evening activity",
  "meals": {{"breakfast": "suggestion", "lunch": "suggestion", "dinner": "suggestion"}},
  "estimated_cost": daily cost
}}

Create an array of {duration_days} such objects. Make it realistic, engaging, and within budget.
Respond ONLY with a JSON array."""

        result = self.llm_client.generate_with_retry(prompt)
        
        if not result or not isinstance(result, list):
            print("   ✗ Échec de génération d'itinéraire")
            return []
        
        itinerary = []
        for day_data in result[:duration_days]:
            try:
                day = ItineraryDay(
                    day_number=day_data['day_number'],
                    date=day_data['date'],
                    morning=day_data['morning'],
                    afternoon=day_data['afternoon'],
                    evening=day_data['evening'],
                    meals=day_data['meals'],
                    estimated_cost=day_data['estimated_cost']
                )
                itinerary.append(day)
            except Exception as e:
                print(f"   ⚠️  Erreur jour {day_data.get('day_number', '?')}: {e}")
                continue
        
        print(f"   ✓ Itinéraire généré: {len(itinerary)} jours")
        return itinerary
    
    def analyze_user_preferences(self, free_text: str) -> Dict[str, Any]:
        """
        Analyse du texte libre pour extraire les préférences
        
        Args:
            free_text: Description libre des souhaits de voyage
            
        Returns:
            Dictionnaire structuré de préférences
        """
        print(f"\n🤖 {self.service_name}: Analyse du texte libre...")
        
        prompt = f"""Analyze this travel request and extract structured preferences:

User request: "{free_text}"

Extract and respond with JSON:
{{
  "interests": ["list of detected interests"],
  "travel_style": "adventure/luxury/budget/cultural/relaxation",
  "budget_range": "low/medium/high/luxury",
  "must_have": ["essential requirements"],
  "avoid": ["things to avoid"],
  "season_preference": "spring/summer/fall/winter/any",
  "group_size": estimated number of travelers,
  "special_needs": ["dietary restrictions, accessibility, etc."]
}}

Respond ONLY with valid JSON."""

        result = self.llm_client.generate_with_retry(prompt)
        
        if result:
            print(f"   ✓ Préférences extraites:")
            print(f"      Intérêts: {', '.join(result.get('interests', []))}")
            print(f"      Style: {result.get('travel_style', 'N/A')}")
            return result
        else:
            print("   ✗ Échec d'analyse")
            return {}
    
    def provide_contextual_advice(self,
                                 destination: str,
                                 context: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Fournit des conseils contextuels pour une destination
        
        Args:
            destination: Destination
            context: Contexte (saison, budget, etc.)
            
        Returns:
            Conseils catégorisés
        """
        print(f"\n🤖 {self.service_name}: Conseils pour {destination}...")
        
        prompt = f"""Provide practical travel advice for {destination}.

Context:
- Season: {context.get('season', 'any')}
- Budget level: {context.get('budget_level', 'medium')}
- Traveler type: {context.get('traveler_type', 'tourist')}

Provide advice in JSON format:
{{
  "packing": ["item1", "item2", "item3"],
  "safety": ["safety tip1", "safety tip2", "safety tip3"],
  "money": ["financial tip1", "financial tip2"],
  "cultural": ["cultural tip1", "cultural tip2", "cultural tip3"],
  "transportation": ["transport tip1", "transport tip2"],
  "food": ["food tip1", "food tip2"]
}}

Give 2-4 specific, practical tips per category. Respond ONLY with JSON."""

        result = self.llm_client.generate_with_retry(prompt)
        
        if result:
            total_tips = sum(len(tips) for tips in result.values())
            print(f"   ✓ {total_tips} conseils générés")
            return result
        else:
            print("   ✗ Échec de génération de conseils")
            return {}


# Test du service
if __name__ == "__main__":
    print("TEST DU SERVICE DE RECOMMANDATION INTELLIGENT\n")
    
    # Créer le service
    try:
        service = IntelligentRecommendationService()
    except Exception as e:
        print(f"❌ Erreur: {e}")
        print("Assurez-vous qu'Ollama est lancé: ollama serve")
        exit(1)
    
    # Test 1: Recommandation
    print("="*80)
    print("TEST 1: Recommandation de destination")
    print("="*80)
    
    preferences = {
        "interests": ["culture", "food", "history"],
        "travel_style": "cultural",
        "other": "wants authentic local experiences"
    }
    
    recommendation = service.recommend_destination(
        user_preferences=preferences,
        budget=2000.0,
        duration_days=7,
        season="spring"
    )
    
    if recommendation:
        print(f"\n📍 Destination recommandée: {recommendation.destination}")
        print(f"💭 Raison: {recommendation.reason}")
        print(f"📅 Meilleure période: {recommendation.best_season}")
        print(f"💰 Budget estimé: ${recommendation.estimated_budget:.2f}")
        print(f"\n🎯 Activités suggérées:")
        for activity in recommendation.activities:
            print(f"   • {activity}")
        print(f"\n💡 Conseils pratiques:")
        for tip in recommendation.tips:
            print(f"   • {tip}")
    
    # Test 2: Analyse de texte libre
    print("\n\n" + "="*80)
    print("TEST 2: Analyse de texte libre")
    print("="*80)
    
    free_text = "Je voudrais partir en vacances au soleil avec ma famille (2 adultes, 2 enfants). On aime la plage, la nature, et on a un budget moyen. Pas de destinations trop touristiques."
    
    analyzed = service.analyze_user_preferences(free_text)
    
    if analyzed:
        print(f"\n📊 Analyse:")
        print(f"   Style de voyage: {analyzed.get('travel_style')}")
        print(f"   Budget: {analyzed.get('budget_range')}")
        print(f"   Taille du groupe: {analyzed.get('group_size')}")
    
    # Test 3: Génération d'itinéraire (court pour le test)
    print("\n\n" + "="*80)
    print("TEST 3: Génération d'itinéraire")
    print("="*80)
    
    itinerary = service.generate_personalized_itinerary(
        destination="Kyoto, Japan",
        duration_days=3,
        interests=["temples", "food", "gardens"],
        budget_per_day=150.0
    )
    
    if itinerary:
        print(f"\n📅 Itinéraire de {len(itinerary)} jours:")
        for day in itinerary[:2]:  # Afficher 2 premiers jours
            print(f"\n   Jour {day.day_number} - {day.date}")
            print(f"      Matin: {day.morning[:80]}...")
            print(f"      Après-midi: {day.afternoon[:80]}...")
            print(f"      Coût estimé: ${day.estimated_cost:.2f}")
    
    print("\n\n✅ Tests terminés!")