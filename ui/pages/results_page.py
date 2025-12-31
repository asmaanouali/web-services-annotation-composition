import streamlit as st
import pandas as pd
import json
import plotly.graph_objects as go
import plotly.express as px
import yaml
from pathlib import Path

def load_scoring_weights():
    """Charge les poids de scoring depuis config.yaml"""
    config_path = Path(__file__).parent.parent.parent / 'config.yaml'
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
            return config.get('scoring', {})
    return {
        'interaction_weight': 0.3,
        'success_rate_weight': 0.3,
        'response_time_weight': 0.2,
        'context_weight': 0.2
    }

def calculate_score_breakdown(annotations, operation, previous_services, weights):
    """
    Calcule le détail du score pour affichage
    Réplique la logique de IntelligentScorer
    """
    breakdown = {
        'interaction_score': 0,
        'success_rate_score': 0,
        'response_time_score': 0,
        'context_score': 0,
        'bonus': 0,
        'penalty': 0,
        'total': 0,
        'details': {}
    }
    
    # Trouver l'annotation d'interaction
    interaction_ann = next(
        (ann for ann in annotations.get('interaction_annotations', []) 
         if ann['operation'] == operation),
        None
    )
    
    if interaction_ann:
        # 1. Score d'interaction (30%)
        num_interactions = interaction_ann['number_of_interactions']
        interaction_normalized = min(num_interactions / 500, 1.0)
        interaction_score = interaction_normalized * weights['interaction_weight'] * 100
        breakdown['interaction_score'] = interaction_score
        breakdown['details']['num_interactions'] = num_interactions
        breakdown['details']['interaction_normalized'] = round(interaction_normalized, 3)
        
        # Bonus pour interactions avec services précédents
        bonus_interactions = 0
        for prev_svc in previous_services:
            if prev_svc in interaction_ann.get('interacts_with_services', []):
                bonus_interactions += 5
        breakdown['bonus'] += bonus_interactions
        breakdown['details']['bonus_previous_services'] = bonus_interactions
        
        # 2. Score de taux de succès (30%)
        success_rate = interaction_ann['success_rate']
        success_score = success_rate * weights['success_rate_weight'] * 100
        breakdown['success_rate_score'] = success_score
        breakdown['details']['success_rate'] = success_rate
        
        # 3. Score de temps de réponse (20%)
        response_time = interaction_ann['avg_response_time_ms']
        time_normalized = max(0, (500 - response_time) / 500)
        time_score = time_normalized * weights['response_time_weight'] * 100
        breakdown['response_time_score'] = time_score
        breakdown['details']['response_time_ms'] = response_time
        breakdown['details']['time_normalized'] = round(time_normalized, 3)
    
    # 4. Score de contexte (20%)
    context_ann = annotations.get('context_annotations', {})
    context_points = 0
    context_details = {}
    if context_ann.get('location_dependent'): 
        context_points += 5
        context_details['location_dependent'] = True
    if context_ann.get('time_sensitive'): 
        context_points += 5
        context_details['time_sensitive'] = True
    if context_ann.get('user_preference_based'): 
        context_points += 5
        context_details['user_preference_based'] = True
    if context_ann.get('requires_session'): 
        context_points += 5
        context_details['requires_session'] = True
    
    context_score = (context_points / 20) * weights['context_weight'] * 100
    breakdown['context_score'] = context_score
    breakdown['details']['context_points'] = context_points
    breakdown['details']['context_features'] = context_details
    
    # Pénalité pour coût élevé
    policy_ann = annotations.get('policy_annotations', {})
    if policy_ann.get('usage_cost') == 'HIGH':
        breakdown['penalty'] = -5
        breakdown['details']['high_cost_penalty'] = True
    
    # Total
    total = (breakdown['interaction_score'] + 
             breakdown['success_rate_score'] + 
             breakdown['response_time_score'] + 
             breakdown['context_score'] + 
             breakdown['bonus'] + 
             breakdown['penalty'])
    
    breakdown['total'] = min(round(total, 2), 100.0)
    
    return breakdown

