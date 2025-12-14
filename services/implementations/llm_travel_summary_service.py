"""
services/implementations/llm_travel_summary_service.py
Service LLM pour générer des résumés et analyses de voyage
"""
import sys
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from annotation_system.ollama_client import OllamaClient


@dataclass
class TravelSummary:
    """Résumé personnalisé d'un voyage"""
    title: str
    overview: str
    highlights: List[str]
    practical_info: Dict[str, str]
    estimated_costs_breakdown: Dict[str, float]
    personalized_message: str


@dataclass
class ServiceComparison:
    """Comparaison intelligente de services"""
    best_choice: str
    reason: str
    alternatives: List[Dict[str, Any]]
    cost_analysis: str
    recommendation_strength: float


class IntelligentTravelSummaryService:
    """
    Service LLM-based pour résumer et analyser des données de voyage
    
    Fonctionnalités :
    - Génère des résumés personnalisés de voyages
    - Compare intelligemment plusieurs options
    - Analyse les coûts et donne des recommandations
    - Crée des documents de voyage formatés
    """
    
    def __init__(self, ollama_model: str = "llama3.2:3b"):
        self.llm_client = OllamaClient(model=ollama_model)
        self.service_name = "IntelligentTravelSummaryService"
    
    def generate_trip_summary(self,
                             flight_details: Dict[str, Any],
                             hotel_details: Dict[str, Any],
                             user_profile: Dict[str, Any]) -> Optional[TravelSummary]:
        """
        Génère un résumé personnalisé du voyage
        
        Args:
            flight_details: Détails du vol sélectionné
            hotel_details: Détails de l'hôtel sélectionné
            user_profile: Profil utilisateur
            
        Returns:
            TravelSummary ou None
        """
        print(f"\n🤖 {self.service_name}: Génération du résumé de voyage...")
        
        prompt = f"""Create a personalized travel summary for this trip.

Flight Details:
{self._format_dict(flight_details)}

Hotel Details:
{self._format_dict(hotel_details)}

User Profile:
- Name: {user_profile.get('name', 'Traveler')}
- Interests: {user_profile.get('interests', [])}
- Travel style: {user_profile.get('travel_style', 'standard')}

Generate a JSON response:
{{
  "title": "Catchy trip title",
  "overview": "2-3 sentence overview of the trip",
  "highlights": ["highlight1", "highlight2", "highlight3", "highlight4"],
  "practical_info": {{
    "check_in": "practical check-in info",
    "transportation": "how to get from airport to hotel",
    "weather": "expected weather info",
    "currency": "currency and money tips"
  }},
  "estimated_costs_breakdown": {{
    "flight": flight cost,
    "hotel": hotel cost,
    "meals": estimated meals cost,
    "activities": estimated activities cost,
    "transportation": estimated local transport cost,
    "total": total estimated cost
  }},
  "personalized_message": "Encouraging 2-3 sentence personalized message based on their interests"
}}

Be specific, practical, and encouraging. Respond ONLY with JSON."""

        result = self.llm_client.generate_with_retry(prompt)
        
        if not result:
            print("   ✗ Échec de génération")
            return None
        
        try:
            summary = TravelSummary(
                title=result['title'],
                overview=result['overview'],
                highlights=result['highlights'],
                practical_info=result['practical_info'],
                estimated_costs_breakdown=result['estimated_costs_breakdown'],
                personalized_message=result['personalized_message']
            )
            
            print(f"   ✓ Résumé généré: {summary.title}")
            return summary
            
        except Exception as e:
            print(f"   ✗ Erreur: {e}")
            return None
    
    def compare_service_options(self,
                               options: List[Dict[str, Any]],
                               user_priorities: Dict[str, float]) -> Optional[ServiceComparison]:
        """
        Compare intelligemment plusieurs options de service
        
        Args:
            options: Liste d'options (vols, hôtels, etc.)
            user_priorities: Priorités utilisateur (price: 0.8, quality: 0.6, etc.)
            
        Returns:
            ServiceComparison ou None
        """
        print(f"\n🤖 {self.service_name}: Comparaison de {len(options)} options...")
        
        prompt = f"""You are a travel advisor. Compare these service options and recommend the best one.

Options:
{self._format_options(options)}

User Priorities (0-1 scale):
{self._format_dict(user_priorities)}

Analyze and respond with JSON:
{{
  "best_choice": "name or id of best option",
  "reason": "Detailed 2-3 sentence explanation considering user priorities",
  "alternatives": [
    {{"name": "alt1", "pros": ["pro1", "pro2"], "cons": ["con1"]}},
    {{"name": "alt2", "pros": ["pro1"], "cons": ["con1", "con2"]}}
  ],
  "cost_analysis": "Brief cost comparison and value assessment",
  "recommendation_strength": 0.85
}}

Be objective, consider trade-offs. Respond ONLY with JSON."""

        result = self.llm_client.generate_with_retry(prompt)
        
        if not result:
            print("   ✗ Échec de comparaison")
            return None
        
        try:
            comparison = ServiceComparison(
                best_choice=result['best_choice'],
                reason=result['reason'],
                alternatives=result['alternatives'],
                cost_analysis=result['cost_analysis'],
                recommendation_strength=result.get('recommendation_strength', 0.7)
            )
            
            print(f"   ✓ Meilleur choix: {comparison.best_choice}")
            print(f"   Confiance: {comparison.recommendation_strength:.0%}")
            
            return comparison
            
        except Exception as e:
            print(f"   ✗ Erreur: {e}")
            return None
    
    def generate_booking_document(self,
                                  trip_summary: TravelSummary,
                                  booking_details: Dict[str, Any]) -> str:
        """
        Génère un document de réservation formaté
        
        Args:
            trip_summary: Résumé du voyage
            booking_details: Détails de réservation
            
        Returns:
            Document formaté en texte
        """
        print(f"\n🤖 {self.service_name}: Génération du document de réservation...")
        
        prompt = f"""Create a professional booking confirmation document.

Trip Summary:
- Title: {trip_summary.title}
- Overview: {trip_summary.overview}

Booking Details:
{self._format_dict(booking_details)}

Create a well-formatted text document with:
1. Header with booking reference
2. Trip overview
3. Flight details section
4. Hotel details section  
5. Cost breakdown
6. Important reminders
7. Emergency contacts section

Make it professional, clear, and helpful. Return plain text."""

        system_prompt = "You are a professional travel document generator. Create clear, well-structured documents."
        
        result = self.llm_client.generate(prompt, system_prompt, format="")
        
        if result["success"]:
            document = result["response"]
            print(f"   ✓ Document généré ({len(document)} caractères)")
            return document
        else:
            print(f"   ✗ Échec: {result['error']}")
            return ""
    
    def analyze_trip_feasibility(self,
                                destination: str,
                                budget: float,
                                duration: int,
                                requirements: List[str]) -> Dict[str, Any]:
        """
        Analyse la faisabilité d'un voyage
        
        Args:
            destination: Destination souhaitée
            budget: Budget disponible
            duration: Durée en jours
            requirements: Exigences spécifiques
            
        Returns:
            Analyse de faisabilité
        """
        print(f"\n🤖 {self.service_name}: Analyse de faisabilité...")
        
        prompt = f"""Analyze if this trip is feasible and provide recommendations.

Trip Plan:
- Destination: {destination}
- Budget: ${budget:.2f}
- Duration: {duration} days
- Requirements: {', '.join(requirements)}

Analyze and respond with JSON:
{{
  "is_feasible": true/false,
  "confidence": 0.85,
  "budget_assessment": {{
    "sufficient": true/false,
    "estimated_needed": estimated total cost,
    "shortfall": 0 or amount missing,
    "breakdown": "brief explanation"
  }},
  "duration_assessment": {{
    "appropriate": true/false,
    "recommended_days": suggested duration,
    "reasoning": "explanation"
  }},
  "requirements_analysis": [
    {{"requirement": "req1", "achievable": true, "notes": "notes"}},
    {{"requirement": "req2", "achievable": false, "notes": "why not"}}
  ],
  "recommendations": ["recommendation1", "recommendation2", "recommendation3"],
  "alternatives": ["alternative suggestion if not feasible"]
}}

Be realistic and helpful. Respond ONLY with JSON."""

        result = self.llm_client.generate_with_retry(prompt)
        
        if result:
            print(f"   ✓ Faisabilité: {'OUI' if result.get('is_feasible') else 'NON'}")
            return result
        else:
            print("   ✗ Échec d'analyse")
            return {}
    
    def _format_dict(self, d: Dict) -> str:
        """Formate un dictionnaire pour le prompt"""
        return '\n'.join(f"- {k}: {v}" for k, v in d.items())
    
    def _format_options(self, options: List[Dict]) -> str:
        """Formate une liste d'options"""
        result = []
        for i, opt in enumerate(options, 1):
            result.append(f"\nOption {i}:")
            result.append(self._format_dict(opt))
        return '\n'.join(result)


