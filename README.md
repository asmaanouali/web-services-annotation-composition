# Système Intelligent de Composition de Services Web

## Installation
```bash
cd web_service_composer
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sur Windows
pip install -r requirements.txt
```

## Lancement
```bash
streamlit run ui/app.py
```

## Utilisation
1. **Import WSDL** : Uploadez vos fichiers WSDL → Analyse automatique des fonctionnalités
2. **Annotation** : Annotez avec LLM (Ollama) pour enrichir les WSDL
3. **Composition** : 
   - Choisissez un WSDL source
   - Sélectionnez la fonction nécessaire
   - Le système trouve tous les WSDL qui la fournissent
   - Composition classique (manuelle) ou intelligente (automatique avec scoring)

Projet CERIST - Stage 2025
