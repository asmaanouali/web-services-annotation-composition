# Système Intelligent de Composition de Services Web

## Vue d'ensemble

Ce projet implémente un **système complet de composition de services web** combinant annotation automatique par LLM et composition classique. Il démontre comment automatiser la description et la composition de services web qui s'adaptent aux besoins changeants, aux environnements et à la disponibilité des services.

### Objectifs du Projet
1. **Automatiser l'annotation des services** : Enrichir les WSDL avec des métadonnées sémantiques
2. **Résoudre le problème de composition** : "Un service A a besoin d'une fonction X, mais plusieurs services la fournissent - lequel choisir ?"
3. **Comparer deux approches** : Composition classique vs composition intelligente (avec LLM)

### Contexte
Stage ESI - CERIST  
**Superviseur** : Amel Benna, DSISM, CERIST  
**Référence** : [1] A. Benna, Z. Maamar, M. Ahmed-Nacer: A MOF-based Social Web Services Description Metamodel. MODELSWARD 2016: 217-224

---

## Architecture Globale

```
project/
├── services/
│   ├── wsdl/
│   │   ├── original/              # WSDL bruts (7 services)
│   │   │   ├── AmadeusFlightService.wsdl
│   │   │   ├── SkyscannerFlightService.wsdl
│   │   │   ├── BookingHotelService.wsdl
│   │   │   ├── ExpediaHotelService.wsdl
│   │   │   ├── StripePaymentService.wsdl
│   │   │   ├── PayPalPaymentService.wsdl
│   │   │   └── WeatherService.wsdl
│   │   │
│   │   └── annotated/             # Annotations JSON générées par LLM
│   │       ├── AmadeusFlightService_annotated.json
│   │       ├── SkyscannerFlightService_annotated.json
│   │       └── ...
│   │
│   └── implementations/           # Implémentations mock (futur)
│
├── models/
│   └── annotation_model.py       # Modèle de données des annotations
│
├── annotation_system/
│   ├── wsdl_parser.py            # Parser WSDL pour LLM
│   ├── ollama_client.py          # Client pour Ollama
│   ├── annotation_generator.py   # Générateur d'annotations
│   └── batch_annotate.py         # Annotation batch
│
├── composition_system/
│   ├── classic_wsdl_parser.py           # Parser pour composition classique
│   ├── classic_service_selector.py     # Sélection basée sur règles
│   ├── classic_composition_engine.py   # Moteur de composition classique
│   └── results/                         # Résultats de composition
│
├── main_classic_composition.py   # Script de démonstration
└── README.md                      # Ce fichier
```

---

# PARTIE 1 : Système d'Annotation Automatique

## Objectif
Enrichir automatiquement les descriptions WSDL avec des annotations sémantiques en utilisant un LLM (Large Language Model).

## Composants

### 1. Modèle d'Annotations (`models/annotation_model.py`)

Basé sur le papier de référence [1], le modèle définit **4 types d'annotations** :

#### 📋 Annotation Fonctionnelle
```python
@dataclass
class FunctionalAnnotation:
    service_category: ServiceCategory  # search, booking, payment, etc.
    capabilities: List[str]            # Liste des capacités
    semantic_description: str          # Description sémantique
    keywords: List[str]                # Mots-clés pour recherche
    special_features: Dict            # Features spécifiques
    input_parameters: List[str]
    output_parameters: List[str]
```

**Exemple** :
```json
{
  "service_category": "search",
  "capabilities": ["search_flights", "multi_city_search", "flexible_dates"],
  "special_features": {
    "supports_multi_currency": true,
    "max_passengers": 9
  }
}
```

#### 🔗 Annotation d'Interaction
```python
@dataclass
class InteractionAnnotation:
    compatible_services: List[str]      # Services compatibles
    requires_services: List[str]        # Dépendances
    provides_for_services: List[str]    # Services suivants possibles
    parameter_mappings: List[ParameterMapping]
    quality_metrics: QualityMetrics     # Métriques de qualité
```

**Exemple** :
```json
{
  "requires_services": [],
  "provides_for_services": ["booking", "payment"],
  "quality_metrics": {
    "response_time_ms": 1200,
    "success_rate": 0.95,
    "cost_per_call": 0.01
  }
}
```

#### Annotation de Contexte
```python
@dataclass
class ContextAnnotation:
    geographic_coverage: List[str]      # ["EU", "US", "GLOBAL"]
    location_aware: bool
    temporal_constraints: List[str]     # Contraintes temporelles
    timezone_support: bool
    adaptation_capabilities: List[str]   # auto_retry, fallback, etc.
```

