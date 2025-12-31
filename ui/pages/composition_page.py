import streamlit as st
import uuid
from src.models.composition import CompositionStep
from src.composers.classic_composer import ClassicComposer
from src.composers.intelligent_composer import IntelligentComposer

def render():
    st.header("🔀 Composition de services")
    
    if not st.session_state.services:
        st.info("ℹ️ Importez des services WSDL d'abord")
        return
    
    st.markdown('''
    **Principe:**
    1. Choisissez un service WSDL source
    2. Sélectionnez la fonction dont vous avez besoin
    3. Le système trouve tous les services qui fournissent cette fonction
    4. **Classique**: Sélection automatique traditionnelle (ordre alphabétique, disponibilité)
    5. **Intelligent**: Sélection basée sur l'analyse LLM des annotations (scoring, contexte, historique)
    ''')
    
    col1, col2 = st.columns([2, 3])
    
    with col1:
        st.subheader("➕ Ajouter une étape")
        
        # 1. Choisir le service source
        service_names = [s.name for s in st.session_state.services]
        selected_source = st.selectbox(
            "Service WSDL source",
            service_names,
            key="source_service"
        )
        
        # 2. Obtenir toutes les fonctions disponibles
        all_functions = set()
        for service in st.session_state.services:
            all_functions.update(service.functionalities)
        
        selected_function = st.selectbox(
            "Fonction nécessaire",
            sorted(all_functions),
            key="needed_function"
        )
        
        # 3. Trouver les services qui fournissent cette fonction
        matching_services = [
            s for s in st.session_state.services 
            if selected_function in s.functionalities
        ]
        
        if matching_services:
            st.success(f"✅ {len(matching_services)} service(s) trouvé(s) fournissant '{selected_function}'")
            
            for svc in matching_services:
                status = "✅ Annoté" if svc.is_annotated else "⏳ Non annoté"
                st.write(f"- **{svc.name}** ({status})")
            
            if st.button("➕ Ajouter cette étape", type="primary", use_container_width=True):
                # Créer l'étape
                step = {
                    'step_id': str(uuid.uuid4()),
                    'step_number': len(st.session_state.composition_steps) + 1,
                    'source_service': selected_source,
                    'needed_function': selected_function,
                    'available_services': [
                        {
                            'service_name': svc.name,
                            'operations': svc.operations,
                            'is_annotated': svc.is_annotated
                        }
                        for svc in matching_services
                    ],
                    'selected_service': None,
                    'selected_operation': None
                }
                st.session_state.composition_steps.append(step)
                st.success("✅ Étape ajoutée!")
                st.rerun()
        else:
            st.warning(f"Aucun service ne fournit la fonction '{selected_function}'")
    
    with col2:
        st.subheader("📜 Script de composition")
        
        if not st.session_state.composition_steps:
            st.info("Aucune étape définie. Ajoutez des étapes depuis la colonne de gauche.")
        else:
            # Afficher chaque étape
            for i, step in enumerate(st.session_state.composition_steps):
                with st.expander(f"Étape {step['step_number']}: {step['needed_function']}", expanded=True):
                    st.write(f"**Source:** {step['source_service']}")
                    st.write(f"**Fonction nécessaire:** {step['needed_function']}")
                    st.write(f"**Services disponibles:** {len(step['available_services'])}")
                    
                    # Afficher les services disponibles
                    col_a, col_b = st.columns(2)
                    
                    with col_a:
                        st.markdown("**Services candidats:**")
                        for svc_info in step['available_services']:
                            icon = "✅" if svc_info['is_annotated'] else "⏳"
                            st.write(f"{icon} {svc_info['service_name']}")
                    
                    with col_b:
                        st.markdown("**Sélection:**")
                        st.write("🔹 **Classique**: 1er alphabétique")
                        st.write("⚡ **Intelligent**: Meilleur score")
                    
                    if st.button("🗑️ Supprimer", key=f"del_{step['step_id']}"):
                        st.session_state.composition_steps = [
                            s for s in st.session_state.composition_steps 
                            if s['step_id'] != step['step_id']
                        ]
                        # Réordonner
                        for j, s in enumerate(st.session_state.composition_steps):
                            s['step_number'] = j + 1
                        st.rerun()
    
    # Actions
    if st.session_state.composition_steps:
        st.divider()
        
        st.markdown("""
        ### 🎯 Méthodes de composition
        
        | Méthode | Critères de sélection | Utilise annotations |
        |---------|----------------------|---------------------|
        | **Classique** | Ordre alphabétique, disponibilité | ❌ Non |
        | **Intelligente** | Score LLM, historique, contexte, QoS | ✅ Oui |
        """)
        
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            if st.button("🧹 Effacer tout", use_container_width=True):
                st.session_state.composition_steps = []
                st.rerun()
        
        with col_b:
            if st.button("📘 Composition Classique", type="secondary", use_container_width=True):
                execute_classic_composition()
        
        with col_c:
            # Vérifier si tous les services disponibles sont annotés
            all_annotated = check_if_all_services_annotated()
            
            if all_annotated:
                if st.button("⚡ Composition Intelligente", type="primary", use_container_width=True):
                    execute_intelligent_composition()
            else:
                st.button(
                    "⚡ Intelligent",
                    disabled=True,
                    use_container_width=True,
                    help="Au moins un service par étape doit être annoté pour la composition intelligente"
                )

def check_if_all_services_annotated():
    """Vérifie si au moins un service par étape est annoté"""
    for step in st.session_state.composition_steps:
        has_annotated = any(
            svc['is_annotated'] for svc in step['available_services']
        )
        if not has_annotated:
            return False
    return True

def execute_classic_composition():
    """
    Exécute la composition classique traditionnelle
    Sélection automatique basée sur l'ordre alphabétique
    """
    with st.spinner("Exécution de la composition classique (sélection alphabétique)..."):
        composer = ClassicComposer(st.session_state.services)
        
        results = []
        for step_data in st.session_state.composition_steps:
            step = CompositionStep(**step_data)
            result = composer.execute_step(step)
            
            if result:
                results.append(result)
        
        st.session_state.composition_results = {
            'classic': results,
            'intelligent': None
        }
        
        st.success("✅ Composition classique terminée!")
        st.info("ℹ️ Sélection basée sur: ordre alphabétique + première opération disponible")
        import time
        time.sleep(1)

def execute_intelligent_composition():
    """
    Exécute les DEUX compositions et compare
    """
    with st.spinner("Exécution des deux méthodes de composition..."):
        # 1. CLASSIQUE
        classic_composer = ClassicComposer(st.session_state.services)
        classic_results = []
        for step_data in st.session_state.composition_steps:
            step = CompositionStep(**step_data)
            result = classic_composer.execute_step(step)
            if result:
                classic_results.append(result)
        
        # 2. INTELLIGENT
        intelligent_composer = IntelligentComposer(st.session_state.services)
        intelligent_results = []
        previous_services = []
        
        for step_data in st.session_state.composition_steps:
            step = CompositionStep(**step_data)
            result = intelligent_composer.execute_step(step, previous_services)
            
            if result:
                intelligent_results.append(result)
                previous_services.append(result['selected_service'])
        
        st.session_state.composition_results = {
            'classic': classic_results,
            'intelligent': intelligent_results
        }
        
        st.success("✅ Compositions terminées!")
        st.info("💡 Consultez l'onglet 'Résultats' pour comparer les deux méthodes")
        import time
        time.sleep(1)