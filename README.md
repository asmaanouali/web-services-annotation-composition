## Vue d'ensemble

Ce projet implémente un **système complet de composition de services web** qui :

- **Annote automatiquement** les services via LLM (Large Language Model)
- **Compose intelligemment** les workflows en fonction du contexte utilisateur
- **S'adapte automatiquement** aux échecs (self-configuration, self-adaptation, self-protection)
- **Compare 3 approches** : Classique vs Intelligente vs Hybride

### Problème résolu

**Problème** : Un service A a besoin d'une fonction X, mais plusieurs services la fournissent → lequel choisir ?

**Solution** : Sélection intelligente basée sur :
- Annotations sémantiques (générées par LLM)
- Contexte utilisateur (budget, localisation, priorités)
- Métriques de qualité (temps de réponse, taux de succès)
- Historique d'exécution (apprentissage)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   INTERFACE GRAPHIQUE (Streamlit)           │
│              Upload WSDL, Annotation, Composition            │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼──────┐    ┌─────────▼────────┐    ┌──────▼──────┐
│  ANNOTATION  │    │   COMPOSITION     │    │  EXECUTION  │
│   SYSTEM     │    │     SYSTEM        │    │  ADAPTATIVE │
│              │    │                   │    │             │
│ • Parser     │───▶│ • Classic Engine  │───▶│ • Retry     │
│ • Ollama     │    │ • Intelligent     │    │ • Fallback  │
│ • Generator  │    │ • Hybrid (LLM)    │    │ • Monitor   │
└──────────────┘    └───────────────────┘    └─────────────┘
```

### 3 Approches de composition

| Approche | Sélection | Mapping | Adaptation | Use Case |
|----------|-----------|---------|------------|----------|
| **Classique** | Règles fixes | Mappings prédéfinis | Aucune | Workflows standards |
| **Intelligente** | Scores LLM | Sémantique avancée | Dynamique | Contextes variés |
| **Hybride** | Mixte | Combiné | Dynamique | Applications premium |

---

## Installation

### Prérequis

- **Python 3.8+**
- **Ollama** (pour les annotations LLM)
- **Git**

### Étape 1 : Cloner le projet

```bash
git clone <votre-repo-url>
cd projet-stage
```

### Étape 2 : Créer un environnement virtuel

```bash
# Créer l'environnement
python -m venv venv

# Activer (Linux/Mac)
source venv/bin/activate

# Activer (Windows)
venv\Scripts\activate
```

### Étape 3 : Installer les dépendances

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Contenu de `requirements.txt` minimal** :
```txt
requests>=2.31.0
lxml>=4.9.0
streamlit>=1.28.0
plotly>=5.17.0
pandas>=2.0.0
```

### Étape 4 : Installer et configurer Ollama

#### Sur Linux
```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.2:3b
```

#### Sur Windows
1. Télécharger depuis [ollama.ai](https://ollama.ai)
2. Installer
3. Ouvrir un terminal et exécuter :
```bash
ollama pull llama3.2:3b
```

#### Sur macOS
```bash
brew install ollama
ollama pull llama3.2:3b
```

### Étape 5 : Lancer Ollama (en arrière-plan)

```bash
# Dans un terminal séparé
ollama serve
```

Laissez ce terminal ouvert pendant l'utilisation du système.

### Étape 6 : Vérifier l'installation

```bash
# Tester Ollama
curl http://localhost:11434/api/tags

# Tester Python
python --version

# Tester les imports
python -c "import streamlit, requests, lxml; print('OK')"
```

---

## Guide d'utilisation

### Option 1 : Interface Graphique (Recommandé)

```bash
streamlit run app_interface.py
```

L'interface s'ouvrira dans votre navigateur (`http://localhost:8501`)