#### Annotation de Politique
```python
@dataclass
class PolicyAnnotation:
    privacy_policies: List[DataPrivacyPolicy]
    usage_policy: UsagePolicy           # Rate limit, pricing
    security_requirements: List[str]    # TLS, OAuth2, etc.
    compliance_standards: List[str]     # GDPR, PCI-DSS, etc.
```

**Exemple** :
```json
{
  "usage_policy": {
    "rate_limit": 1000,
    "pricing_model": "pay_per_use",
    "cost_per_request": 0.01,
    "guaranteed_uptime": 0.99
  },
  "compliance_standards": ["GDPR", "PCI-DSS"]
}
```

---

### 2. Parser WSDL (`annotation_system/wsdl_parser.py`)

**Rôle** : Extraire les informations des WSDL pour préparer l'annotation par LLM

**Fonctionnalités** :
- Parse XML des WSDL
- Extrait les opérations et leurs paramètres
- Génère un format JSON simplifié pour le LLM

**Exemple d'utilisation** :
```python
parser = WSDLParser("services/wsdl/original/AmadeusFlightService.wsdl")
llm_data = parser.extract_for_llm()

# Résultat :
{
  "service_name": "AmadeusFlightService",
  "operations": [{
    "name": "SearchFlights",
    "input_parameters": [
      {"name": "origin", "type": "string", "required": true},
      {"name": "destination", "type": "string", "required": true}
    ]
  }]
}
```

---

### 3. Client Ollama (`annotation_system/ollama_client.py`)

**Rôle** : Communiquer avec l'API Ollama pour générer les annotations

**Prérequis** :
```bash
# Installer Ollama : https://ollama.ai
# Télécharger le modèle
ollama pull llama3.2:3b

# Lancer le serveur
ollama serve
```

**Fonctionnalités** :
- Connexion à Ollama (localhost:11434)
- Génération de JSON structuré
- Retry automatique en cas d'échec
- Parsing robuste des réponses

**Exemple** :
```python
client = OllamaClient(model="llama3.2:3b")
result = client.generate(prompt, format="json")
```

---

### 4. Générateur d'Annotations (`annotation_system/annotation_generator.py`)

**Rôle** : Orchestrer l'annotation automatique complète

**Processus** :
1. Parse le WSDL
2. Génère l'annotation fonctionnelle (via LLM)
3. Génère l'annotation d'interaction (via LLM)
4. Génère l'annotation de contexte (via LLM)
5. Génère l'annotation de politique (via LLM)
6. Sauvegarde le JSON complet

**Exemple d'utilisation** :
```python
generator = AnnotationGenerator(ollama_model="llama3.2:3b")
annotation = generator.generate_annotation("services/wsdl/original/AmadeusFlightService.wsdl")
# Génère : AmadeusFlightService_annotated.json
```

---

### 5. Annotation Batch (`annotation_system/batch_annotate.py`)

**Rôle** : Annoter tous les services en une seule commande

**Utilisation** :
```bash
python annotation_system/batch_annotate.py --model llama3.2:3b
```

**Résultat** :
- 7 fichiers JSON annotés dans `services/wsdl/annotated/`
- Rapport de génération (`annotation_report.json`)

---

## Résultats de l'Annotation

### Exemple d'annotation complète

**Entrée** : `AmadeusFlightService.wsdl` (WSDL brut)

**Sortie** : `AmadeusFlightService_annotated.json`
```json
{
  "annotation_id": "amadeus_flight_001",
  "service_name": "AmadeusFlightService",
  "functional": {
    "service_category": "search",
    "capabilities": ["search_flights", "book_flights", "multi_city"],
    "special_features": {
      "supports_multi_currency": true,
      "global_coverage": true
    }
  },
  "interaction": {
    "requires_services": [],
    "provides_for_services": ["booking", "payment"],
    "quality_metrics": {
      "response_time_ms": 1200,
      "success_rate": 0.95,
      "cost_per_call": 0.01
    }
  },
  "context": {
    "geographic_coverage": ["GLOBAL"],
    "location_aware": true,
    "temporal_constraints": ["24/7_available"]
  },
  "policy": {
    "usage_policy": {
      "rate_limit": 1000,
      "cost_per_request": 0.01,
      "pricing_model": "pay_per_use"
    },
    "compliance_standards": ["GDPR", "PCI-DSS"]
  }
}
```

