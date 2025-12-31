import streamlit as st
import time
import zipfile
from io import BytesIO
from src.annotators.llm_annotator import LLMAnnotator

def render():
    st.header("📝 Annotation des services avec LLM")
    
    if not st.session_state.services:
        st.info("ℹ️ Veuillez d'abord importer des fichiers WSDL")
        return
    
    st.markdown('''
    **3 types d'annotations générées par le LLM:**
    1. 🔗 **Annotations d'interaction** : Interactions avec autres services, taux de succès, temps de réponse
    2. 🌍 **Annotations de contexte** : Dépendance localisation, temps, préférences utilisateur
    3. 🔒 **Annotations de politique** : Authentification, confidentialité, rate limits, coûts
    ''')
    
    # Stats
    non_annotated = [s for s in st.session_state.services if not s.is_annotated]
    annotated = [s for s in st.session_state.services if s.is_annotated]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Services total", len(st.session_state.services))
    col2.metric("À annoter", len(non_annotated))
    col3.metric("Annotés", len(annotated))
    
    st.divider()
    
    # Boutons d'action principaux
    col_action1, col_action2 = st.columns(2)
    
    with col_action1:
        if non_annotated:
            if st.button("🚀 Annoter tous les services", type="primary", use_container_width=True):
                annotate_all_services(non_annotated)
    
    with col_action2:
        if annotated:
            if st.button("📦 Télécharger tous les WSDL enrichis", type="secondary", use_container_width=True):
                download_all_enriched_wsdl(annotated)
    
    st.divider()
    
    # Liste des services avec boutons individuels
    st.subheader("Services")
    
    for service in st.session_state.services:
        with st.expander(
            f"{'✅' if service.is_annotated else '⏳'} {service.name}",
            expanded=not service.is_annotated 
        ):
            col1, col2 = st.columns([3, 2])
            
            with col1:
                st.write(f"**Fichier:** {service.filename}")
                st.write(f"**Fonctionnalités:** {', '.join(service.functionalities)}")
                st.write(f"**Opérations:** {', '.join(service.operations)}")

                if service.is_annotated and service.annotations:
                    st.success("✅ Service annoté et WSDL enrichi")

                    # Afficher les annotations
                    if st.checkbox(
                        "Afficher les annotations",
                        key=f"chk_ann_{service.id}"
                    ):
                        st.json(service.annotations)
                else:
                    st.info("Service non annoté")

            with col2:
                # Bouton annoter/re-annoter
                label = "🔄 Re-annoter" if service.is_annotated else "📝 Annoter"
                if st.button(label, key=f"ann_{service.id}", use_container_width=True):
                    annotate_single_service(service)
                
                # Bouton télécharger (uniquement si annoté)
                if service.is_annotated and service.enriched_wsdl:
                    st.download_button(
                        label="⬇️ Télécharger WSDL enrichi",
                        data=service.enriched_wsdl,
                        file_name=f"{service.name}_enriched.wsdl",
                        mime="application/xml",
                        key=f"dl_{service.id}",
                        use_container_width=True
                    )

def annotate_single_service(service):
    """Annote un seul service"""
    with st.spinner(f"Annotation de {service.name} avec LLM..."):
        annotator = LLMAnnotator(
            st.session_state.ollama_url,
            st.session_state.ollama_model
        )
        
        try:
            # Générer les annotations avec LLM
            annotations = annotator.annotate_service(service, st.session_state.services)
            service.annotations = annotations
            service.is_annotated = True
            
            # Enrichir le WSDL original
            if service.filename:
                # Simuler le contenu WSDL original pour l'enrichissement
                original_wsdl = f'''<?xml version="1.0"?>
<definitions name="{service.name}"
             targetNamespace="http://example.com/{service.name}"
             xmlns="http://schemas.xmlsoap.org/wsdl/"
             xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
             xmlns:tns="http://example.com/{service.name}">
  <!-- Original WSDL content -->
  <types/>
  <message name="Request"/>
  <message name="Response"/>
  <portType name="{service.name}PortType">
    {''.join(f'<operation name="{op}"/>' for op in service.operations)}
  </portType>
  <binding name="{service.name}Binding" type="tns:{service.name}PortType">
    <soap:binding transport="http://schemas.xmlsoap.org/soap/http"/>
  </binding>
  <service name="{service.name}Service">
    <port name="{service.name}Port" binding="tns:{service.name}Binding">
      <soap:address location="{service.endpoint}"/>
    </port>
  </service>
</definitions>'''
                service.enriched_wsdl = annotator.enrich_wsdl(original_wsdl, annotations)
            
            st.success(f"✅ {service.name} annoté avec succès!")
            time.sleep(1)
            st.rerun()
            
        except Exception as e:
            st.error(f"Erreur lors de l'annotation: {str(e)}")

def annotate_all_services(services):
    """Annote tous les services non annotés"""
    annotator = LLMAnnotator(
        st.session_state.ollama_url,
        st.session_state.ollama_model
    )
    
    # Vérifier disponibilité Ollama
    if annotator.is_available():
        st.info("🟢 Ollama connecté - Utilisation du LLM")
    else:
        st.warning("⚠️ Ollama non disponible - Génération d'annotations réalistes intelligentes")
    
    progress = st.progress(0)
    status = st.empty()
    
    for i, service in enumerate(services):
        status.text(f"Annotation de {service.name}... ({i+1}/{len(services)})")
        
        try:
            annotations = annotator.annotate_service(service, st.session_state.services)
            service.annotations = annotations
            service.is_annotated = True
            
            # Enrichir WSDL
            original_wsdl = f'''<?xml version="1.0"?>
<definitions name="{service.name}"
             targetNamespace="http://example.com/{service.name}"
             xmlns="http://schemas.xmlsoap.org/wsdl/"
             xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
             xmlns:tns="http://example.com/{service.name}">
  <!-- Original WSDL content -->
  <types/>
  <message name="Request"/>
  <message name="Response"/>
  <portType name="{service.name}PortType">
    {''.join(f'<operation name="{op}"/>' for op in service.operations)}
  </portType>
  <binding name="{service.name}Binding" type="tns:{service.name}PortType">
    <soap:binding transport="http://schemas.xmlsoap.org/soap/http"/>
  </binding>
  <service name="{service.name}Service">
    <port name="{service.name}Port" binding="tns:{service.name}Binding">
      <soap:address location="{service.endpoint}"/>
    </port>
  </service>
</definitions>'''
            service.enriched_wsdl = annotator.enrich_wsdl(original_wsdl, annotations)
            
        except Exception as e:
            st.error(f"Erreur avec {service.name}: {str(e)}")
        
        progress.progress((i + 1) / len(services))
    
    status.empty()
    progress.empty()
    
    st.success("✅ Tous les services ont été annotés!")
    time.sleep(2)
    st.rerun()

def download_all_enriched_wsdl(annotated_services):
    """Télécharge tous les WSDL enrichis dans un fichier ZIP"""
    # Créer un fichier ZIP en mémoire
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for service in annotated_services:
            if service.enriched_wsdl:
                filename = f"{service.name}_enriched.wsdl"
                zip_file.writestr(filename, service.enriched_wsdl)
    
    # Réinitialiser le pointeur du buffer
    zip_buffer.seek(0)
    
    # Créer le bouton de téléchargement
    st.download_button(
        label="📦 Cliquez ici pour télécharger le ZIP",
        data=zip_buffer.getvalue(),
        file_name="wsdl_enrichis.zip",
        mime="application/zip",
        type="primary",
        use_container_width=True
    )