# Test du service
if __name__ == "__main__":
    print("TEST DU SERVICE DE RÉSUMÉ INTELLIGENT\n")
    
    try:
        service = IntelligentTravelSummaryService()
    except Exception as e:
        print(f"❌ Erreur: {e}")
        exit(1)
    
    # Test 1: Génération de résumé
    print("="*80)
    print("TEST 1: Génération de résumé de voyage")
    print("="*80)
    
    flight = {
        "from": "Paris",
        "to": "Tokyo",
        "departure": "2025-08-10 10:00",
        "arrival": "2025-08-10 18:00",
        "price": 650.00,
        "airline": "Air France"
    }
    
    hotel = {
        "name": "Tokyo Grand Hotel",
        "stars": 4,
        "location": "Shibuya",
        "price_per_night": 120.00,
        "nights": 7
    }
    
    user = {
        "name": "Marie Dubois",
        "interests": ["culture", "food", "technology"],
        "travel_style": "cultural explorer"
    }
    
    summary = service.generate_trip_summary(flight, hotel, user)
    
    if summary:
        print(f"\n📋 {summary.title}")
        print(f"\n{summary.overview}")
        print(f"\n🌟 Points forts:")
        for h in summary.highlights:
            print(f"   • {h}")
        print(f"\n💰 Coûts estimés:")
        for category, cost in summary.estimated_costs_breakdown.items():
            print(f"   {category}: ${cost:.2f}")
        print(f"\n💬 Message personnalisé:")
        print(f"   {summary.personalized_message}")
    
    # Test 2: Comparaison d'options
    print("\n\n" + "="*80)
    print("TEST 2: Comparaison de services")
    print("="*80)
    
    options = [
        {"name": "Budget Hotel", "price": 80, "stars": 3, "rating": 4.1, "distance_km": 5},
        {"name": "Luxury Resort", "price": 200, "stars": 5, "rating": 4.8, "distance_km": 15},
        {"name": "City Center Inn", "price": 120, "stars": 4, "rating": 4.5, "distance_km": 1}
    ]
    
    priorities = {
        "price": 0.7,
        "location": 0.9,
        "comfort": 0.6
    }
    
    comparison = service.compare_service_options(options, priorities)
    
    if comparison:
        print(f"\n🏆 Meilleur choix: {comparison.best_choice}")
        print(f"📊 Raison: {comparison.reason}")
        print(f"💵 Analyse des coûts: {comparison.cost_analysis}")
        print(f"\n🔄 Alternatives:")
        for alt in comparison.alternatives:
            print(f"\n   {alt['name']}:")
            print(f"      Avantages: {', '.join(alt['pros'])}")
            print(f"      Inconvénients: {', '.join(alt['cons'])}")
    
    print("\n\n✅ Tests terminés!")