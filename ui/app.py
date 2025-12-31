import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.pages import import_page, annotation_page, composition_page, results_page

st.set_page_config(
    page_title="Web Service Composer",
    page_icon="🔗",
    layout="wide"
)

# Session state
if 'services' not in st.session_state:
    st.session_state.services = []
if 'composition_steps' not in st.session_state:
    st.session_state.composition_steps = []
if 'composition_results' not in st.session_state:
    st.session_state.composition_results = None

st.title("🔗 Système Intelligent de Composition de Services Web")
st.markdown("**Annotation automatique avec LLM et composition intelligente**")

with st.sidebar:
    st.header("📊 Statistiques")
    st.metric("Services importés", len(st.session_state.services))
    annotated = sum(1 for s in st.session_state.services if s.is_annotated)
    st.metric("Services annotés", f"{annotated}/{len(st.session_state.services)}")
    st.metric("Étapes composition", len(st.session_state.composition_steps))
    
    st.divider()
    
    st.header("⚙️ Configuration Ollama")
    ollama_url = st.text_input("URL", "http://localhost:11434", key="ollama_url_sidebar")
    ollama_model = st.text_input("Modèle", "llama2", key="ollama_model_sidebar")
    
    st.session_state.ollama_url = ollama_url
    st.session_state.ollama_model = ollama_model
    
    st.divider()
    
    if st.button("🗑️ Tout effacer", use_container_width=True):
        st.session_state.services = []
        st.session_state.composition_steps = []
        st.session_state.composition_results = None
        st.rerun()

tab1, tab2, tab3, tab4 = st.tabs([
    "📥 Import WSDL",
    "📝 Annotation",
    "🔀 Composition",
    "📊 Résultats"
])

with tab1:
    import_page.render()

with tab2:
    annotation_page.render()

with tab3:
    composition_page.render()

with tab4:
    results_page.render()

st.divider()
st.markdown("<p style='text-align: center; color: gray;'>Système de Composition Intelligente - CERIST 2025</p>", unsafe_allow_html=True)
