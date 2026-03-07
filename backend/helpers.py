"""
Shared helper functions used across multiple route modules.

Extracted here to avoid duplication (DRY principle) and keep route
files focused on request handling.
"""

import os
import tempfile
import threading
import traceback


def parse_xml_upload(file_obj, parser_fn):
    """Write an uploaded file to a temp file, parse it, and clean up.

    Args:
        file_obj:   Werkzeug FileStorage from ``request.files``
        parser_fn:  callable(filepath) -> parsed result

    Returns:
        The result of ``parser_fn(filepath)``.
    """
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".xml", delete=False) as tmp:
        content = file_obj.read()
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = tmp.name

    try:
        print(f"Parsing from temp file: {tmp_path} ({os.path.getsize(tmp_path)} bytes)")
        return parser_fn(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def generate_enriched_wsdl(service):
    """Generate an enriched WSDL/XML with social annotations."""

    # Start with original WSDL if available
    if service.wsdl_content:
        original_lines = service.wsdl_content.split("\n")
        definitions_closing_index = -1
        for i in range(len(original_lines) - 1, -1, -1):
            if "</definitions>" in original_lines[i]:
                definitions_closing_index = i
                break

        if definitions_closing_index > 0:
            xml_lines = original_lines[:definitions_closing_index]
            xml_lines.append("")
            xml_lines.append(
                "  <!-- ========== Social Annotations Extension ========== -->"
            )
        else:
            xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
            xml_lines.append(f'<definitions xmlns="http://schemas.xmlsoap.org/wsdl/"')
            xml_lines.append(
                '             xmlns:social="http://social-ws/annotations"'
            )
            xml_lines.append(f'             name="{service.id}">')
    else:
        xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_lines.append(f'<definitions xmlns="http://schemas.xmlsoap.org/wsdl/"')
        xml_lines.append('             xmlns:social="http://social-ws/annotations"')
        xml_lines.append(f'             name="{service.id}">')
        xml_lines.append("")
        xml_lines.append(
            "  <!-- ========== Basic Service Description ========== -->"
        )
        xml_lines.append("  <types>")
        xml_lines.append(
            '    <xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
        )
        for inp in service.inputs:
            xml_lines.append(f'      <xsd:element name="{inp}" type="xsd:string"/>')
        for out in service.outputs:
            xml_lines.append(f'      <xsd:element name="{out}" type="xsd:string"/>')
        xml_lines.append("    </xsd:schema>")
        xml_lines.append("  </types>")

    # QoS extension
    xml_lines.append("")
    xml_lines.append("  <!-- ========== QoS Properties ========== -->")
    xml_lines.append("  <social:QoS>")
    qos_dict = (
        service.qos.to_dict()
        if hasattr(service.qos, "to_dict")
        else (service.qos if isinstance(service.qos, dict) else vars(service.qos))
    )
    for key, value in qos_dict.items():
        xml_lines.append(f"    <social:{key}>{value:.2f}</social:{key}>")
    xml_lines.append("  </social:QoS>")
    xml_lines.append("")

    # Social annotations
    if hasattr(service, "annotations") and service.annotations:
        xml_lines.append("  <!-- ========== Social Annotations ========== -->")
        annotations = service.annotations
        social_node = annotations.social_node

        xml_lines.append("  <social:SocialNode>")
        xml_lines.append(f"    <social:nodeId>{social_node.node_id}</social:nodeId>")
        xml_lines.append(
            f"    <social:nodeType>{social_node.node_type}</social:nodeType>"
        )
        xml_lines.append(f"    <social:state>{social_node.state}</social:state>")
        xml_lines.append("")

        xml_lines.append("    <social:NodeProperties>")
        xml_lines.append(
            f"      <social:trustDegree>{social_node.trust_degree.value:.3f}"
            f"</social:trustDegree>"
        )
        xml_lines.append(
            f"      <social:reputation>{social_node.reputation.value:.3f}"
            f"</social:reputation>"
        )
        xml_lines.append(
            f"      <social:cooperativeness>{social_node.cooperativeness.value:.3f}"
            f"</social:cooperativeness>"
        )
        for prop in social_node.properties:
            xml_lines.append(
                f'      <social:property name="{prop.prop_name}" '
                f'value="{prop.value:.3f}"/>'
            )
        xml_lines.append("    </social:NodeProperties>")
        xml_lines.append("")

        if social_node.associations:
            xml_lines.append("    <social:Associations>")
            for assoc in social_node.associations:
                xml_lines.append("      <social:Association>")
                xml_lines.append(
                    f"        <social:sourceNode>{assoc.source_node}</social:sourceNode>"
                )
                xml_lines.append(
                    f"        <social:targetNode>{assoc.target_node}</social:targetNode>"
                )
                xml_lines.append(
                    f"        <social:type>{assoc.association_type.type_name}</social:type>"
                )
                xml_lines.append(
                    f"        <social:weight>{assoc.association_weight.value:.3f}"
                    f"</social:weight>"
                )
                xml_lines.append("      </social:Association>")
            xml_lines.append("    </social:Associations>")

        xml_lines.append("  </social:SocialNode>")
        xml_lines.append("")

        # Interaction annotations
        xml_lines.append("  <social:Interaction>")
        inter = annotations.interaction
        inter_dict = (
            inter.to_dict()
            if hasattr(inter, "to_dict")
            else (inter if isinstance(inter, dict) else {"role": "worker"})
        )
        xml_lines.append(
            f'    <social:role>{inter_dict.get("role", "worker")}</social:role>'
        )
        if inter_dict.get("collaboration_associations"):
            xml_lines.append("    <social:collaborations>")
            for svc_id in inter_dict["collaboration_associations"][:5]:
                xml_lines.append(f"      <social:service>{svc_id}</social:service>")
            xml_lines.append("    </social:collaborations>")
        xml_lines.append("  </social:Interaction>")
        xml_lines.append("")

        # Context annotations
        xml_lines.append("  <social:Context>")
        ctx = annotations.context
        ctx_dict = (
            ctx.to_dict()
            if hasattr(ctx, "to_dict")
            else (ctx if isinstance(ctx, dict) else {})
        )
        xml_lines.append(
            f"    <social:contextAware>"
            f'{str(ctx_dict.get("context_aware", False)).lower()}'
            f"</social:contextAware>"
        )
        xml_lines.append(
            f'    <social:timeCritical>{ctx_dict.get("time_critical", "low")}'
            f"</social:timeCritical>"
        )
        xml_lines.append(
            f'    <social:interactionCount>{ctx_dict.get("interaction_count", 0)}'
            f"</social:interactionCount>"
        )
        xml_lines.append("  </social:Context>")
        xml_lines.append("")

        # Policy annotations
        xml_lines.append("  <social:Policy>")
        pol = annotations.policy
        pol_dict = (
            pol.to_dict()
            if hasattr(pol, "to_dict")
            else (pol if isinstance(pol, dict) else {})
        )
        xml_lines.append(
            f"    <social:gdprCompliant>"
            f'{str(pol_dict.get("gdpr_compliant", True)).lower()}'
            f"</social:gdprCompliant>"
        )
        xml_lines.append(
            f'    <social:securityLevel>{pol_dict.get("security_level", "medium")}'
            f"</social:securityLevel>"
        )
        xml_lines.append(
            f"    <social:dataRetentionDays>"
            f'{pol_dict.get("data_retention_days", 30)}'
            f"</social:dataRetentionDays>"
        )
        xml_lines.append("  </social:Policy>")

    xml_lines.append("")
    xml_lines.append("</definitions>")
    return "\n".join(xml_lines)


def calculate_statistics(comparisons):
    """Calculate global statistics for classic vs LLM comparison."""
    stats = {
        "classic": {
            "success_rate": 0, "avg_utility": 0, "avg_time": 0,
            "max_utility": 0, "min_utility": 0,
            "total_composed": 0, "avg_services_used": 0, "avg_states_explored": 0,
        },
        "llm": {
            "success_rate": 0, "avg_utility": 0, "avg_time": 0,
            "max_utility": 0, "min_utility": 0,
            "total_composed": 0, "avg_services_used": 0,
        },
        "comparison": {
            "classic_wins": 0, "llm_wins": 0, "ties": 0,
            "avg_utility_gap": 0, "avg_time_ratio": 0,
        },
    }

    classic_results = [
        c["classic"] for c in comparisons
        if c["classic"] and c["classic"].get("success")
    ]
    llm_results = [
        c["llm"] for c in comparisons
        if c["llm"] and c["llm"].get("success")
    ]

    if classic_results:
        utilities = [r["utility_value"] for r in classic_results]
        n = len(classic_results)
        stats["classic"]["success_rate"] = n / max(len(comparisons), 1) * 100
        stats["classic"]["avg_utility"] = sum(utilities) / n
        stats["classic"]["max_utility"] = max(utilities)
        stats["classic"]["min_utility"] = min(utilities)
        stats["classic"]["avg_time"] = sum(
            r["computation_time"] for r in classic_results
        ) / n
        stats["classic"]["total_composed"] = n
        stats["classic"]["avg_services_used"] = sum(
            len(r.get("services", [])) for r in classic_results
        ) / n
        stats["classic"]["avg_states_explored"] = sum(
            r.get("states_explored", 0) for r in classic_results
        ) / n

    if llm_results:
        utilities = [r["utility_value"] for r in llm_results]
        n = len(llm_results)
        stats["llm"]["success_rate"] = n / max(len(comparisons), 1) * 100
        stats["llm"]["avg_utility"] = sum(utilities) / n
        stats["llm"]["max_utility"] = max(utilities)
        stats["llm"]["min_utility"] = min(utilities)
        stats["llm"]["avg_time"] = sum(
            r["computation_time"] for r in llm_results
        ) / n
        stats["llm"]["total_composed"] = n
        stats["llm"]["avg_services_used"] = sum(
            len(r.get("services", [])) for r in llm_results
        ) / n

    # Head-to-head
    for comp in comparisons:
        c, l = comp["classic"], comp["llm"]
        if c and l and c.get("success") and l.get("success"):
            cu, lu = c["utility_value"], l["utility_value"]
            if cu > lu:
                stats["comparison"]["classic_wins"] += 1
            elif lu > cu:
                stats["comparison"]["llm_wins"] += 1
            else:
                stats["comparison"]["ties"] += 1

    if stats["classic"]["avg_utility"] > 0 and stats["llm"]["avg_utility"] > 0:
        stats["comparison"]["avg_utility_gap"] = (
            stats["llm"]["avg_utility"] - stats["classic"]["avg_utility"]
        )
    if stats["classic"]["avg_time"] > 0 and stats["llm"]["avg_time"] > 0:
        stats["comparison"]["avg_time_ratio"] = (
            stats["llm"]["avg_time"] / stats["classic"]["avg_time"]
        )

    return stats


# ── Formal evaluation metrics (precision, recall, F1 vs best-known) ──


def _extract_service_ids(result):
    """Extract a set of service IDs from a composition result dict."""
    if not result:
        return set()
    # result["services"] is a list of service-ID strings (from .to_dict())
    sids = result.get("services", [])
    if not sids:
        wf = result.get("workflow", [])
        if wf:
            sids = wf
    return set(sids)


def _single_request_metrics(composed_ids, best_ids, composed_utility, best_utility):
    """Compute precision, recall, F1, exact-match, utility-ratio, Jaccard
    for a single request.

    Returns a dict of floats (all in [0, 1] except utility_ratio which
    can exceed 1 if composed is better than reference).
    """
    if not composed_ids and not best_ids:
        return {
            "precision": 1.0, "recall": 1.0, "f1": 1.0,
            "exact_match": 1.0, "utility_ratio": 1.0, "jaccard": 1.0,
        }
    if not composed_ids:
        return {
            "precision": 0.0, "recall": 0.0, "f1": 0.0,
            "exact_match": 0.0, "utility_ratio": 0.0, "jaccard": 0.0,
        }
    if not best_ids:
        # No ground truth — cannot evaluate
        return None

    tp = len(composed_ids & best_ids)
    precision = tp / len(composed_ids) if composed_ids else 0.0
    recall = tp / len(best_ids) if best_ids else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    exact_match = 1.0 if composed_ids == best_ids else 0.0
    union = composed_ids | best_ids
    jaccard = tp / len(union) if union else 0.0

    if best_utility and best_utility > 0:
        utility_ratio = composed_utility / best_utility
    else:
        utility_ratio = 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "exact_match": exact_match,
        "utility_ratio": round(utility_ratio, 4),
        "jaccard": round(jaccard, 4),
    }