---

# PARTIE 2 : Système de Composition Classique

## Objectif
Composer automatiquement des workflows de services **sans utiliser les annotations LLM**, uniquement avec des règles prédéfinies et le parsing WSDL.

## 🔧 Composants

### 1. Classic WSDL Parser (`composition_system/classic_wsdl_parser.py`)

**Rôle** : Parser minimaliste des WSDL pour composition classique

**Différence avec le parser d'annotation** :
- Plus simple, moins de détails
- Détection automatique de catégorie par mots-clés
- Pas d'extraction pour LLM

**Fonctionnalités** :
```python
parser = ClassicWSDLParser("services/wsdl/original/AmadeusFlightService.wsdl")
service = parser.parse()

# Résultat : ServiceInfo
- name: "AmadeusFlightService"
- category: "flight" (détecté automatiquement)
- operations: [ServiceOperation(...)]
- endpoint: "http://api.amadeus.example.com/flights/v1"
```

---

### 2. Classic Service Selector (`composition_system/classic_service_selector.py`)

**Rôle** : Sélectionner les services selon des **règles hardcodées**

#### Règles de Priorité
```python
PRIORITY_RULES = {
    "flight": {
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
    }
}
```

#### Algorithme de Sélection
1. Découvrir tous les services de la catégorie
2. Appliquer les règles de priorité
3. Retourner le premier service disponible dans l'ordre
4. Justifier le choix

**Exemple** :
```python
selector = ClassicServiceSelector(registry)
result = selector.select_service("flight")

# Résultat :
- service: AmadeusFlightService
- reason: "Amadeus a une couverture mondiale supérieure"
- alternatives: ["SkyscannerFlightService"]
```

---

### 3. Simple Parameter Mapper (`composition_system/classic_service_selector.py`)

**Rôle** : Mapper les paramètres entre services avec des **mappings prédéfinis**

#### Mappings Hardcodés
```python
KNOWN_MAPPINGS = {
    "origin": ["from", "departure", "departureAirport"],
    "destination": ["to", "arrival", "city"],
    "departureDate": ["outboundDate", "checkInDate", "arrivalDate"],
    "passengers": ["adults", "guests", "numberOfGuests"],
    "price": ["amount", "totalPrice", "totalAmount"],
    ...
}
```

#### Algorithme de Mapping
1. **Correspondance exacte** (case-sensitive)
2. **Correspondance case-insensitive**
3. **Utilisation des mappings prédéfinis**
4. **Identification des paramètres manquants**

**Exemple** :
```python
mapper = SimpleParameterMapper()

source = {
    "origin": "Paris",
    "destination": "Tokyo",
    "departureDate": "2025-08-10",
    "passengers": 1
}

target_params = ["from", "to", "outboundDate", "adults"]

result = mapper.map_parameters(source, target_params)

# Résultat :
{
    "from": "Paris",           # origin → from
    "to": "Tokyo",             # destination → to
    "outboundDate": "2025-08-10",  # departureDate → outboundDate
    "adults": 1                # passengers → adults
}
```

---

### 4. Classic Composition Engine (`composition_system/classic_composition_engine.py`)

**Rôle** : Orchestrer la composition complète du workflow

#### Workflows Prédéfinis
```python
WORKFLOW_TEMPLATES = {
    "book_complete_travel": [
        {"step": 1, "category": "flight", "function": "search"},
        {"step": 2, "category": "hotel", "function": "search"},
        {"step": 3, "category": "payment", "function": "process"}
    ]
}
```

#### Processus de Composition
```
Pour chaque étape du workflow:
  1. Sélectionner le service (ClassicServiceSelector)
     ↓
  2. Choisir l'opération appropriée
     ↓
  3. Mapper les paramètres (SimpleParameterMapper)
     ↓
  4. Calculer la couverture (% de paramètres mappés)
     ↓
  5. Identifier les paramètres manquants
     ↓
  6. Enrichir le contexte avec les sorties
     ↓
  7. Passer à l'étape suivante
```

**Exemple d'utilisation** :
```python
engine = ClassicCompositionEngine(registry)

result = engine.compose(
    goal="book_complete_travel",
    user_input={
        "origin": "Paris",
        "destination": "Tokyo",
        "departureDate": "2025-08-10",
        "returnDate": "2025-08-17",
        "passengers": 1
    }
)
```