def render():
    st.header("📊 Résultats de la composition")

    if not st.session_state.get('composition_results'):
        st.info("ℹ️ Aucune composition exécutée pour le moment")
        return

    results = st.session_state.composition_results
    weights = load_scoring_weights()

    tab1, tab2, tab3, tab4 = st.tabs([
        "📘 Composition Classique",
        "⚡ Composition Intelligente",
        "🎯 Détail du Scoring",
        "📈 Comparaison"
    ])

    # ====================================================================
    # COMPOSITION CLASSIQUE
    # ====================================================================
    with tab1:
        st.subheader("📘 Résultats – Composition Classique (Traditionnelle)")
        
        st.info("""
        **Méthode traditionnelle:**
        - ✅ Sélection automatique par ordre alphabétique
        - ✅ Première opération disponible
        - ❌ N'utilise PAS les annotations sémantiques
        - ❌ Ne considère PAS l'historique d'interactions
        - ❌ Ne considère PAS les métriques de performance
        """)

        classic_results = results.get("classic")
        if not classic_results:
            st.warning("Aucune donnée disponible")
        else:
            df_classic = pd.DataFrame(classic_results)
            
            display_cols = ['step', 'needed_function', 'selected_service', 
                          'selected_operation', 'execution_time']
            if 'selection_criteria' in df_classic.columns:
                display_cols.append('selection_criteria')
            
            st.dataframe(df_classic[display_cols], use_container_width=True)

            total_time = df_classic["execution_time"].sum()
            avg_time = df_classic["execution_time"].mean()
            
            col1, col2 = st.columns(2)
            col1.metric("⏱️ Temps total d'exécution (ms)", int(total_time))
            col2.metric("📊 Temps moyen par étape (ms)", int(avg_time))

    # ====================================================================
    # COMPOSITION INTELLIGENTE
    # ====================================================================
    with tab2:
        st.subheader("⚡ Résultats – Composition Intelligente (Basée sur LLM)")
        
        st.success("""
        **Méthode intelligente:**
        - ✅ Sélection basée sur le scoring LLM
        - ✅ Analyse des annotations d'interaction (historique)
        - ✅ Considère le taux de succès et temps de réponse
        - ✅ Prend en compte le contexte (localisation, session, etc.)
        - ✅ Applique les politiques (auth, privacy, coût)
        """)

        intelligent_results = results.get("intelligent")
        if not intelligent_results:
            st.warning("Aucune donnée disponible")
        else:
            df_intel = pd.DataFrame(intelligent_results)
            
            display_cols = ['step', 'needed_function', 'selected_service', 
                          'selected_operation', 'score', 'execution_time']
            st.dataframe(df_intel[display_cols], use_container_width=True)

            total_time = df_intel["execution_time"].sum()
            avg_score = df_intel["score"].mean()
            avg_time = df_intel["execution_time"].mean()

            col1, col2, col3 = st.columns(3)
            col1.metric("⏱️ Temps total (ms)", int(total_time))
            col2.metric("🎯 Score moyen", round(avg_score, 2))
            col3.metric("📊 Temps moyen (ms)", int(avg_time))

            with st.expander("🔍 Détails des annotations utilisées"):
                for _, row in df_intel.iterrows():
                    st.markdown(f"### Étape {row['step']}: {row['needed_function']}")
                    st.markdown(f"**Service sélectionné:** {row['selected_service']} - {row['selected_operation']}")
                    st.markdown(f"**Score calculé:** {row['score']}/100")
                    
                    if row.get("annotations_used"):
                        anns = row["annotations_used"]
                        
                        col_a, col_b = st.columns(2)
                        
                        with col_a:
                            st.markdown("**📊 Annotations d'interaction:**")
                            for ia in anns.get('interaction_annotations', []):
                                if ia['operation'] == row['selected_operation']:
                                    st.json(ia)
                            
                            st.markdown("**🌍 Annotations de contexte:**")
                            st.json(anns.get('context_annotations', {}))
                        
                        with col_b:
                            st.markdown("**🔒 Annotations de politique:**")
                            st.json(anns.get('policy_annotations', {}))
                    
                    st.divider()

    # ====================================================================
    # DÉTAIL DU SCORING - NOUVEAU TAB
    # ====================================================================
    with tab3:
        st.subheader("🎯 Comment les scores sont calculés")
        
        intelligent_results = results.get("intelligent")
        if not intelligent_results:
            st.warning("Exécutez d'abord une composition intelligente")
            return
        
        # Afficher la formule de scoring
        st.markdown("### 📐 Formule de Scoring")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown(f"""
            **Score Total = Score Interaction + Score Succès + Score Temps + Score Contexte + Bonus - Pénalités**
            
            #### Composantes du score :
            
            1. **Score Interaction** ({weights['interaction_weight']*100}% du total)
               - Basé sur l'historique d'utilisation (0-500 interactions)
               - Formule : `min(nombre_interactions / 500, 1.0) × {weights['interaction_weight']} × 100`
            
            2. **Score Taux de Succès** ({weights['success_rate_weight']*100}% du total)
               - Basé sur le taux de succès historique (0.0-1.0)
               - Formule : `taux_succès × {weights['success_rate_weight']} × 100`
            
            3. **Score Temps de Réponse** ({weights['response_time_weight']*100}% du total)
               - Meilleur score pour temps < 200ms, décroît jusqu'à 500ms
               - Formule : `max(0, (500 - temps_ms) / 500) × {weights['response_time_weight']} × 100`
            
            4. **Score Contexte** ({weights['context_weight']*100}% du total)
               - +5 points par feature contextuelle activée (max 20 points)
               - Features : location, time, user_preference, session
               - Formule : `(points_contexte / 20) × {weights['context_weight']} × 100`
            
            5. **Bonus**
               - +5 points par service précédent avec lequel il a déjà interagi
            
            6. **Pénalités**
               - -5 points si coût d'usage = HIGH
            """)
        
        with col2:
            st.markdown("#### ⚙️ Poids configurés")
            st.metric("Interaction", f"{weights['interaction_weight']*100}%")
            st.metric("Succès", f"{weights['success_rate_weight']*100}%")
            st.metric("Temps", f"{weights['response_time_weight']*100}%")
            st.metric("Contexte", f"{weights['context_weight']*100}%")
        
        st.divider()
        
        # Détail par étape
        st.markdown("### 🔍 Détail du calcul par étape")
        
        df_intel = pd.DataFrame(intelligent_results)
        previous_services = []
        
        for idx, row in df_intel.iterrows():
            with st.expander(
                f"**Étape {row['step']}**: {row['needed_function']} → {row['selected_service']} (Score: {row['score']}/100)",
                expanded=(idx == 0)
            ):
                if row.get("annotations_used"):
                    # Calculer le breakdown
                    breakdown = calculate_score_breakdown(
                        row["annotations_used"],
                        row["selected_operation"],
                        previous_services,
                        weights
                    )
                    
                    # Graphique de décomposition du score
                    fig = go.Figure()
                    
                    components = {
                        'Interaction': breakdown['interaction_score'],
                        'Succès': breakdown['success_rate_score'],
                        'Temps': breakdown['response_time_score'],
                        'Contexte': breakdown['context_score']
                    }
                    
                    if breakdown['bonus'] > 0:
                        components['Bonus'] = breakdown['bonus']
                    if breakdown['penalty'] < 0:
                        components['Pénalité'] = breakdown['penalty']
                    
                    fig.add_trace(go.Bar(
                        x=list(components.keys()),
                        y=list(components.values()),
                        text=[f"{v:.1f}" for v in components.values()],
                        textposition='auto',
                        marker_color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
                    ))
                    
                    fig.update_layout(
                        title=f"Décomposition du Score: {breakdown['total']}/100",
                        yaxis_title="Points",
                        height=400,
                        showlegend=False
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Tableau détaillé
                    col_a, col_b = st.columns(2)
                    
                    with col_a:
                        st.markdown("**📊 Calculs détaillés**")
                        
                        details = breakdown['details']
                        
                        st.markdown(f"""
                        **1. Score Interaction ({weights['interaction_weight']*100}%)**
                        - Nombre d'interactions : `{details.get('num_interactions', 0)}`
                        - Normalisé : `{details.get('interaction_normalized', 0):.3f}`
                        - Score : `{breakdown['interaction_score']:.2f}` points
                        """)
                        
                        if details.get('bonus_previous_services', 0) > 0:
                            st.markdown(f"""
                            - Bonus interactions précédentes : `+{details['bonus_previous_services']}` points
                            """)
                        
                        st.markdown(f"""
                        **2. Score Succès ({weights['success_rate_weight']*100}%)**
                        - Taux de succès : `{details.get('success_rate', 0):.2%}`
                        - Score : `{breakdown['success_rate_score']:.2f}` points
                        
                        **3. Score Temps ({weights['response_time_weight']*100}%)**
                        - Temps moyen : `{details.get('response_time_ms', 0)} ms`
                        - Normalisé : `{details.get('time_normalized', 0):.3f}`
                        - Score : `{breakdown['response_time_score']:.2f}` points
                        """)
                    
                    with col_b:
                        st.markdown("**🌍 Score Contexte**")
                        
                        context_features = details.get('context_features', {})
                        context_points = details.get('context_points', 0)
                        
                        st.markdown(f"""
                        **Features activées :** ({context_points}/20 points)
                        """)
                        
                        if context_features.get('location_dependent'):
                            st.markdown("✅ Location dependent (+5)")
                        else:
                            st.markdown("❌ Location dependent (0)")
                        
                        if context_features.get('time_sensitive'):
                            st.markdown("✅ Time sensitive (+5)")
                        else:
                            st.markdown("❌ Time sensitive (0)")
                        
                        if context_features.get('user_preference_based'):
                            st.markdown("✅ User preference (+5)")
                        else:
                            st.markdown("❌ User preference (0)")
                        
                        if context_features.get('requires_session'):
                            st.markdown("✅ Requires session (+5)")
                        else:
                            st.markdown("❌ Requires session (0)")
                        
                        st.markdown(f"""
                        **Score contexte : `{breakdown['context_score']:.2f}` points**
                        """)
                        
                        if details.get('high_cost_penalty'):
                            st.markdown("⚠️ **Pénalité coût élevé : -5 points**")
                    
                    # Récapitulatif
                    st.markdown("---")
                    st.markdown(f"""
                    ### 🎯 Score Final
                    
                    ```
                    {breakdown['interaction_score']:.2f} (interaction) +
                    {breakdown['success_rate_score']:.2f} (succès) +
                    {breakdown['response_time_score']:.2f} (temps) +
                    {breakdown['context_score']:.2f} (contexte) +
                    {breakdown['bonus']:.2f} (bonus) +
                    {breakdown['penalty']:.2f} (pénalités)
                    = {breakdown['total']:.2f} / 100
                    ```
                    """)
                
                else:
                    st.warning("Annotations non disponibles pour cette étape")
                
                # Ajouter le service aux services précédents
                previous_services.append(row['selected_service'])
        
        
    # ====================================================================
    # COMPARAISON
    # ====================================================================
    with tab4:
        st.subheader("📈 Comparaison Classique vs Intelligente")

        classic_results = results.get("classic")
        intelligent_results = results.get("intelligent")

        if not classic_results or not intelligent_results:
            st.info("Les deux méthodes doivent être exécutées pour comparer")
            return

        df_classic = pd.DataFrame(classic_results)
        df_intel = pd.DataFrame(intelligent_results)

        # Tableau de comparaison
        st.markdown("### 🔄 Services sélectionnés")
        
        comparison_data = []
        for i in range(len(df_classic)):
            classic_row = df_classic.iloc[i]
            intel_row = df_intel.iloc[i]
            
            is_different = classic_row['selected_service'] != intel_row['selected_service']
            
            comparison_data.append({
                "Étape": classic_row["step"],
                "Fonction": classic_row["needed_function"],
                "Service (Classique)": classic_row["selected_service"] + (" 🔴" if is_different else ""),
                "Opération (Classique)": classic_row["selected_operation"],
                "Service (Intelligent)": intel_row["selected_service"] + (" 🟢" if is_different else ""),
                "Opération (Intelligent)": intel_row["selected_operation"],
                "Score LLM": round(intel_row["score"], 2)
            })
        
        comparison_df = pd.DataFrame(comparison_data)
        st.dataframe(comparison_df, use_container_width=True)
        
        st.caption("🔴 = Choix classique • 🟢 = Choix intelligent (quand différents)")

        # Métriques de performance
        st.markdown("### ⚡ Performance")
        
        col1, col2, col3 = st.columns(3)
        
        classic_time = df_classic["execution_time"].sum()
        intel_time = df_intel["execution_time"].sum()
        gain = classic_time - intel_time
        gain_percent = (gain / classic_time * 100) if classic_time > 0 else 0
        
        col1.metric(
            "Temps Classique (ms)", 
            int(classic_time),
            help="Temps total de la composition classique"
        )
        col2.metric(
            "Temps Intelligent (ms)", 
            int(intel_time),
            help="Temps total de la composition intelligente"
        )
        col3.metric(
            "Gain de performance", 
            f"{int(gain)} ms",
            delta=f"{gain_percent:+.1f}%",
            help="Différence de temps d'exécution"
        )
        
        # Analyse des choix
        st.markdown("### 🎯 Analyse des choix")
        
        different_choices = sum(
            1 for i in range(len(df_classic))
            if df_classic.iloc[i]['selected_service'] != df_intel.iloc[i]['selected_service']
        )
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.metric(
                "Choix différents", 
                f"{different_choices}/{len(df_classic)}",
                help="Nombre d'étapes où les deux méthodes ont choisi des services différents"
            )
        
        with col_b:
            avg_score = df_intel["score"].mean()
            st.metric(
                "Score LLM moyen",
                f"{avg_score:.2f}/100",
                help="Score moyen de qualité calculé par le LLM"
            )
        
        # Explication
        st.markdown("### 💡 Explication")
        
        if different_choices > 0:
            st.success(f"""
            **L'approche intelligente a fait {different_choices} choix différent(s)** par rapport à l'approche classique.
            
            Ces choix sont basés sur:
            - 📊 L'historique d'interactions entre services
            - ✅ Le taux de succès des opérations
            - ⚡ Les temps de réponse moyens
            - 🌍 Le contexte d'exécution
            - 🔒 Les politiques de sécurité et coût
            
            Score moyen de {avg_score:.1f}/100 → Les services sélectionnés sont optimaux selon les annotations LLM.
            """)
        else:
            st.info("""
            **Les deux méthodes ont fait les mêmes choix** pour cette composition.
            
            Cela peut arriver quand:
            - Les services alphabétiquement premiers sont aussi les meilleurs selon le scoring
            - Il y a peu de services disponibles par étape
            - Les annotations ne montrent pas de différences significatives
            """)
        
        # Export des résultats
        st.divider()
        
        if st.button("📥 Exporter les résultats (JSON)", use_container_width=True):
            export_data = {
                "classic": classic_results,
                "intelligent": intelligent_results,
                "comparison": {
                    "total_steps": len(df_classic),
                    "different_choices": int(different_choices),
                    "classic_total_time": int(classic_time),
                    "intelligent_total_time": int(intel_time),
                    "time_gain_ms": int(gain),
                    "time_gain_percent": round(gain_percent, 2),
                    "avg_score": round(avg_score, 2)
                }
            }
            
            st.download_button(
                label="💾 Télécharger JSON",
                data=json.dumps(export_data, indent=2, ensure_ascii=False),
                file_name="composition_results.json",
                mime="application/json"
            )