def calculate_formal_metrics(comparisons):
    """Compute formal evaluation metrics (precision, recall, F1, etc.)
    for classic and LLM compositions against best-known solutions.

    Args:
        comparisons: list of dicts, each with keys:
            "request_id", "best_known", "classic", "llm"

    Returns:
        dict with per-method aggregated metrics and per-request detail,
        or None if no best-known solutions are available.
    """
    classic_metrics = []
    llm_metrics = []
    per_request = []

    has_any_best = False

    for comp in comparisons:
        best = comp.get("best_known")
        if not best:
            continue

        has_any_best = True
        best_ids = set(best.get("service_ids", []))
        best_utility = best.get("utility", 0.0)

        entry = {"request_id": comp["request_id"]}

        # ── Classic vs best ──
        classic = comp.get("classic")
        if classic and classic.get("success"):
            c_ids = _extract_service_ids(classic)
            c_util = classic.get("utility_value", 0.0)
            m = _single_request_metrics(c_ids, best_ids, c_util, best_utility)
            if m:
                classic_metrics.append(m)
                entry["classic"] = m
        else:
            entry["classic"] = None

        # ── LLM vs best ──
        llm = comp.get("llm")
        if llm and llm.get("success"):
            l_ids = _extract_service_ids(llm)
            l_util = llm.get("utility_value", 0.0)
            m = _single_request_metrics(l_ids, best_ids, l_util, best_utility)
            if m:
                llm_metrics.append(m)
                entry["llm"] = m
        else:
            entry["llm"] = None

        per_request.append(entry)

    if not has_any_best:
        return None

    def _aggregate(metrics_list):
        if not metrics_list:
            return {
                "macro_precision": 0.0, "macro_recall": 0.0, "macro_f1": 0.0,
                "exact_match_rate": 0.0, "mean_utility_ratio": 0.0,
                "mean_jaccard": 0.0, "evaluated_requests": 0,
            }
        n = len(metrics_list)
        return {
            "macro_precision": round(sum(m["precision"] for m in metrics_list) / n, 4),
            "macro_recall": round(sum(m["recall"] for m in metrics_list) / n, 4),
            "macro_f1": round(sum(m["f1"] for m in metrics_list) / n, 4),
            "exact_match_rate": round(sum(m["exact_match"] for m in metrics_list) / n, 4),
            "mean_utility_ratio": round(sum(m["utility_ratio"] for m in metrics_list) / n, 4),
            "mean_jaccard": round(sum(m["jaccard"] for m in metrics_list) / n, 4),
            "evaluated_requests": n,
        }

    return {
        "classic": _aggregate(classic_metrics),
        "llm": _aggregate(llm_metrics),
        "per_request": per_request,
        "total_with_ground_truth": sum(1 for c in comparisons if c.get("best_known")),
    }


