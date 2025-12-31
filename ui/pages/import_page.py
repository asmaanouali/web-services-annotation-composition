import streamlit as st
import uuid
from src.models.service import Service
from src.parsers.wsdl_parser import WSDLParser

def render():
    st.header("📥 Import des fichiers WSDL")
    
    st.info("""
    📋 **Détection intelligente en 2 étapes avec LLM**
    
    1. 🔍 **Détection libre** : Le LLM identifie toutes les fonctionnalités du service
    2. 🔄 **Normalisation** : Regroupement en catégories génériques
    """)
    
    # Vérifier la disponibilité d'Ollama
    parser = WSDLParser(
        st.session_state.get('ollama_url', 'http://localhost:11434'),
        st.session_state.get('ollama_model', 'llama2')
    )
    
    ollama_status = parser.is_ollama_available()
    
    if ollama_status:
        st.success("🟢 Ollama connecté")
    else:
        st.warning("⚠️ Ollama non disponible - Détection et normalisation de fallback seront utilisées")
    
    uploaded_files = st.file_uploader(
        "Sélectionnez vos fichiers WSDL",
        type=['wsdl', 'xml'],
        accept_multiple_files=True,
        key="wsdl_uploader"
    )
    
    if uploaded_files:
        if st.button("🔍 Analyser les fichiers", type="primary", use_container_width=True):
            with st.spinner("Analyse des fichiers WSDL..."):
                progress = st.progress(0)
                status = st.empty()
                
                newly_added = 0
                for i, file in enumerate(uploaded_files):
                    status.text(f"📄 {file.name} - Détection + Normalisation LLM...")
                    
                    try:
                        content = file.read().decode('utf-8')
                        
                        # Parser avec LLM (détection + normalisation)
                        data = WSDLParser.parse(
                            content, 
                            file.name,
                            st.session_state.get('ollama_url', 'http://localhost:11434'),
                            st.session_state.get('ollama_model', 'llama2')
                        )
                        
                        if data:
                            # Vérifier si pas déjà importé
                            if not any(s.name == data['name'] for s in st.session_state.services):
                                service = Service(
                                    id=str(uuid.uuid4()),
                                    **data
                                )
                                st.session_state.services.append(service)
                                newly_added += 1
                                
                                # Afficher les catégories normalisées
                                status.text(f"✅ {file.name}: {', '.join(data['functionalities'])}")
                    except Exception as e:
                        st.error(f"Erreur avec {file.name}: {str(e)}")
                    
                    progress.progress((i + 1) / len(uploaded_files))
                
                status.empty()
                progress.empty()
                
                if newly_added > 0:
                    st.success(f"✅ {newly_added} service(s) analysé(s) et catégorisé(s) avec LLM!")
                    st.balloons()
                else:
                    st.info("Tous les services sont déjà importés")
                
                st.rerun()
    
    # Liste des services
    if st.session_state.services:
        st.divider()
        st.subheader(f"📋 Services importés ({len(st.session_state.services)})")
        
        for service in st.session_state.services:
            with st.expander(f"{'✅' if service.is_annotated else '⏳'} {service.name}"):
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    st.write(f"**Fichier:** {service.filename}")
                    st.write(f"**Endpoint:** {service.endpoint}")
                    
                    # Catégories normalisées
                    st.write("**🔄 Catégories normalisées:**")
                    for func in service.functionalities:
                        st.markdown(f"- `{func}`")
                    
                    st.write(f"**Opérations ({len(service.operations)}):** {', '.join(service.operations)}")
                    
                    if service.is_annotated:
                        st.success("✅ Service annoté et enrichi")
                    else:
                        st.warning("⏳ Service non annoté")
                
                with col2:
                    if st.button("🗑️ Supprimer", key=f"del_{service.id}"):
                        st.session_state.services = [s for s in st.session_state.services if s.id != service.id]
                        st.rerun()
    else:
        st.info("👆 Uploadez des fichiers WSDL pour commencer")
    
