# Stage - Annotation Sémantique de Services SOAP

## Objectif
Enrichir automatiquement des fichiers WSDL avec des annotations sémantiques en utilisant un LLM local (Ollama).

## Architecture
- **Input** : Fichier WSDL décrivant un service SOAP
- **Traitement** : Analyse par LLM pour extraire la sémantique
- **Output** : WSDL enrichi avec annotations

## Installation

### Prérequis
```bash
pip install -r requirements.txt
ollama pull llama3.2:3b
```

### Lancement
```bash
python app.py
```

## Endpoints API
- `GET /` - Page d'accueil
- `POST /annotate` - Annoter un fichier WSDL
- `GET /health` - Vérifier le statut du système

## Semaine 1 - Setup
- [x] Installation environnement
- [x] Structure du projet
- [ ] Parser WSDL
- [ ] Intégration LLM
- [ ] Génération annotations