---

## Résultat de Composition Classique

### Workflow Généré

```
COMPOSITION RÉUSSIE

ÉTAPE 1: FLIGHT
   Service: SkyscannerFlightService
   Opération: FindFlights
   Raison: Amadeus a une couverture mondiale supérieure
   
   Entrées (56% mappés):
   • from = Paris
   • to = Tokyo
   • outboundDate = 2025-08-10
   • inboundDate = 2025-08-17
   • adults = 1
   
   Manquants:
   • children, infants, cabinClass, directFlightsOnly

ÉTAPE 2: HOTEL
   Service: BookingHotelService
   Opération: SearchHotels
   Raison: Booking.com a le plus grand inventaire
   Alternatives: ExpediaHotelService
   
   Entrées (88% mappés):
   • city = Tokyo
   • checkInDate = 2025-08-10
   • checkOutDate = 2025-08-17
   • guests = 1
   • rooms = 1
   • minStars = 4
   
   Manquants:
   • amenities

ÉTAPE 3: PAYMENT
   Service: StripePaymentService
   Opération: ProcessPayment
   Raison: Stripe a des frais plus bas
   Alternatives: PayPalPaymentService
   
   Entrées (11% mappés):
   • currency = EUR
   
   Manquants:
   • amount, cardNumber, expiryMonth, expiryYear, cvv, etc.
```

### Statistiques
```
STATISTIQUES GLOBALES:
   • Étapes complétées: 3/3
   • Services utilisés: 3
   • Couverture moyenne: 51.4%
   • Paramètres manquants: 13
```

---

# Utilisation Complète

## Prérequis

```bash
# Python 3.8+
python --version

# Ollama (pour l'annotation)
ollama --version

# Modèle LLM
ollama pull llama3.2:3b
```

## Installation

```bash
# Cloner le projet
git clone <repository>
cd project

# Créer la structure
python create_structure.py

# Générer les WSDL
python create_wsdl_files.py
```

## Workflow Complet

### Étape 1 : Annotation Automatique (Phase 2)

```bash
# Lancer Ollama
ollama serve

# Annoter tous les services
python annotation_system/batch_annotate.py
```

**Résultat** : 7 fichiers JSON dans `services/wsdl/annotated/`

### Étape 2 : Composition Classique (Phase 3A)

```bash
# Exécuter la démonstration
python main_classic_composition.py
```

**Résultat** : Workflow complet affiché + JSON sauvegardé

---

# Structure des Fichiers Générés

## Annotations (JSON)

```
services/wsdl/annotated/
├── AmadeusFlightService_annotated.json
├── SkyscannerFlightService_annotated.json
├── BookingHotelService_annotated.json
├── ExpediaHotelService_annotated.json
├── StripePaymentService_annotated.json
├── PayPalPaymentService_annotated.json
├── WeatherService_annotated.json
└── annotation_report.json
```

## Résultats de Composition

```
composition_system/results/
└── wf_YYYYMMDD_HHMMSS_classic.json
```

**Contenu** :
```json
{
  "workflow_id": "wf_20251127_065930",
  "goal": "book_complete_travel",
  "success": true,
  "total_steps": 3,
  "steps": [
    {
      "step_number": 1,
      "selected_service": "SkyscannerFlightService",
      "mapping_coverage": 0.56,
      "missing_parameters": ["children", "infants", ...]
    }
  ]
}
```

---

# Cas de Test Complet ( le fichier main.py )

## Scénario : Voyage d'affaires Paris → Tokyo

**Utilisateur** : Jean Dupont, TechCorp International  
**Budget** : 3500 EUR  
**Période** : 10-17 Août 2025  

**Entrées** :
```python
{
    "origin": "Paris",
    "destination": "Tokyo",
    "departureDate": "2025-08-10",
    "returnDate": "2025-08-17",
    "passengers": 1,
    "currency": "EUR",
    "maxPrice": 3500.00
}
```

**Workflow Généré** :
1. Recherche vol → SkyscannerFlightService
2. Recherche hôtel → BookingHotelService
3. Paiement → StripePaymentService

**Résultat** : 3/3 étapes complétées, 51.4% couverture

---

## Prochaines Étapes

- **Phase 3B** : Implémenter la composition intelligente utilisant les annotations LLM
- **Comparaison** : Mesurer quantitativement les différences (couverture, qualité, adaptation)
- **Évaluation** : Tester sur des scénarios complexes et variés