# ── Analytical discussion generator ────────────────────────────────
def generate_comparison_discussion(statistics, formal_metrics=None, training_impact=None):
    """Generate a structured analytical discussion comparing Solution A
    (classic) vs Solution B (LLM) based on computed statistics and metrics.

    Returns a dict with 'sections' (list of {title, paragraphs}) and
    a 'summary' string.
    """
    sections = []
    cs = statistics.get("classic", {})
    ls = statistics.get("llm", {})
    comp = statistics.get("comparison", {})

    # ── 1. Overall Performance ──
    c_util = cs.get("avg_utility", 0)
    l_util = ls.get("avg_utility", 0)
    gap = comp.get("avg_utility_gap", 0)
    c_sr = cs.get("success_rate", 0)
    l_sr = ls.get("success_rate", 0)

    perf_paragraphs = []
    if c_util > 0 or l_util > 0:
        if abs(gap) < 0.5:
            perf_paragraphs.append(
                f"Both approaches achieve comparable average utility scores "
                f"(Classic: {c_util:.2f}, LLM: {l_util:.2f}, gap: {gap:+.2f}). "
                f"This suggests that for this dataset, the classic algorithmic "
                f"approach is competitive with the LLM-based approach in terms "
                f"of solution quality."
            )
        elif gap > 0:
            perf_paragraphs.append(
                f"The LLM-based approach (Solution B) outperforms the classic "
                f"approach (Solution A) with an average utility of {l_util:.2f} "
                f"vs {c_util:.2f} (improvement: {gap:+.2f}). The LLM benefits "
                f"from pattern recognition in training data and social trust "
                f"annotations to make more informed service selections."
            )
        else:
            perf_paragraphs.append(
                f"The classic approach (Solution A) outperforms the LLM-based "
                f"approach (Solution B) with an average utility of {c_util:.2f} "
                f"vs {l_util:.2f} (gap: {gap:+.2f}). The exhaustive search "
                f"strategies (Dijkstra/A*) guarantee optimality within the "
                f"explored search space, which can surpass heuristic LLM "
                f"selections."
            )

    sr_diff = l_sr - c_sr
    if abs(sr_diff) > 5:
        winner = "LLM" if sr_diff > 0 else "Classic"
        perf_paragraphs.append(
            f"Success rates differ noticeably: Classic {c_sr:.1f}% vs "
            f"LLM {l_sr:.1f}%. {winner} achieves higher reliability "
            f"in finding valid compositions."
        )
    else:
        perf_paragraphs.append(
            f"Both approaches have similar success rates "
            f"(Classic: {c_sr:.1f}%, LLM: {l_sr:.1f}%), indicating "
            f"comparable robustness in finding valid compositions."
        )

    sections.append({"title": "Overall Performance", "paragraphs": perf_paragraphs})

    # ── 2. Execution Time Trade-off ──
    c_time = cs.get("avg_time", 0)
    l_time = ls.get("avg_time", 0)
    time_paragraphs = []

    if c_time > 0 and l_time > 0:
        ratio = l_time / max(c_time, 0.0001)
        if ratio > 5:
            time_paragraphs.append(
                f"The LLM approach is significantly slower "
                f"(avg {l_time*1000:.0f}ms vs {c_time*1000:.0f}ms), "
                f"primarily due to LLM inference overhead. For latency-"
                f"sensitive applications, the classic approach is preferable. "
                f"However, the LLM provides richer explanations and "
                f"context-aware reasoning that justify the extra cost in "
                f"scenarios where interpretability matters."
            )
        elif ratio > 1.5:
            time_paragraphs.append(
                f"The LLM approach is moderately slower "
                f"(avg {l_time*1000:.0f}ms vs {c_time*1000:.0f}ms). "
                f"This overhead is acceptable for most use cases and is "
                f"offset by the LLM's ability to leverage social trust "
                f"annotations and contextual adaptation."
            )
        else:
            time_paragraphs.append(
                f"Both approaches have comparable execution times "
                f"(Classic: {c_time*1000:.0f}ms, LLM: {l_time*1000:.0f}ms). "
                f"The knowledge-base driven LLM selection avoids expensive "
                f"graph traversal, achieving competitive speed."
            )

    sections.append({"title": "Execution Time Analysis", "paragraphs": time_paragraphs})

    # ── 3. Formal Metrics (if ground truth available) ──
    if formal_metrics:
        fm_classic = formal_metrics.get("classic", {})
        fm_llm = formal_metrics.get("llm", {})
        fm_paragraphs = []

        c_prec = fm_classic.get("precision", 0)
        c_rec = fm_classic.get("recall", 0)
        c_f1 = fm_classic.get("f1", 0)
        l_prec = fm_llm.get("precision", 0)
        l_rec = fm_llm.get("recall", 0)
        l_f1 = fm_llm.get("f1", 0)

        if c_f1 > 0 or l_f1 > 0:
            fm_paragraphs.append(
                f"Against the ground-truth best-known solutions: "
                f"Classic achieves Precision={c_prec:.2f}, Recall={c_rec:.2f}, "
                f"F1={c_f1:.2f}; LLM achieves Precision={l_prec:.2f}, "
                f"Recall={l_rec:.2f}, F1={l_f1:.2f}."
            )

            if l_f1 > c_f1:
                fm_paragraphs.append(
                    "The LLM approach better approximates optimal solutions, "
                    "likely because it learns service selection patterns from "
                    "training examples and can generalize to similar requests."
                )
            elif c_f1 > l_f1:
                fm_paragraphs.append(
                    "The classic approach better approximates optimal solutions, "
                    "as its exhaustive search explores more of the solution "
                    "space, whereas the LLM relies on approximate heuristics."
                )

            c_jaccard = fm_classic.get("jaccard_index", 0)
            l_jaccard = fm_llm.get("jaccard_index", 0)
            if c_jaccard > 0 or l_jaccard > 0:
                fm_paragraphs.append(
                    f"Jaccard Index (set similarity with optimal): "
                    f"Classic={c_jaccard:.2f}, LLM={l_jaccard:.2f}. "
                    f"Higher values indicate the selected services more "
                    f"closely match the ground-truth optimal set."
                )

        sections.append({"title": "Formal Evaluation Metrics", "paragraphs": fm_paragraphs})

    # ── 4. Impact of Training ──
    if training_impact:
        train_paragraphs = []
        n_examples = training_impact.get("training_examples", 0)
        is_trained = training_impact.get("is_trained", False)

        if is_trained and n_examples > 0:
            train_paragraphs.append(
                f"The LLM was trained with {n_examples} examples, enabling "
                f"few-shot learning and pattern recognition. Training provides "
                f"the LLM with knowledge of which service combinations produce "
                f"high-utility compositions, improving its selection accuracy."
            )
            perf = training_impact.get("performance_metrics", {})
            total_comps = perf.get("total_compositions", 0)
            if total_comps > 0:
                avg_u = perf.get("average_utility", 0)
                train_paragraphs.append(
                    f"Post-training, the LLM has performed {total_comps} "
                    f"compositions with an average utility of {avg_u:.2f}, "
                    f"demonstrating continuous learning from feedback."
                )
        else:
            train_paragraphs.append(
                "The LLM was not trained with example data for this evaluation. "
                "Training would likely improve the LLM's performance by providing "
                "domain-specific composition patterns. Without training, the LLM "
                "relies solely on its general reasoning capabilities and QoS-based "
                "heuristics."
            )

        sections.append({"title": "Training Impact", "paragraphs": train_paragraphs})

    # ── 5. Strengths & When to Use Each ──
    strengths_paragraphs = [
        "Solution A (Classic) excels at: exhaustive search guaranteeing "
        "optimality within the explored space, fast execution without "
        "external dependencies, deterministic and reproducible results, "
        "clear algorithmic traceability (step-by-step visualization).",

        "Solution B (LLM) excels at: leveraging social trust annotations "
        "and service reputation for selection, context-aware adaptation "
        "(network, location, temporal), explainable reasoning with "
        "natural-language justifications, continuous improvement through "
        "the QSRT pipeline (SFT → Reward Model → RL fine-tuning).",

        "Recommendation: Use the classic approach for latency-critical or "
        "deterministic scenarios. Use the LLM approach when context-awareness, "
        "explainability, and adaptive behaviour are required — especially in "
        "dynamic environments where service availability and user context "
        "change frequently."
    ]
    sections.append({"title": "Strengths & Recommendations", "paragraphs": strengths_paragraphs})

    # ── Summary ──
    if gap > 0:
        summary_winner = "LLM (Solution B)"
        summary_reason = "higher average utility and richer contextual reasoning"
    elif gap < 0:
        summary_winner = "Classic (Solution A)"
        summary_reason = "higher average utility and guaranteed optimality"
    else:
        summary_winner = "Neither (Tie)"
        summary_reason = "equivalent average utility"

    summary = (
        f"Overall winner: {summary_winner} ({summary_reason}). "
        f"The two approaches are complementary: classic composition provides "
        f"reliable algorithmic baselines, while LLM composition adds intelligence, "
        f"context-awareness, and adaptability."
    )

    return {"sections": sections, "summary": summary}


