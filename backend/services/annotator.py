"""
Module d'annotation automatique des services web
Basé sur le modèle MOF-based Social Web Services Description Metamodel
Référence: Benna, A., Maamar, Z., & Nacer, M. A. (2016)

Performance-optimised implementation:
  – Bulk annotation in two global phases (edge computation + per-service assembly)
  – Merged interaction + association building (single index walk, no duplicate)
  – Capped associations per service (top-K by weight → bounds object creation)
  – Pre-cached QoS scalars (avoids repeated attribute lookups)
  – Progress callback throttled (every 200 services, not every service)
  – Parallel LLM calls via ThreadPoolExecutor (6 workers)
"""

import json
import requests
from collections import defaultdict
from datetime import datetime
from operator import itemgetter
from concurrent.futures import ThreadPoolExecutor, as_completed
from models.annotation import (
    ServiceAnnotation,
    SNAssociation,
    SNAssociationType,
    SNAssociationWeight,
    InteractionAnnotation,
    ContextAnnotation,
    PolicyAnnotation,
)
from models.interaction_history import InteractionHistoryStore

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------
MAX_COLLAB_ASSOC = 30        # keep top-K collaboration associations per service
MAX_SUBSTITUTION_ASSOC = 15  # keep top-K substitution associations per service
COLLAB_WEIGHT_THRESHOLD = 0.3
SUBSTITUTION_OVERLAP = 0.7


