# Stage - Annotation Sémantique de Services SOAP

## 📋 Description

Ce projet permet d'enrichir automatiquement des fichiers WSDL (Web Services Description Language) avec des annotations sémantiques en utilisant un modèle de langage local (LLM). L'objectif est de faciliter la découverte, la compréhension et la composition intelligente de services web SOAP.

## 🎯 Objectifs

- **Parser** des fichiers WSDL pour extraire les informations structurées
- **Générer** des annotations sémantiques via un LLM (Ollama)
- **Enrichir** le WSDL original avec ces annotations
- Fournir une **API REST** pour l'intégration dans d'autres systèmes

## 🏗️ Architecture
```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐      ┌──────────────┐
│ WSDL        │─────▶│ WSDL Parser  │─────▶│ LLM         │─────▶│ WSDL         │
│ Original    │      │              │      │ Annotator   │      │ Enricher     │
└─────────────┘      └──────────────┘      └─────────────┘      └──────────────┘
                              │                    │                     │
                              ▼                    ▼                     ▼
                     Service Info (dict)   Annotations (JSON)   WSDL Enrichi
```

### Modules principaux

1. **`services/wsdl_parser.py`** : Parse et extrait les informations d'un fichier WSDL
2. **`services/llm_annotator.py`** : Génère des annotations sémantiques via Ollama
3. **`services/wsdl_enricher.py`** : Enrichit le WSDL avec les annotations générées

## 🚀 Installation

### Prérequis

- Python 3.10 ou supérieur
- Ollama installé (pour le LLM local)

### Étapes d'installation

#### 1. Cloner ou télécharger le projet
```bash
git clone <votre-repo>
cd stage-intelligent-services
```

#### 2. Créer un environnement virtuel (Windows)
```cmd
python -m venv venv
venv\Scripts\activate
```

#### 3. Installer les dépendances Python
```cmd
pip install -r requirements.txt
```

#### 4. Installer Ollama

**Windows :**
- Télécharger depuis https://ollama.com/download
- Installer et lancer l'application
- Ollama se lancera automatiquement en arrière-plan

**Linux/Mac :**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

#### 5. Télécharger le modèle LLM
```cmd
ollama pull llama3.2:3b
```

## 📂 Structure du projet
```
stage-intelligent-services/
├── venv/                           # Environnement virtuel Python
├── data/
│   ├── input/                      # Fichiers WSDL à analyser
│   │   └── exemple_service.wsdl
│   └── output/                     # Résultats générés
│       ├── exemple_service_enriched.wsdl
│       ├── generated_annotations.json
│       └── complete_analysis.json
├── services/
│   ├── __init__.py
│   ├── wsdl_parser.py             # Parser WSDL
│   ├── llm_annotator.py           # Annotateur via LLM
│   └── wsdl_enricher.py           # Enrichisseur WSDL
├── tests/
│   └── test_demo.py               # Script de démonstration
├── app.py                          # Application Flask (API REST)
├── config.py                       # Configuration du projet
├── requirements.txt                # Dépendances Python
├── .gitignore
└── README.md
```

## 🎮 Utilisation

### Option 1 : Script de démonstration (Recommandé)
```cmd
# Activer l'environnement virtuel
venv\Scripts\activate

# Lancer la démo complète
python tests/test_demo.py
```

**Ce script exécute :**
1. ✅ Parsing du WSDL
2. ✅ Génération des annotations via LLM
3. ✅ Enrichissement du WSDL
4. ✅ Sauvegarde de tous les résultats

### Option 2 : API REST

#### Démarrer le serveur
```cmd
python app.py
```

Le serveur démarre sur `http://127.0.0.1:5000`

#### Endpoints disponibles

##### GET `/`
Page d'accueil avec les informations du système

##### GET `/health`
Vérifier l'état du système (Flask, Ollama, dossiers)

**Exemple de réponse :**
```json
{
  "flask": "OK",
  "ollama": "OK",
  "available_models": ["llama3.2:3b"],
  "directories": {
    "input": true,
    "output": true
  }
}
```

##### GET `/parse-example`
Parser le fichier WSDL exemple

**Réponse :** Informations structurées du service en JSON

##### POST `/annotate`
Annoter et enrichir un fichier WSDL

**Body (JSON) :**
```json
{
  "wsdl_filename": "exemple_service.wsdl"
}
```

**Réponse :**
```json
{
  "status": "success",
  "service_name": "WeatherService",
  "annotations": {
    "domain": "weather",
    "description": "Service de prévisions météorologiques...",
    "keywords": ["météo", "température", "climat"],
    "use_cases": [...],
    "operations": [...]
  },
  "files": {
    "enriched_wsdl": "path/to/enriched.wsdl",
    "annotations_json": "path/to/annotations.json"
  }
}
```

## 🧪 Tests et validation

### Vérifier que tout fonctionne
```cmd
# 1. Vérifier l'état du système
python app.py
# Puis visiter http://127.0.0.1:5000/health

# 2. Tester le parsing
curl http://127.0.0.1:5000/parse-example

# 3. Tester l'annotation complète
curl -X POST http://127.0.0.1:5000/annotate \
  -H "Content-Type: application/json" \
  -d "{\"wsdl_filename\": \"exemple_service.wsdl\"}"
```

## 📊 Exemple de résultat

### WSDL Original
```xml
<service name="WeatherService">
  <port name="WeatherPort" binding="tns:WeatherBinding">
    <soap:address location="http://example.com/weather"/>
  </port>
</service>
```

### WSDL Enrichi
```xml
<service name="WeatherService" 
         semantic:domain="weather" 
         semantic:keywords="météo,température,climat">
  <documentation>
Service Annotations (Generated on 2025-01-XX)

Domain: weather
Description: Service de prévisions météorologiques...
Keywords: météo, température, climat, prévisions

Use Cases:
- Applications mobiles de météo
- Systèmes de gestion agricole
- Planification d'événements extérieurs
  </documentation>
  <port name="WeatherPort" binding="tns:WeatherBinding">
    <soap:address location="http://example.com/weather"/>
  </port>
</service>
```

## ⚙️ Configuration

Le fichier `config.py` contient les paramètres principaux :
```python
class Config:
    # Dossiers
    INPUT_DIR = "data/input"
    OUTPUT_DIR = "data/output"
    
    # Configuration Ollama
    OLLAMA_BASE_URL = "http://localhost:11434"
    OLLAMA_MODEL = "llama3.2:3b"  # Modèle LLM utilisé
    
    # Configuration Flask
    FLASK_PORT = 5000
```

## 🐛 Dépannage

### Problème : Ollama ne répond pas

**Solution :**
- Vérifier qu'Ollama est lancé (icône dans la barre des tâches Windows)
- Tester : `curl http://localhost:11434/api/tags`
- Relancer Ollama si nécessaire

### Problème : Timeout lors de la génération d'annotations

**Solution 1 :** Utiliser un modèle plus léger
```cmd
ollama pull llama3.2:1b
```
Puis modifier `config.py` : `OLLAMA_MODEL = "llama3.2:1b"`

**Solution 2 :** Le timeout est déjà augmenté à 120 secondes dans le code

### Problème : Erreur de parsing XML

**Solution :** Vérifier que le fichier WSDL est bien formé (pas de contenu après `</definitions>`)

## 📚 Technologies utilisées

- **Python 3.13** : Langage principal
- **Flask 3.0** : Framework web pour l'API REST
- **lxml 5.1** : Parsing et manipulation XML
- **Ollama** : Plateforme LLM locale
- **Llama 3.2** : Modèle de langage pour les annotations
- **Requests 2.31** : Appels HTTP vers Ollama