# ── Generic background-worker pattern ──────────────────────────────
def run_background_task(
    *,
    name: str,
    state_dict: dict,
    state_lock: threading.Lock,
    task_fn,
    on_success=None,
    on_error=None,
    thread_key: str = "thread",
):
    """
    Launch *task_fn* in a daemon thread while managing the common
    is_training / is_trained / error / thread pattern used throughout
    the application.

    Parameters
    ----------
    name : str
        Human-readable label for log messages (e.g. "SFT", "Annotation").
    state_dict : dict
        The mutable state dict (e.g. ``app_state["sft_state"]``).
    state_lock : threading.Lock
        Lock protecting *state_dict*.
    task_fn : callable
        Zero-argument callable that performs the long-running work.
    on_success : callable | None
        ``on_success(state_dict)`` is called (under lock) after *task_fn*
        finishes without error.  Use it to set result fields.
    on_error : callable | None
        ``on_error(state_dict, exception)`` is called (under lock) when
        *task_fn* raises.  A default handler stores the error string.
    thread_key : str
        Key in *state_dict* to store the Thread reference.

    Returns
    -------
    threading.Thread
        The started daemon thread.
    """

    def _worker():
        try:
            task_fn()
            with state_lock:
                state_dict["is_training"] = False
                state_dict["is_trained"] = True
                if on_success:
                    on_success(state_dict)
            print(f"[{name}] Background task complete")
        except Exception as exc:
            traceback.print_exc()
            with state_lock:
                state_dict["is_training"] = False
                if on_error:
                    on_error(state_dict, exc)
                else:
                    state_dict["error"] = str(exc)

    t = threading.Thread(target=_worker, daemon=True)
    with state_lock:
        state_dict["is_training"] = True
        state_dict.setdefault("error", None)
        state_dict["error"] = None
    state_dict[thread_key] = t
    t.start()
    return t