class ServiceAnnotator:
    def __init__(self, services=None, ollama_url="http://localhost:11434",
                 training_examples=None, interaction_store: InteractionHistoryStore = None):
        self.services = services or []
        self.service_dict = {s.id: s for s in self.services}
        self.ollama_url = ollama_url
        self.model = "llama3.2:3b"

        # Interaction history store — single source of truth for annotations
        self.history_store = interaction_store or InteractionHistoryStore()

        # Import training examples into the history store if provided
        # and the store is still empty (avoid duplicate imports).
        if training_examples and not self.history_store.has_history:
            self.history_store.import_from_training(training_examples)

        # Pre-computed stats from the history store
        self._history_stats = self.history_store.get_all_stats() if self.history_store.has_history else None

        # Legacy compat: expose same flags for code that checks _has_training_data
        self._collaboration_counts = defaultdict(lambda: defaultdict(int))
        self._interaction_counts = defaultdict(int)
        self._has_training_data = self.history_store.has_history
        if self._has_training_data:
            # Populate legacy dicts from store (read-only, for LLM fallback code)
            hs = self._history_stats
            for sid, cnt in hs['interaction_counts'].items():
                self._interaction_counts[sid] = cnt
            for sid, others in hs['collaboration_counts'].items():
                for oid, cnt in others.items():
                    self._collaboration_counts[sid][oid] = cnt

        # ----- Pre-built indexes -----
        self._output_index = defaultdict(set)   # param -> set of service IDs that produce it
        self._input_index  = defaultdict(set)    # param -> set of service IDs that consume it
        self._service_output_sets = {}           # sid -> frozenset(outputs)
        self._service_input_sets  = {}           # sid -> frozenset(inputs)

        # Pre-cached QoS scalars used for weight computation (avoid attribute lookups)
        self._qos_reliability  = {}
        self._qos_availability = {}
        self._qos_successability = {}
        self._qos_compliance   = {}
        self._qos_best_practices = {}
        self._qos_documentation = {}
        self._qos_response_time = {}

        for s in self.services:
            sid = s.id
            outs = frozenset(s.outputs)
            ins  = frozenset(s.inputs)
            self._service_output_sets[sid] = outs
            self._service_input_sets[sid]  = ins
            for o in outs:
                self._output_index[o].add(sid)
            for i in ins:
                self._input_index[i].add(sid)

            q = s.qos
            self._qos_reliability[sid]    = q.reliability
            self._qos_availability[sid]   = q.availability
            self._qos_successability[sid] = q.successability
            self._qos_compliance[sid]     = q.compliance
            self._qos_best_practices[sid] = q.best_practices
            self._qos_documentation[sid]  = q.documentation
            self._qos_response_time[sid]  = q.response_time

        # Pre-computed lengths for tight inner loops (avoid len() in hot path)
        self._input_lengths = {sid: len(ins) for sid, ins in self._service_input_sets.items()}
        self._output_lengths = {sid: len(outs) for sid, outs in self._service_output_sets.items()}

    # ------------------------------------------------------------------
    #  Refresh stats from the history store (called after new recordings)
    # ------------------------------------------------------------------
    def refresh_history_stats(self):
        """Recharge les statistiques depuis le store d'historique.
        Appelé après l'enregistrement de nouvelles compositions."""
        self._history_stats = self.history_store.get_all_stats() if self.history_store.has_history else None
        self._has_training_data = self.history_store.has_history
        if self._has_training_data and self._history_stats:
            hs = self._history_stats
            self._interaction_counts.clear()
            self._collaboration_counts.clear()
            for sid, cnt in hs['interaction_counts'].items():
                self._interaction_counts[sid] = cnt
            for sid, others in hs['collaboration_counts'].items():
                for oid, cnt in others.items():
                    self._collaboration_counts[sid][oid] = cnt

    # ====================================================================
    #  BULK CLASSIC ANNOTATION  (two-phase: edges → assembly)
    # ====================================================================
    def annotate_all(self, service_ids=None, use_llm=False, annotation_types=None, progress_callback=None):
        if annotation_types is None:
            annotation_types = ['interaction', 'context', 'policy']

        if service_ids:
            id_set = set(service_ids)
            services_to_annotate = [s for s in self.services if s.id in id_set]
        else:
            services_to_annotate = list(self.services)

        total = len(services_to_annotate)

        if use_llm:
            return self._annotate_all_llm(services_to_annotate, annotation_types, progress_callback)

        # ---------- Classic bulk path ----------
        need_interaction = 'interaction' in annotation_types
        need_context     = 'context'     in annotation_types
        need_policy      = 'policy'      in annotation_types

        # ---------------------------------------------------------------
        # PHASE 1: Bulk edge computation (one pass over all services)
        # ---------------------------------------------------------------
        # Results: per-service lightweight edge tuples
        collab_edges  = defaultdict(list)   # sid -> [(target, weight), ...]
        subst_edges   = defaultdict(list)   # sid -> [(target, robustness), ...]
        depend_edges  = defaultdict(set)    # sid -> set of target ids
        can_call_map  = defaultdict(set)    # sid -> set of target ids

        sids = {s.id for s in services_to_annotate}

        # Local variable caching for tight inner loop
        _out_idx   = self._output_index
        _inp_idx   = self._input_index
        _out_sets  = self._service_output_sets
        _inp_sets  = self._service_input_sets
        _qos_rel   = self._qos_reliability
        _qos_avl   = self._qos_availability
        _inp_lens  = self._input_lengths
        _empty_fs  = frozenset()
        _empty_set = set()

        for sid in sids:
            svc_outs = _out_sets[sid]
            svc_ins  = _inp_sets[sid]
            n_outs   = len(svc_outs)
            rel1     = _qos_rel[sid]
            avail1   = _qos_avl[sid]

            # -- Collaboration & can_call (services whose inputs ∩ our outputs)
            candidates = set()
            for o in svc_outs:
                cset = _inp_idx.get(o)
                if cset:
                    candidates.update(cset)
            candidates.discard(sid)

            # By construction, every candidate has io_match >= 1 (came from index).
            # So all candidates are can-call targets; assign directly.
            can_call_map[sid] = candidates

            collab_buf = collab_edges[sid]
            for other_id in candidates:
                io_match = len(svc_outs & _inp_sets[other_id])
                # Inline weight: io_ratio * 0.5 + qos_sim * 0.3 + 0.2 (trust=1 default)
                io_ratio = io_match / (_inp_lens[other_id] or 1)
                rel_diff = rel1 - _qos_rel[other_id]
                qos_sim  = 1.0 - (rel_diff if rel_diff > 0 else -rel_diff) * 0.01
                weight   = io_ratio * 0.5 + qos_sim * 0.3 + 0.2
                if weight > COLLAB_WEIGHT_THRESHOLD:
                    collab_buf.append((other_id, weight))

            # keep top-K by weight
            if len(collab_buf) > MAX_COLLAB_ASSOC:
                collab_buf.sort(key=itemgetter(1), reverse=True)
                collab_edges[sid] = collab_buf[:MAX_COLLAB_ASSOC]

            # -- Substitution (services with ≥70% overlapping outputs)
            if n_outs > 0:
                sub_cands = set()
                for o in svc_outs:
                    oset = _out_idx.get(o)
                    if oset:
                        sub_cands.update(oset)
                sub_cands.discard(sid)

                threshold = n_outs * SUBSTITUTION_OVERLAP
                subst_buf = subst_edges[sid]

                for other_id in sub_cands:
                    if len(svc_outs & _out_sets[other_id]) >= threshold:
                        rd = rel1 - _qos_rel[other_id]
                        r_sim = 1.0 - (rd if rd > 0 else -rd) * 0.01
                        ad = avail1 - _qos_avl[other_id]
                        a_sim = 1.0 - (ad if ad > 0 else -ad) * 0.01
                        subst_buf.append((other_id, r_sim * 0.5 + a_sim * 0.5))

                if len(subst_buf) > MAX_SUBSTITUTION_ASSOC:
                    subst_buf.sort(key=itemgetter(1), reverse=True)
                    subst_edges[sid] = subst_buf[:MAX_SUBSTITUTION_ASSOC]

            # -- Dependency (services whose outputs provide our inputs)
            dep_buf = depend_edges[sid]
            for inp in svc_ins:
                dset = _out_idx.get(inp)
                if dset:
                    for other_id in dset:
                        if other_id != sid:
                            dep_buf.add(other_id)

        if progress_callback:
            progress_callback(0, total, "edges computed")

        # ---------------------------------------------------------------
        # PHASE 2: Assemble annotation objects (tight loop, no method calls)
        # ---------------------------------------------------------------
        annotated = []
        now_iso = datetime.now().isoformat()

        _qos_suc = self._qos_successability
        _qos_cmp = self._qos_compliance
        _qos_bpr = self._qos_best_practices
        _qos_doc = self._qos_documentation
        _qos_rt  = self._qos_response_time
        # History-derived bulk data
        _hs = self._history_stats  # may be None
        _hist_interaction = _hs['interaction_counts'] if _hs else {}
        _hist_collab = _hs['collaboration_counts'] if _hs else {}
        _hist_success = _hs['success_rates'] if _hs else {}
        _hist_last = _hs['last_used'] if _hs else {}
        _hist_util = _hs['avg_utilities'] if _hs else {}
        _store = self.history_store

        # Cache __new__ for zero-init object creation (skip __init__ dispatch)
        _new_assoc   = SNAssociation.__new__
        _new_at      = SNAssociationType.__new__
        _new_aw      = SNAssociationWeight.__new__
        _SNAssoc_cls = SNAssociation
        _SNAType_cls = SNAssociationType
        _SNAWt_cls   = SNAssociationWeight

        for idx, service in enumerate(services_to_annotate):
            sid = service.id
            ann = ServiceAnnotation(sid)
            ann.social_node.node_type = "WebService"
            ann.social_node.state = "active"

            # ---- Social node properties (QoS-derived, inlined) ----
            rel = _qos_rel[sid]
            avl = _qos_avl[sid]
            suc = _qos_suc[sid]
            cmp = _qos_cmp[sid]
            bpr = _qos_bpr[sid]
            doc = _qos_doc[sid]
            rt  = _qos_rt[sid]

            trust = (rel * 0.3 + suc * 0.3 + avl * 0.2 + cmp * 0.2) * 0.01
            reputation = (bpr * 0.4 + doc * 0.3 + cmp * 0.3) * 0.01
            cooperativeness = (rel * 0.5 + avl * 0.5) * 0.01

            sn = ann.social_node
            sn.trust_degree.value     = min(max(trust, 0.0), 1.0)
            sn.reputation.value       = min(max(reputation, 0.0), 1.0)
            sn.cooperativeness.value  = min(max(cooperativeness, 0.0), 1.0)
            sn.add_property("robustness_score", (rel * 0.4 + avl * 0.3 + suc * 0.3) * 0.01)

            # ---- Interaction annotation (from pre-computed edges + history) ----
            if need_interaction:
                ia = ann.interaction
                cc = list(can_call_map.get(sid, set()))
                dd = list(depend_edges.get(sid, set()))
                ia.can_call = cc
                ia.collaboration_associations = [t for t, _ in collab_edges.get(sid, [])]
                ia.depends_on = dd
                ia.substitutes = [t for t, _ in subst_edges.get(sid, [])]
                ia.substitution_associations = ia.substitutes
                ia.role = (
                    "orchestrator" if len(cc) > 3
                    else "aggregator" if len(dd) > 3
                    else "worker"
                )
                # Collaboration history from REAL interaction records
                sid_collab = _hist_collab.get(sid, {})
                ia.collaboration_history = {
                    s_id: sid_collab.get(s_id, 0)
                    for s_id in cc[:10]
                }

            # ---- Context annotation (from REAL history) ----
            if need_context:
                ctx = ann.context
                interaction_count = _hist_interaction.get(sid, 0)
                success_rate = _hist_success.get(sid, 0.0)
                last_used = _hist_last.get(sid)
                observed_ctx = _store.get_observed_contexts(sid)
                usage_patterns = _store.get_usage_patterns(sid)

                # context_aware: true if the service has been invoked with
                # context metadata at least once
                ctx.context_aware = observed_ctx.get('total_with_context', 0) > 0

                # location_sensitive: true if observed from multiple locations
                ctx.location_sensitive = len(observed_ctx.get('locations', {})) > 1

                ctx.time_critical = "low" if rt < 50 else ("medium" if rt < 200 else "high")
                ctx.interaction_count = interaction_count
                ctx.last_used = last_used or now_iso
                ctx.usage_patterns = usage_patterns if usage_patterns else []

                # Environmental requirements derived from observed network types
                env_reqs = []
                obs_nets = observed_ctx.get('networks', {})
                if 'vpn' in obs_nets or cmp > 80:
                    env_reqs.append('vpn')
                if obs_nets.get('ethernet', 0) > obs_nets.get('wifi', 0):
                    env_reqs.append('secure_network')
                elif cmp > 85:
                    env_reqs.append('secure_network')
                ctx.environmental_requirements = env_reqs

                # NEW: populate observed context summaries
                ctx.observed_locations = observed_ctx.get('locations', {})
                ctx.observed_networks = observed_ctx.get('networks', {})
                ctx.observed_devices = observed_ctx.get('device_types', {})

                # Context adaptation score: how diverse are the contexts this
                # service has been successfully used in?
                n_locs = len(ctx.observed_locations)
                n_nets = len(ctx.observed_networks)
                n_devs = len(ctx.observed_devices)
                diversity = min((n_locs + n_nets + n_devs) / 10.0, 1.0)
                ctx.context_adaptation_score = round(
                    diversity * 0.6 + (success_rate * 0.4), 3
                )

            # ---- Policy annotation (deterministic from QoS) ----
            if need_policy:
                pol = ann.policy
                pol.gdpr_compliant = cmp > 70
                # Retention based on observed success rate & compliance
                sr = _hist_success.get(sid, 0.5)
                if sr >= 0.95 and cmp > 85:
                    pol.data_retention_days = 365
                elif sr >= 0.8 and cmp > 70:
                    pol.data_retention_days = 180
                elif cmp > 60:
                    pol.data_retention_days = 90
                else:
                    pol.data_retention_days = 30
                pol.security_level = "high" if rel > 90 else ("medium" if rel > 70 else "low")
                pol.privacy_policy = (
                    "encrypted_and_anonymized" if cmp > 85
                    else ("encrypted" if rel > 70 else "anonymized")
                )
                if cmp > 85:
                    pol.compliance_standards = ["ISO27001", "SOC2"]
                elif cmp > 70:
                    pol.compliance_standards = ["ISO27001"]
                pol.data_classification = "confidential" if cmp > 85 else ("internal" if cmp > 70 else "public")
                pol.encryption_required = pol.security_level == "high"

            # ---- Materialise SNAssociation objects (skip __init__, set slots directly) ----
            assocs = sn.associations
            for target, w in collab_edges.get(sid, []):
                a = _new_assoc(_SNAssoc_cls)
                a.source_node = sid
                a.target_node = target
                a.duration = "permanent"
                a.creation_date = None
                a.last_interaction = None
                at = _new_at(_SNAType_cls)
                at.type_name = "collaboration"
                at.is_symmetric = False
                at.supports_transitivity = True
                at.is_dependent = False
                at.temporal_aspect = "permanent"
                a.association_type = at
                aw = _new_aw(_SNAWt_cls)
                aw.prop_name = "collaboration_weight"
                aw.value = w
                aw.calculation_method = "combined"
                a.association_weight = aw
                assocs.append(a)

            for target, r in subst_edges.get(sid, []):
                a = _new_assoc(_SNAssoc_cls)
                a.source_node = sid
                a.target_node = target
                a.duration = "permanent"
                a.creation_date = None
                a.last_interaction = None
                at = _new_at(_SNAType_cls)
                at.type_name = "substitution"
                at.is_symmetric = True
                at.supports_transitivity = False
                at.is_dependent = False
                at.temporal_aspect = "upon_request"
                a.association_type = at
                aw = _new_aw(_SNAWt_cls)
                aw.prop_name = "robustness_weight"
                aw.value = r
                aw.calculation_method = "interaction_count"
                a.association_weight = aw
                assocs.append(a)

            service.annotations = ann
            annotated.append(service)

            if progress_callback and (idx % max(total // 100, 1) == 0 or idx == total - 1):
                progress_callback(idx + 1, total, sid)

        return annotated

    # ====================================================================
    #  LLM ANNOTATION  (parallel I/O via ThreadPoolExecutor)
    # ====================================================================
    def _annotate_all_llm(self, services_to_annotate, annotation_types, progress_callback):
        total = len(services_to_annotate)
        annotated = []
        max_workers = 6  # concurrent Ollama calls

        def _do_one(service):
            return self.annotate_service(service, use_llm=True, annotation_types=annotation_types)

        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_svc = {pool.submit(_do_one, s): s for s in services_to_annotate}
            for future in as_completed(future_to_svc):
                svc = future_to_svc[future]
                try:
                    future.result()
                except Exception as exc:
                    print(f"LLM annotation error for {svc.id}: {exc}")
                annotated.append(svc)
                completed += 1
                if progress_callback and (completed % 10 == 0 or completed == total):
                    progress_callback(completed, total, svc.id)

        return annotated

    # ====================================================================
    #  SINGLE-SERVICE ANNOTATION (used by LLM path & individual calls)
    # ====================================================================
    def annotate_service(self, service, use_llm=False, annotation_types=None):
        if annotation_types is None:
            annotation_types = ['interaction', 'context', 'policy']

        annotation = ServiceAnnotation(service.id)
        annotation.social_node.node_type = "WebService"
        annotation.social_node.state = "active"

        if use_llm:
            annotation = self._annotate_with_llm(service, annotation_types)
        else:
            if 'interaction' in annotation_types:
                annotation.interaction = self._generate_interaction_annotations(service)
            if 'context' in annotation_types:
                annotation.context = self._generate_context_annotations(service)
            if 'policy' in annotation_types:
                annotation.policy = self._generate_policy_annotations(service)

        self._calculate_social_properties(service, annotation)
        self._build_social_associations(service, annotation)

        service.annotations = annotation
        return service

    # --------  helpers kept for single-service / LLM fallback  --------

    def _calculate_social_properties(self, service, annotation):
        q = service.qos
        trust = (q.reliability * 0.3 + q.successability * 0.3 + q.availability * 0.2 + q.compliance * 0.2) * 0.01
        reputation = (q.best_practices * 0.4 + q.documentation * 0.3 + q.compliance * 0.3) * 0.01
        cooperativeness = (q.reliability * 0.5 + q.availability * 0.5) * 0.01

        annotation.social_node.trust_degree.value    = min(max(trust, 0.0), 1.0)
        annotation.social_node.reputation.value       = min(max(reputation, 0.0), 1.0)
        annotation.social_node.cooperativeness.value   = min(max(cooperativeness, 0.0), 1.0)
        annotation.social_node.add_property(
            "robustness_score",
            (q.reliability * 0.4 + q.availability * 0.3 + q.successability * 0.3) * 0.01,
        )

    def _build_social_associations(self, service, annotation):
        """Build social associations — single-service version (LLM fallback)."""
        sid = service.id
        svc_outs = self._service_output_sets.get(sid, frozenset())
        svc_ins  = self._service_input_sets.get(sid, frozenset())
        rel1   = self._qos_reliability.get(sid, 50)
        avail1 = self._qos_availability.get(sid, 50)

        # Collaboration
        candidates = set()
        for o in svc_outs:
            candidates.update(self._input_index.get(o, set()))
        candidates.discard(sid)

        collab = []
        for oid in candidates:
            other_ins = self._service_input_sets.get(oid, frozenset())
            io = len(svc_outs & other_ins)
            if io > 0:
                io_ratio = io / max(len(other_ins), 1)
                qos_sim  = 1.0 - abs(rel1 - self._qos_reliability.get(oid, 50)) * 0.01
                w = io_ratio * 0.5 + qos_sim * 0.3 + 0.2
                if w > COLLAB_WEIGHT_THRESHOLD:
                    collab.append((oid, w))

        collab.sort(key=itemgetter(1), reverse=True)
        for target, w in collab[:MAX_COLLAB_ASSOC]:
            a = SNAssociation()
            a.source_node, a.target_node = sid, target
            a.association_type.type_name = "collaboration"
            a.association_type.is_symmetric = False
            a.association_type.supports_transitivity = True
            a.association_type.temporal_aspect = "permanent"
            a.association_weight.prop_name = "collaboration_weight"
            a.association_weight.value = w
            a.association_weight.calculation_method = "combined"
            annotation.social_node.associations.append(a)
            annotation.interaction.collaboration_associations.append(target)
            annotation.interaction.can_call.append(target)

        # Substitution
        n_outs = len(svc_outs)
        if n_outs > 0:
            sub_cands = set()
            for o in svc_outs:
                sub_cands.update(self._output_index.get(o, set()))
            sub_cands.discard(sid)
            thresh = n_outs * SUBSTITUTION_OVERLAP

            subst = []
            for oid in sub_cands:
                other_outs = self._service_output_sets.get(oid, frozenset())
                if len(svc_outs & other_outs) >= thresh:
                    r_sim = 1.0 - abs(rel1 - self._qos_reliability.get(oid, 50)) * 0.01
                    a_sim = 1.0 - abs(avail1 - self._qos_availability.get(oid, 50)) * 0.01
                    subst.append((oid, r_sim * 0.5 + a_sim * 0.5))

            subst.sort(key=itemgetter(1), reverse=True)
            for target, r in subst[:MAX_SUBSTITUTION_ASSOC]:
                a = SNAssociation()
                a.source_node, a.target_node = sid, target
                a.association_type.type_name = "substitution"
                a.association_type.is_symmetric = True
                a.association_type.supports_transitivity = False
                a.association_type.temporal_aspect = "upon_request"
                a.association_weight.prop_name = "robustness_weight"
                a.association_weight.value = r
                annotation.social_node.associations.append(a)
                annotation.interaction.substitution_associations.append(target)
                annotation.interaction.substitutes.append(target)

        # Dependency
        for inp in svc_ins:
            for oid in self._output_index.get(inp, set()):
                if oid != sid:
                    annotation.interaction.depends_on.append(oid)

    def _generate_interaction_annotations(self, service):
        interaction = InteractionAnnotation()
        svc_outs = self._service_output_sets.get(service.id, frozenset())
        svc_ins  = self._service_input_sets.get(service.id, frozenset())

        seen = set()
        for o in svc_outs:
            for oid in self._input_index.get(o, set()):
                if oid != service.id and oid not in seen:
                    seen.add(oid)
                    interaction.can_call.append(oid)
                    interaction.collaboration_associations.append(oid)

        seen2 = set()
        for inp in svc_ins:
            for oid in self._output_index.get(inp, set()):
                if oid != service.id and oid not in seen2:
                    seen2.add(oid)
                    interaction.depends_on.append(oid)

        cc, dd = len(interaction.can_call), len(interaction.depends_on)
        interaction.role = "orchestrator" if cc > 3 else ("aggregator" if dd > 3 else "worker")
        # Collaboration history from REAL interaction records
        collab_counts = self.history_store.get_collaboration_counts(service.id)
        interaction.collaboration_history = {
            s: collab_counts.get(s, 0)
            for s in interaction.can_call[:10]
        }
        return interaction

    def _generate_context_annotations(self, service):
        ctx = ContextAnnotation()
        q = service.qos
        sid = service.id

        # Derive context from REAL observed interactions
        observed_ctx = self.history_store.get_observed_contexts(sid)
        usage_patterns = self.history_store.get_usage_patterns(sid)
        success_rate = self.history_store.get_success_rate(sid)

        ctx.context_aware = observed_ctx.get('total_with_context', 0) > 0
        ctx.location_sensitive = len(observed_ctx.get('locations', {})) > 1
        ctx.time_critical = "low" if q.response_time < 50 else ("medium" if q.response_time < 200 else "high")
        ctx.interaction_count = self.history_store.get_interaction_count(sid)
        ctx.last_used = self.history_store.get_last_used(sid) or datetime.now().isoformat()
        ctx.usage_patterns = usage_patterns if usage_patterns else []

        # Environmental requirements from observed networks
        env_reqs = []
        obs_nets = observed_ctx.get('networks', {})
        if 'vpn' in obs_nets or q.compliance > 80:
            env_reqs.append('vpn')
        if obs_nets.get('ethernet', 0) > obs_nets.get('wifi', 0) or q.compliance > 85:
            env_reqs.append('secure_network')
        ctx.environmental_requirements = env_reqs

        # Observed context summaries
        ctx.observed_locations = observed_ctx.get('locations', {})
        ctx.observed_networks = observed_ctx.get('networks', {})
        ctx.observed_devices = observed_ctx.get('device_types', {})

        # Context adaptation score
        n_locs = len(ctx.observed_locations)
        n_nets = len(ctx.observed_networks)
        n_devs = len(ctx.observed_devices)
        diversity = min((n_locs + n_nets + n_devs) / 10.0, 1.0)
        ctx.context_adaptation_score = round(diversity * 0.6 + success_rate * 0.4, 3)
        return ctx

    def _generate_policy_annotations(self, service):
        policy = PolicyAnnotation()
        q = service.qos
        sr = self.history_store.get_success_rate(service.id)
        policy.gdpr_compliant = q.compliance > 70
        # Retention based on observed success rate & compliance
        if sr >= 0.95 and q.compliance > 85:
            policy.data_retention_days = 365
        elif sr >= 0.8 and q.compliance > 70:
            policy.data_retention_days = 180
        elif q.compliance > 60:
            policy.data_retention_days = 90
        else:
            policy.data_retention_days = 30
        policy.security_level = "high" if q.reliability > 90 else ("medium" if q.reliability > 70 else "low")
        policy.privacy_policy = (
            "encrypted_and_anonymized" if q.compliance > 85
            else ("encrypted" if q.reliability > 70 else "anonymized")
        )
        if q.compliance > 85:
            policy.compliance_standards = ["ISO27001", "SOC2"]
        elif q.compliance > 70:
            policy.compliance_standards = ["ISO27001"]
        policy.data_classification = "confidential" if q.compliance > 85 else ("internal" if q.compliance > 70 else "public")
        policy.encryption_required = policy.security_level == "high"
        return policy

    # ====================================================================
    #  LLM ANNOTATION HELPERS
    # ====================================================================
    def _annotate_with_llm(self, service, annotation_types):
        annotation = ServiceAnnotation(service.id)
        service_context = {
            'id': service.id,
            'inputs': service.inputs,
            'outputs': service.outputs,
            'qos': {
                'reliability': service.qos.reliability,
                'availability': service.qos.availability,
                'response_time': service.qos.response_time,
                'compliance': service.qos.compliance,
            },
        }
        if 'interaction' in annotation_types:
            annotation.interaction = self._llm_generate_interaction(service, service_context)
        if 'context' in annotation_types:
            annotation.context = self._llm_generate_context(service, service_context)
        if 'policy' in annotation_types:
            annotation.policy = self._llm_generate_policy(service, service_context)
        return annotation

    def _llm_generate_interaction(self, service, context):
        interaction = InteractionAnnotation()

        # Index-based compatible service lookup (O(degree))
        compatible_services = []
        seen = set()
        svc_outs = self._service_output_sets.get(service.id, frozenset())
        for o in svc_outs:
            for oid in self._input_index.get(o, set()):
                if oid != service.id and oid not in seen:
                    seen.add(oid)
                    other_ins = self._service_input_sets.get(oid, frozenset())
                    compatible_services.append({'id': oid, 'match_score': len(svc_outs & other_ins)})

        prompt = f"""Analyze this web service and determine its role in a service composition:

Service ID: {service.id}
Inputs: {len(service.inputs)}
Outputs: {len(service.outputs)}
QoS Reliability: {service.qos.reliability}%
Compatible services: {len(compatible_services)}

Respond ONLY with JSON (no markdown):
{{
  "role": "orchestrator" or "worker" or "aggregator",
  "can_call_count": number (0-{min(len(compatible_services), 5)}),
  "collaboration_level": "high" or "medium" or "low"
}}
"""
        try:
            response = self._call_ollama(prompt)
            data = self._extract_json(response)
            if data:
                interaction.role = {'orchestrator': 'orchestrator', 'worker': 'worker', 'aggregator': 'aggregator'}.get(data.get('role', '').lower(), 'worker')
                n = min(data.get('can_call_count', 3), len(compatible_services))
                top = sorted(compatible_services, key=lambda x: x['match_score'], reverse=True)
                interaction.can_call = [s['id'] for s in top[:n]]
                interaction.collaboration_associations = interaction.can_call.copy()
                # Use real history for collaboration counts
                collab_counts = self.history_store.get_collaboration_counts(service.id)
                interaction.collaboration_history = {
                    sid: collab_counts.get(sid, 0)
                    for sid in interaction.can_call[:10]
                }
            else:
                interaction = self._generate_interaction_annotations(service)
        except Exception as e:
            print(f"LLM error for interaction: {e}")
            interaction = self._generate_interaction_annotations(service)
        return interaction

    def _llm_generate_context(self, service, context):
        ctx = ContextAnnotation()
        prompt = f"""Analyze this web service's contextual characteristics:

Service: {service.id}
QoS:
- Availability: {service.qos.availability}%
- Response Time: {service.qos.response_time}ms
- Reliability: {service.qos.reliability}%

Respond ONLY with JSON:
{{
  "context_aware": true or false,
  "location_sensitive": true or false,
  "time_critical": "high" or "medium" or "low",
  "usage_frequency": "high" or "medium" or "low"
}}
"""
        try:
            response = self._call_ollama(prompt)
            data = self._extract_json(response)
            if data:
                ctx.context_aware = data.get('context_aware', False)
                ctx.location_sensitive = data.get('location_sensitive', False)
                ctx.time_critical = data.get('time_critical', 'medium')
                # Use REAL interaction count from history
                ctx.interaction_count = self.history_store.get_interaction_count(service.id)
                ctx.usage_patterns = self.history_store.get_usage_patterns(service.id) or []
                ctx.last_used = self.history_store.get_last_used(service.id) or datetime.now().isoformat()
                obs_ctx = self.history_store.get_observed_contexts(service.id)
                env_reqs = []
                obs_nets = obs_ctx.get('networks', {})
                if 'vpn' in obs_nets or service.qos.compliance > 80:
                    env_reqs.append('vpn')
                if obs_nets.get('ethernet', 0) > obs_nets.get('wifi', 0) or service.qos.compliance > 85:
                    env_reqs.append('secure_network')
                ctx.environmental_requirements = env_reqs
            else:
                ctx = self._generate_context_annotations(service)
        except Exception as e:
            print(f"LLM error for context: {e}")
            ctx = self._generate_context_annotations(service)
        return ctx

    def _llm_generate_policy(self, service, context):
        policy = PolicyAnnotation()
        prompt = f"""Analyze this web service's policy requirements:

Service: {service.id}
QoS Compliance: {service.qos.compliance}%
Best Practices: {service.qos.best_practices}%
Reliability: {service.qos.reliability}%

Respond ONLY with JSON:
{{
  "gdpr_compliant": true or false,
  "security_level": "high" or "medium" or "low",
  "data_retention_days": 30 or 60 or 90 or 180 or 365,
  "encryption_required": true or false,
  "data_classification": "public" or "internal" or "confidential"
}}
"""
        try:
            response = self._call_ollama(prompt)
            data = self._extract_json(response)
            if data:
                policy.gdpr_compliant = data.get('gdpr_compliant', True)
                policy.security_level = data.get('security_level', 'medium')
                policy.data_retention_days = data.get('data_retention_days', 30)
                policy.encryption_required = data.get('encryption_required', False)
                policy.data_classification = data.get('data_classification', 'internal')
                policy.privacy_policy = "encrypted" if policy.encryption_required else "standard"
                if service.qos.compliance > 85:
                    policy.compliance_standards = ["ISO27001", "SOC2"]
                elif service.qos.compliance > 70:
                    policy.compliance_standards = ["ISO27001"]
            else:
                policy = self._generate_policy_annotations(service)
        except Exception as e:
            print(f"LLM error for policy: {e}")
            policy = self._generate_policy_annotations(service)
        return policy

    # ====================================================================
    #  OLLAMA HELPERS
    # ====================================================================
    def _call_ollama(self, prompt):
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False, "options": {"temperature": 0.3, "top_p": 0.9}},
                timeout=30,
            )
            if response.status_code == 200:
                return response.json()['response']
            raise Exception(f"Ollama API error: {response.status_code}")
        except requests.exceptions.ConnectionError:
            raise Exception("Cannot connect to Ollama. Is it running?")
        except Exception as e:
            raise Exception(f"Ollama error: {str(e)}")

    def _extract_json(self, text):
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
            return None
        except Exception:
            return None