**Fonctionnalités de l'interface** :
1. **Upload de fichiers WSDL** (vos propres services)
2. **Annotation automatique** (lancement en un clic)
3. **Composition** (choix de l'approche : Classique / Intelligente / Hybride)
4. **Visualisation des résultats**
5. **Comparaison des approches**

### Option 2 : Ligne de commande

#### Annotation

```bash
# Annoter un fichier WSDL
python annotation_system/annotation_generator.py \
    --wsdl services/wsdl/original/MonService.wsdl

# Annoter tous les WSDL d'un dossier
python annotation_system/batch_annotate.py \
    --input services/wsdl/original \
    --model llama3.2:3b
```

#### Composition Classique

```bash
python main_classic_composition.py
```

#### Composition Intelligente

```bash
python main_intelligent_composition.py
```

#### Démonstration complète (3 approches)

```bash
python demo_complete.py
```

---

## Modules du système

### 1. Système d'Annotation (`annotation_system/`)

**Objectif** : Enrichir les WSDL avec des métadonnées sémantiques

#### Composants
- `wsdl_parser.py` : Parse les fichiers WSDL
- `ollama_client.py` : Communication avec le LLM
- `annotation_generator.py` : Génère les 4 types d'annotations
- `batch_annotate.py` : Annotation en masse

#### 4 types d'annotations (basés sur le papier de référence)

```python
ServiceAnnotation
├── Functional      # Capacités, paramètres
├── Interaction     # Relations avec autres services
├── Context         # Contraintes géographiques, temporelles
└── Policy          # Sécurité, confidentialité, coûts
```

#### Exemple d'utilisation

```python
from annotation_system.annotation_generator import AnnotationGenerator

generator = AnnotationGenerator(ollama_model="llama3.2:3b")
annotation = generator.generate_annotation("mon_service.wsdl")
```

**Sortie** : Fichier JSON avec toutes les annotations

---

### 2. Composition Classique (`composition_system/classic_*`)

**Principe** : Règles hardcodées, sélection déterministe

#### Composants
- `classic_wsdl_parser.py` : Parser minimaliste
- `classic_service_selector.py` : Sélection par règles
- `classic_composition_engine.py` : Orchestration

#### Algorithme

```python
FOR each étape du workflow:
    1. Découvrir services de la catégorie
    2. Appliquer règles de priorité
    3. Mapper paramètres (exact match ou mappings prédéfinis)
    4. Retourner workflow complet
```

**Avantages** : Rapide (~7ms), simple, fiable  
**Inconvénients** : Rigide, pas d'adaptation au contexte

---

### 3. Composition Intelligente (`composition_system/intelligent_*`)

**Principe** : Sélection basée sur les annotations LLM + contexte utilisateur

#### Composants
- `intelligent_service_registry.py` : Gestion des annotations
- `intelligent_service_selector.py` : Scoring multi-critères
- `intelligent_parameter_mapper.py` : Mapping sémantique
- `intelligent_composition_engine.py` : Orchestration intelligente

#### Algorithme de scoring

```python
Score_total = w1×Score_fonctionnel + 
              w2×Score_qualité + 
              w3×Score_coût + 
              w4×Score_contexte

Poids adaptatifs selon :
- Budget serré → w3 = 0.4
- Mission critique → w2 = 0.4
```

**Avantages** : Adaptatif, contextuel, explicable  
**Inconvénients** : Plus lent (~628ms), nécessite annotations

---

### 4. Composition Hybride (`composition_system/hybrid_*`)

**Principe** : Combine services classiques + services LLM

#### Services LLM disponibles
- `IntelligentRecommendationService` : Recommande destinations, génère itinéraires
- `IntelligentTravelSummaryService` : Résume voyages, compare options

#### Workflows hybrides

```
enhanced_travel_booking:
  1. LLM: Analyse préférences utilisateur
  2. Classique: Recherche vols
  3. Hybride: Recherche hôtels + analyse LLM
  4. Classique: Paiement
  5. LLM: Génération résumé personnalisé
```

**Avantages** : Meilleur des deux mondes, UX premium  
**Inconvénients** : Plus complexe

---

### 5. Exécuteur Adaptatif (`composition_system/adaptive_executor.py`)

**Objectif** : Implémenter self-configuration, self-adaptation, self-protection

#### Capacités

```python
AdaptiveExecutor
├── Self-configuration
│   └── Ajustement automatique des paramètres manquants
├── Self-adaptation
│   ├── Retry avec backoff exponentiel
│   └── Basculement vers services alternatifs
└── Self-protection
    ├── Timeout automatique
    └── Fallback graceful (données mock)
```

#### Exemple d'adaptation

```
Étape 1: Service A
  ├─ Tentative 1: Échec
  ├─ Tentative 2: Échec
  ├─ Basculement vers Service B (alternative)
  └─ Tentative 1: Succès
```

---

### 6. Enrichissement des Annotations (`annotation_system/annotation_enricher.py`)

**Objectif** : Améliorer les annotations avec l'historique d'exécution

#### Processus

```python
Exécution du workflow
    ↓
Feedback (temps, succès, erreurs)
    ↓
Mise à jour des annotations
    ├─ Métriques de qualité (temps réel)
    ├─ Taux de succès
    └─ Paramètres fréquemment utilisés
    ↓
Amélioration continue
```

---

## Interface Graphique

### Fonctionnalités

#### 1. Upload de WSDL
- Glisser-déposer ou sélection
- Support multi-fichiers
- Validation automatique

#### 2. Annotation
- Modèle LLM configurable
- Lancement batch ou individuel
- Progression en temps réel

#### 3. Composition
- Choix de l'approche
- Paramètres du scénario
- Contexte utilisateur

#### 4. Visualisation
- Workflow généré (graphique)
- Statistiques détaillées
- Comparaison des approches

#### 5. Résultats
- Export JSON/PDF
- Historique des compositions
- Métriques de performance

### Captures d'écran

*(Voir `docs/screenshots/`)*

---

## Résultats et évaluation

### Métriques de comparaison

| Métrique | Classique | Intelligente | Hybride |
|----------|-----------|--------------|---------|
| **Temps d'exécution** | 7ms | 628ms | ~300ms |
| **Couverture paramètres** | 51% | 11% | Variable |
| **Adaptations** | 0 | 5.8/workflow | Selon étape |
| **Score qualité** | N/A | 0.775/1.0 | 0.775/1.0 |
| **Complexité** | Faible | Moyenne | Élevée |

### Cas d'usage recommandés

- **Classique** : Workflows standards, performance critique
- **Intelligente** : Forte hétérogénéité, qualité critique
- **Hybride** : Applications grand public, expérience premium

### Évaluation complète

```bash
python evaluation_suite.py
```

Génère un rapport dans `evaluation_results/`

---

## Structure du projet

```
projet-stage/
├── annotation_system/          # Annotation automatique
│   ├── wsdl_parser.py
│   ├── ollama_client.py
│   ├── annotation_generator.py
│   ├── batch_annotate.py
│   └── annotation_enricher.py
│
├── composition_system/          # Composition de services
│   ├── classic_*.py            # Approche classique
│   ├── intelligent_*.py        # Approche intelligente
│   ├── hybrid_*.py             # Approche hybride
│   ├── adaptive_executor.py    # Exécution adaptative
│   └── results/                # Résultats de composition
│
├── models/
│   └── annotation_model.py     # Modèle de données
│
├── services/
│   ├── wsdl/
│   │   ├── original/          # WSDL bruts
│   │   └── annotated/         # Annotations JSON
│   └── implementations/
│       ├── llm_recommendation_service.py
│       └── llm_travel_summary_service.py
│
├── evaluation_results/          # Rapports d'évaluation
│
├── app_interface.py            # Interface graphique Streamlit
├── demo_complete.py            # Démonstration complète
├── requirements.txt            # Dépendances Python
└── README.md                   # Ce fichier
```

---

## Documentation détaillée


**4 types d'annotations** :

#### 1. Annotation Fonctionnelle
```json
{
  "service_category": "search",
  "capabilities": ["search_flights", "multi_city"],
  "special_features": {
    "supports_multi_currency": true
  }
}
```

#### 2. Annotation d'Interaction
```json
{
  "requires_services": [],
  "provides_for_services": ["booking", "payment"],
  "quality_metrics": {
    "response_time_ms": 1200,
    "success_rate": 0.95
  }
}
```

#### 3. Annotation de Contexte
```json
{
  "geographic_coverage": ["GLOBAL"],
  "location_aware": true,
  "temporal_constraints": ["24/7_available"]
}
```

#### 4. Annotation de Politique
```json
{
  "usage_policy": {
    "rate_limit": 1000,
    "cost_per_request": 0.01
  },
  "compliance_standards": ["GDPR", "PCI-DSS"]
}
```
