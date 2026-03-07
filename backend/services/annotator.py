"""
Automatic web service annotation module.
Based on the MOF-based Social Web Services Description Metamodel.
Reference: Benna, A., Maamar, Z., & Nacer, M. A. (2016).

Performance-optimised implementation:
  – Bulk annotation in two global phases (edge computation + per-service assembly)
  – Merged interaction + association building (single index walk, no duplicate)
  – Capped associations per service (top-K by weight → bounds object creation)
  – Pre-cached QoS scalars (avoids repeated attribute lookups)
  – Progress callback throttled (every 200 services, not every service)
  – Parallel LLM calls via ThreadPoolExecutor (6 workers)
"""

import json
import logging
import os
import requests
import time
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
# Annotation log setup
# ---------------------------------------------------------------------------
_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)

def _make_annotation_logger():
    """Create a file logger that writes to logs/annotation_<timestamp>.log."""
    logger = logging.getLogger("annotation")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    # Remove old handlers (e.g. from previous runs in the same process)
    for h in logger.handlers[:]:
        logger.removeHandler(h)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(
        os.path.join(_LOG_DIR, f"annotation_{ts}.txt"), encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s.%(msecs)03d | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger

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
        self.log = _make_annotation_logger()
        self.services = services or []
        self.service_dict = {s.id: s for s in self.services}
        self.ollama_url = ollama_url
        self.model = "llama3.2:3b"
        self.log.info("="*80)
        self.log.info("ServiceAnnotator INITIALISED")
        self.log.info("  Total services loaded : %d", len(self.services))
        self.log.info("  Ollama URL            : %s", self.ollama_url)
        self.log.info("  Model                 : %s", self.model)

        # Interaction history store — single source of truth for annotations
        self.history_store = interaction_store or InteractionHistoryStore()
        self.log.info("  History store provided : %s", bool(interaction_store))

        # Import training examples into the history store if provided
        # and the store is still empty (avoid duplicate imports).
        if training_examples and not self.history_store.has_history:
            self.log.info("  Importing %d training examples into history store", len(training_examples))
            self.history_store.import_from_training(training_examples)
        elif training_examples:
            self.log.info("  Training examples provided but history store already has data — skipping import")
        else:
            self.log.info("  No training examples provided")

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

        self.log.info("  Has training data     : %s", self._has_training_data)
        self.log.info("  Unique output params  : %d", len(self._output_index))
        self.log.info("  Unique input params   : %d", len(self._input_index))
        self.log.info("  Indexes built successfully")
        self.log.info("="*80)

    # ------------------------------------------------------------------
    #  Refresh stats from the history store (called after new recordings)
    # ------------------------------------------------------------------
    def refresh_history_stats(self):
        """Reload statistics from the history store.
        Called after recording new compositions."""
        self.log.info("Refreshing history stats from store...")
        self._history_stats = self.history_store.get_all_stats() if self.history_store.has_history else None
        self._has_training_data = self.history_store.has_history
        self.log.info("  has_history=%s", self._has_training_data)
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

        self.log.info("="*80)
        self.log.info("annotate_all() CALLED")
        self.log.info("  service_ids filter : %s", service_ids if service_ids else "ALL")
        self.log.info("  use_llm           : %s", use_llm)
        self.log.info("  annotation_types  : %s", annotation_types)
        t_start = time.perf_counter()

        if service_ids:
            id_set = set(service_ids)
            services_to_annotate = [s for s in self.services if s.id in id_set]
        else:
            services_to_annotate = list(self.services)

        total = len(services_to_annotate)
        self.log.info("  services to annotate: %d / %d total", total, len(self.services))

        if use_llm:
            self.log.info("  Delegating to LLM annotation path")
            return self._annotate_all_llm(services_to_annotate, annotation_types, progress_callback)

        # ---------- Classic bulk path ----------
        self.log.info("-"*60)
        self.log.info("CLASSIC BULK PATH")
        need_interaction = 'interaction' in annotation_types
        need_context     = 'context'     in annotation_types
        need_policy      = 'policy'      in annotation_types
        self.log.info("  need_interaction=%s  need_context=%s  need_policy=%s",
                       need_interaction, need_context, need_policy)

        # ---------------------------------------------------------------
        # PHASE 1: Bulk edge computation (one pass over all services)
        # ---------------------------------------------------------------
        self.log.info("PHASE 1: Computing edges across %d services", total)
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

        t_phase1 = time.perf_counter()
        total_collab = sum(len(v) for v in collab_edges.values())
        total_subst  = sum(len(v) for v in subst_edges.values())
        total_deps   = sum(len(v) for v in depend_edges.values())
        total_cancall = sum(len(v) for v in can_call_map.values())
        self.log.info("-"*60)
        self.log.info("PHASE 1 COMPLETE  (%.3f s)", t_phase1 - t_start)
        self.log.info("  Collaboration edges : %d  (across %d services)", total_collab, len(collab_edges))
        self.log.info("  Substitution edges  : %d  (across %d services)", total_subst, len(subst_edges))
        self.log.info("  Dependency edges    : %d  (across %d services)", total_deps, len(depend_edges))
        self.log.info("  Can-call edges      : %d  (across %d services)", total_cancall, len(can_call_map))

        if progress_callback:
            progress_callback(0, total, "edges computed")

        # ---------------------------------------------------------------
        # PHASE 2: Assemble annotation objects (tight loop, no method calls)
        # ---------------------------------------------------------------
        self.log.info("-"*60)
        self.log.info("PHASE 2: Assembling annotations per service")
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
        _hist_contexts = _hs['observed_contexts'] if _hs else {}
        _hist_patterns = _hs['usage_patterns'] if _hs else {}
        _empty_ctx = {"locations": {}, "networks": {}, "device_types": {}, "total_with_context": 0}

        # Cache __new__ for zero-init object creation (skip __init__ dispatch)
        _new_assoc   = SNAssociation.__new__
        _new_at      = SNAssociationType.__new__
        _new_aw      = SNAssociationWeight.__new__
        _SNAssoc_cls = SNAssociation
        _SNAType_cls = SNAssociationType
        _SNAWt_cls   = SNAssociationWeight

        for idx, service in enumerate(services_to_annotate):
            sid = service.id
            self.log.debug("[%d/%d] Assembling annotation for %s", idx+1, total, sid)
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
            self.log.debug("  Social node: trust=%.4f  reputation=%.4f  cooperativeness=%.4f  QoS(rel=%.1f avl=%.1f suc=%.1f cmp=%.1f rt=%.1f)",
                           sn.trust_degree.value, sn.reputation.value, sn.cooperativeness.value, rel, avl, suc, cmp, rt)

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
                self.log.debug("  Interaction: role=%s  can_call=%d  collab_assoc=%d  depends_on=%d  substitutes=%d  collab_history_entries=%d",
                               ia.role, len(cc), len(ia.collaboration_associations), len(dd), len(ia.substitutes), len(ia.collaboration_history))

            # ---- Context annotation (from REAL history, bulk precomputed) ----
            if need_context:
                ctx = ann.context
                interaction_count = _hist_interaction.get(sid, 0)
                success_rate = _hist_success.get(sid, 0.0)
                last_used = _hist_last.get(sid)
                observed_ctx = _hist_contexts.get(sid, _empty_ctx)
                usage_patterns = _hist_patterns.get(sid, [])

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
                self.log.debug("  Context: aware=%s  loc_sensitive=%s  time_critical=%s  interactions=%d  adaptation_score=%.3f  env_reqs=%s  locations=%d  networks=%d  devices=%d",
                               ctx.context_aware, ctx.location_sensitive, ctx.time_critical, ctx.interaction_count,
                               ctx.context_adaptation_score, ctx.environmental_requirements,
                               n_locs, n_nets, n_devs)

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
                self.log.debug("  Policy: gdpr=%s  security=%s  retention=%dd  encryption=%s  classification=%s  standards=%s",
                               pol.gdpr_compliant, pol.security_level, pol.data_retention_days,
                               pol.encryption_required, pol.data_classification,
                               pol.compliance_standards if hasattr(pol, 'compliance_standards') else [])

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

            n_assocs = len(assocs)
            self.log.debug("  Associations materialised: %d total for %s", n_assocs, sid)

            if progress_callback and (idx % max(total // 100, 1) == 0 or idx == total - 1):
                progress_callback(idx + 1, total, sid)

        t_end = time.perf_counter()
        self.log.info("-"*60)
        self.log.info("PHASE 2 COMPLETE  (%.3f s)", t_end - t_phase1)
        self.log.info("ANNOTATION FINISHED  total_time=%.3f s  services_annotated=%d", t_end - t_start, len(annotated))
        self.log.info("="*80)
        return annotated

    # ====================================================================
    #  LLM ANNOTATION  (parallel I/O via ThreadPoolExecutor)
    # ====================================================================
    def _annotate_all_llm(self, services_to_annotate, annotation_types, progress_callback):
        total = len(services_to_annotate)
        annotated = []
        max_workers = 10  # concurrent Ollama calls
        self.log.info("-"*60)
        self.log.info("LLM BULK ANNOTATION  services=%d  workers=%d", total, max_workers)
        self.log.info("  annotation_types: %s", annotation_types)
        t_llm_start = time.perf_counter()

        def _do_one(service):
            return self.annotate_service(service, use_llm=True, annotation_types=annotation_types)

        completed = 0
        errors = 0
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_svc = {pool.submit(_do_one, s): s for s in services_to_annotate}
            for future in as_completed(future_to_svc):
                svc = future_to_svc[future]
                try:
                    future.result()
                except Exception as exc:
                    errors += 1
                    self.log.error("LLM annotation EXCEPTION for %s: %s", svc.id, exc)
                annotated.append(svc)
                completed += 1
                if progress_callback and (completed % 10 == 0 or completed == total):
                    progress_callback(completed, total, svc.id)

        t_llm_end = time.perf_counter()
        self.log.info("LLM BULK ANNOTATION FINISHED  time=%.3f s  annotated=%d  errors=%d",
                       t_llm_end - t_llm_start, len(annotated), errors)
        self.log.info("="*80)
        return annotated

    # ====================================================================
    #  SINGLE-SERVICE ANNOTATION (used by LLM path & individual calls)
    # ====================================================================
    def annotate_service(self, service, use_llm=False, annotation_types=None):
        if annotation_types is None:
            annotation_types = ['interaction', 'context', 'policy']

        self.log.info("annotate_service(%s)  use_llm=%s  types=%s", service.id, use_llm, annotation_types)
        t0 = time.perf_counter()

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
        self.log.info("  annotate_service(%s) DONE in %.3f s  associations=%d",
                       service.id, time.perf_counter() - t0,
                       len(annotation.social_node.associations))
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
    #  LLM ANNOTATION HELPERS — SINGLE COMBINED PROMPT PER SERVICE
    # ====================================================================
    def _annotate_with_llm(self, service, annotation_types):
        """Annotate using ONE combined LLM call instead of 3 separate calls."""
        self.log.info("  _annotate_with_llm(%s)  types=%s", service.id, annotation_types)
        t_llm = time.perf_counter()
        annotation = ServiceAnnotation(service.id)

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
        self.log.debug("    Compatible services found: %d", len(compatible_services))
        if compatible_services:
            top3 = sorted(compatible_services, key=lambda x: x['match_score'], reverse=True)[:3]
            self.log.debug("    Top-3 compatible: %s", [(c['id'], c['match_score']) for c in top3])

        need_interaction = 'interaction' in annotation_types
        need_context = 'context' in annotation_types
        need_policy = 'policy' in annotation_types

        # Build a single combined prompt
        prompt = f"""Analyze this web service and provide ALL annotations in a single JSON response.

Service ID: {service.id}
Inputs: {len(service.inputs)}
Outputs: {len(service.outputs)}
QoS:
- Reliability: {service.qos.reliability}%
- Availability: {service.qos.availability}%
- Response Time: {service.qos.response_time}ms
- Compliance: {service.qos.compliance}%
- Best Practices: {service.qos.best_practices}%
Compatible services: {len(compatible_services)}

Respond ONLY with JSON (no markdown, no explanation):
{{"""

        json_parts = []
        if need_interaction:
            json_parts.append(f'"interaction": {{"role": "orchestrator" or "worker" or "aggregator", "can_call_count": number (0-{min(len(compatible_services), 5)}), "collaboration_level": "high" or "medium" or "low"}}')
        if need_context:
            json_parts.append('"context": {"context_aware": true or false, "location_sensitive": true or false, "time_critical": "high" or "medium" or "low"}')
        if need_policy:
            json_parts.append('"policy": {"gdpr_compliant": true or false, "security_level": "high" or "medium" or "low", "data_retention_days": 30 or 90 or 180 or 365, "encryption_required": true or false, "data_classification": "public" or "internal" or "confidential"}')

        prompt += ', '.join(json_parts) + '}'
        self.log.debug("    PROMPT (len=%d):\n%s", len(prompt), prompt)

        try:
            t_call = time.perf_counter()
            response = self._call_ollama(prompt)
            t_resp = time.perf_counter()
            self.log.info("    Ollama response received in %.3f s  (len=%d)", t_resp - t_call, len(response) if response else 0)
            self.log.debug("    RAW RESPONSE:\n%s", response)
            data = self._extract_json(response)
            self.log.debug("    Parsed JSON: %s", json.dumps(data, default=str) if data else "NONE")
            if data:
                # --- Interaction ---
                if need_interaction:
                    i_data = data.get('interaction', data)  # fallback to flat if no nesting
                    interaction = InteractionAnnotation()
                    interaction.role = {'orchestrator': 'orchestrator', 'worker': 'worker', 'aggregator': 'aggregator'}.get(
                        str(i_data.get('role', '')).lower(), 'worker'
                    )
                    n = min(i_data.get('can_call_count', 3), len(compatible_services))
                    top = sorted(compatible_services, key=lambda x: x['match_score'], reverse=True)
                    interaction.can_call = [s['id'] for s in top[:n]]
                    interaction.collaboration_associations = interaction.can_call.copy()
                    collab_counts = self.history_store.get_collaboration_counts(service.id)
                    interaction.collaboration_history = {
                        sid: collab_counts.get(sid, 0)
                        for sid in interaction.can_call[:10]
                    }
                    annotation.interaction = interaction
                    self.log.debug("    LLM Interaction: role=%s  can_call=%d  collab_history=%d",
                                   interaction.role, len(interaction.can_call), len(interaction.collaboration_history))

                # --- Context ---
                if need_context:
                    c_data = data.get('context', data)
                    ctx = ContextAnnotation()
                    ctx.context_aware = c_data.get('context_aware', False)
                    ctx.location_sensitive = c_data.get('location_sensitive', False)
                    ctx.time_critical = c_data.get('time_critical', 'medium')
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
                    annotation.context = ctx
                    self.log.debug("    LLM Context: aware=%s  loc_sensitive=%s  time_critical=%s  interaction_count=%d  env_reqs=%s",
                                   ctx.context_aware, ctx.location_sensitive, ctx.time_critical, ctx.interaction_count, env_reqs)

                # --- Policy ---
                if need_policy:
                    p_data = data.get('policy', data)
                    policy = PolicyAnnotation()
                    policy.gdpr_compliant = p_data.get('gdpr_compliant', True)
                    policy.security_level = p_data.get('security_level', 'medium')
                    policy.data_retention_days = p_data.get('data_retention_days', 30)
                    policy.encryption_required = p_data.get('encryption_required', False)
                    policy.data_classification = p_data.get('data_classification', 'internal')
                    policy.privacy_policy = "encrypted" if policy.encryption_required else "standard"
                    if service.qos.compliance > 85:
                        policy.compliance_standards = ["ISO27001", "SOC2"]
                    elif service.qos.compliance > 70:
                        policy.compliance_standards = ["ISO27001"]
                    annotation.policy = policy
                    self.log.debug("    LLM Policy: gdpr=%s  security=%s  retention=%dd  encryption=%s  classification=%s  standards=%s",
                                   policy.gdpr_compliant, policy.security_level, policy.data_retention_days,
                                   policy.encryption_required, policy.data_classification,
                                   policy.compliance_standards if hasattr(policy, 'compliance_standards') else [])
            else:
                raise ValueError("LLM returned no parseable JSON")

            self.log.info("    _annotate_with_llm(%s) SUCCESS in %.3f s", service.id, time.perf_counter() - t_llm)

        except Exception as e:
            self.log.warning("    LLM FALLBACK for %s: %s — reverting to classic annotation", service.id, e)
            if need_interaction:
                annotation.interaction = self._generate_interaction_annotations(service)
                self.log.debug("    Fallback interaction: role=%s  can_call=%d", annotation.interaction.role, len(annotation.interaction.can_call))
            if need_context:
                annotation.context = self._generate_context_annotations(service)
                self.log.debug("    Fallback context: aware=%s  adaptation_score=%.3f", annotation.context.context_aware, annotation.context.context_adaptation_score)
            if need_policy:
                annotation.policy = self._generate_policy_annotations(service)
                self.log.debug("    Fallback policy: gdpr=%s  security=%s", annotation.policy.gdpr_compliant, annotation.policy.security_level)
            self.log.info("    _annotate_with_llm(%s) FALLBACK COMPLETE in %.3f s", service.id, time.perf_counter() - t_llm)

        return annotation

    # ====================================================================
    #  OLLAMA HELPERS
    # ====================================================================
    def _call_ollama(self, prompt):
        self.log.debug("    _call_ollama: POST %s/api/generate  model=%s  prompt_len=%d", self.ollama_url, self.model, len(prompt))
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False, "options": {"temperature": 0.3, "top_p": 0.9}},
                timeout=30,
            )
            self.log.debug("    _call_ollama: HTTP %d  response_len=%d", response.status_code, len(response.text))
            if response.status_code == 200:
                return response.json()['response']
            self.log.error("    _call_ollama: non-200 status %d  body=%s", response.status_code, response.text[:500])
            raise Exception(f"Ollama API error: {response.status_code}")
        except requests.exceptions.ConnectionError as ce:
            self.log.error("    _call_ollama: ConnectionError — %s", ce)
            raise Exception("Cannot connect to Ollama. Is it running?")
        except Exception as e:
            self.log.error("    _call_ollama: Exception — %s", e)
            raise Exception(f"Ollama error: {str(e)}")

    def _extract_json(self, text):
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                json_str = text[start:end]
                self.log.debug("    _extract_json: extracted chars [%d:%d] (len=%d)", start, end, len(json_str))
                parsed = json.loads(json_str)
                self.log.debug("    _extract_json: parsed OK  keys=%s", list(parsed.keys()) if isinstance(parsed, dict) else type(parsed).__name__)
                return parsed
            self.log.warning("    _extract_json: no JSON braces found in response (len=%d)", len(text) if text else 0)
            return None
        except Exception as je:
            self.log.error("    _extract_json: JSON parse error — %s  text_snippet=%s", je, text[:200] if text else '')
            return None
