import streamlit as st
import pandas as pd
import json

def render():
    st.header("📊 Résultats de la composition")

    if not st.session_state.get('composition_results'):
        st.info("ℹ️ Aucune composition exécutée pour le moment")
        return

    results = st.session_state.composition_results

    tab1, tab2, tab3 = st.tabs([
        "📘 Composition Classique",
        "⚡ Composition Intelligente",
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
            # Afficher le tableau
            df_classic = pd.DataFrame(classic_results)
            
            # Colonnes à afficher
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
            
            # Afficher le tableau principal
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

            # Détails des annotations
            with st.expander("🔍 Détails des annotations utilisées pour le scoring"):
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
    # COMPARAISON
    # ====================================================================
    with tab3:
        st.subheader("📈 Comparaison Classique vs Intelligente")

        classic_results = results.get("classic")
        intelligent_results = results.get("intelligent")

        if not classic_results or not intelligent_results:
            st.info("Les deux méthodes doivent être exécutées pour comparer")
            return

        df_classic = pd.DataFrame(classic_results)
        df_intel = pd.DataFrame(intelligent_results)

        # Tableau de comparaison - Version simplifiée sans styling
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