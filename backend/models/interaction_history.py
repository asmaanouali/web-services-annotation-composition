"""
Magasin d'historique des interactions de services.

Enregistre chaque invocation / composition réelle et fournit
des méthodes d'agrégation utilisées par l'annotateur pour produire
des annotations **basées sur l'historique**, et non synthétiques.

Persistance : fichier JSON local (interaction_history.json).
"""

import json
import os
import threading
from collections import defaultdict
from datetime import datetime, timedelta


_HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "interaction_history.json"
)


class InteractionRecord:
    """Un enregistrement d'interaction unique."""
    __slots__ = (
        "timestamp", "composition_id", "service_id",
        "co_services", "success", "utility",
        "context", "response_time_ms",
    )

    def __init__(
        self,
        service_id: str,
        composition_id: str = "",
        co_services: list = None,
        success: bool = True,
        utility: float = 0.0,
        context: dict = None,
        response_time_ms: float = 0.0,
        timestamp: str = None,
    ):
        self.timestamp = timestamp or datetime.utcnow().isoformat()
        self.composition_id = composition_id
        self.service_id = service_id
        self.co_services = co_services or []
        self.success = success
        self.utility = utility
        self.context = context or {}
        self.response_time_ms = response_time_ms

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "composition_id": self.composition_id,
            "service_id": self.service_id,
            "co_services": self.co_services,
            "success": self.success,
            "utility": self.utility,
            "context": self.context,
            "response_time_ms": self.response_time_ms,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            service_id=d["service_id"],
            composition_id=d.get("composition_id", ""),
            co_services=d.get("co_services", []),
            success=d.get("success", True),
            utility=d.get("utility", 0.0),
            context=d.get("context", {}),
            response_time_ms=d.get("response_time_ms", 0.0),
            timestamp=d.get("timestamp"),
        )


class InteractionHistoryStore:
    """
    Magasin thread-safe pour l'historique des interactions.

    Usage typique :
        store = InteractionHistoryStore()
        store.record(InteractionRecord(service_id="s1", ...))
        stats = store.get_service_stats("s1")
    """

    def __init__(self, path: str = None):
        self._path = path or _HISTORY_FILE
        self._lock = threading.Lock()
        self._records: list[InteractionRecord] = []
        # Caches invalidés à chaque record()
        self._collaboration_cache: dict | None = None
        self._interaction_count_cache: dict | None = None
        self._success_rate_cache: dict | None = None
        self._last_used_cache: dict | None = None
        self._usage_pattern_cache: dict | None = None
        self._context_cache: dict | None = None
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._records = [InteractionRecord.from_dict(d) for d in data]
            except Exception:
                self._records = []

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in self._records], f, indent=2)
        except Exception as exc:
            print(f"[InteractionHistoryStore] save error: {exc}")

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------
    def record(self, rec: InteractionRecord):
        """Enregistre une interaction et invalide les caches."""
        with self._lock:
            self._records.append(rec)
            self._invalidate_caches()
            self._save()

    def record_composition(
        self,
        composition_id: str,
        service_ids: list,
        success: bool,
        utility: float,
        context: dict = None,
        response_time_ms: float = 0.0,
    ):
        """Enregistre toutes les interactions d'une composition d'un coup."""
        now = datetime.utcnow().isoformat()
        with self._lock:
            for sid in service_ids:
                others = [s for s in service_ids if s != sid]
                self._records.append(
                    InteractionRecord(
                        service_id=sid,
                        composition_id=composition_id,
                        co_services=others,
                        success=success,
                        utility=utility,
                        context=context or {},
                        response_time_ms=response_time_ms,
                        timestamp=now,
                    )
                )
            self._invalidate_caches()
            self._save()

    def import_from_training(self, training_examples: list):
        """Importe l'historique à partir des données d'entraînement (best solutions).

        Permet de démarrer avec un historique non-vide même avant
        la première composition réelle.
        """
        with self._lock:
            for ex in training_examples:
                best = ex.get("best_solution")
                if not best:
                    continue
                sids = best.get("service_ids") or []
                if not sids and best.get("service_id"):
                    sids = [best["service_id"]]
                if not sids:
                    continue
                utility = best.get("utility", 0.0)
                req = ex.get("request", {})
                comp_id = req.get("id", "")
                now = datetime.utcnow().isoformat()
                for sid in sids:
                    others = [s for s in sids if s != sid]
                    self._records.append(
                        InteractionRecord(
                            service_id=sid,
                            composition_id=comp_id,
                            co_services=others,
                            success=True,
                            utility=utility,
                            context={},
                            response_time_ms=0.0,
                            timestamp=now,
                        )
                    )
            self._invalidate_caches()
            self._save()

    # ------------------------------------------------------------------
    # Caches
    # ------------------------------------------------------------------
    def _invalidate_caches(self):
        self._collaboration_cache = None
        self._interaction_count_cache = None
        self._success_rate_cache = None
        self._last_used_cache = None
        self._usage_pattern_cache = None
        self._context_cache = None

    # ------------------------------------------------------------------
    # Query helpers (used by annotator)
    # ------------------------------------------------------------------
    def get_interaction_count(self, service_id: str) -> int:
        """Nombre total d'invocations enregistrées pour ce service."""
        if self._interaction_count_cache is None:
            cache = defaultdict(int)
            for r in self._records:
                cache[r.service_id] += 1
            self._interaction_count_cache = dict(cache)
        return self._interaction_count_cache.get(service_id, 0)

    def get_collaboration_counts(self, service_id: str) -> dict:
        """Retourne {other_service_id: count} — combien de fois
        chaque paire a été composée ensemble."""
        if self._collaboration_cache is None:
            cache = defaultdict(lambda: defaultdict(int))
            for r in self._records:
                for co in r.co_services:
                    cache[r.service_id][co] += 1
            self._collaboration_cache = {k: dict(v) for k, v in cache.items()}
        return self._collaboration_cache.get(service_id, {})

    def get_success_rate(self, service_id: str) -> float:
        """Taux de succès (0.0 – 1.0) du service dans les compositions."""
        if self._success_rate_cache is None:
            totals = defaultdict(int)
            successes = defaultdict(int)
            for r in self._records:
                totals[r.service_id] += 1
                if r.success:
                    successes[r.service_id] += 1
            self._success_rate_cache = {
                sid: successes[sid] / totals[sid] if totals[sid] else 0.0
                for sid in totals
            }
        return self._success_rate_cache.get(service_id, 0.0)

    def get_avg_utility(self, service_id: str) -> float:
        """Utilité moyenne observée quand ce service est impliqué."""
        utils = [r.utility for r in self._records if r.service_id == service_id and r.utility > 0]
        return sum(utils) / len(utils) if utils else 0.0

    def get_last_used(self, service_id: str) -> str | None:
        """Timestamp ISO de la dernière utilisation."""
        if self._last_used_cache is None:
            cache = {}
            for r in self._records:
                prev = cache.get(r.service_id)
                if prev is None or r.timestamp > prev:
                    cache[r.service_id] = r.timestamp
            self._last_used_cache = cache
        return self._last_used_cache.get(service_id)

    def get_usage_patterns(self, service_id: str) -> list:
        """Déduit les patterns d'utilisation réels (heures, jours)."""
        if self._usage_pattern_cache is None:
            self._usage_pattern_cache = {}

        if service_id in self._usage_pattern_cache:
            return self._usage_pattern_cache[service_id]

        hours = defaultdict(int)
        weekdays = defaultdict(int)
        for r in self._records:
            if r.service_id != service_id:
                continue
            try:
                dt = datetime.fromisoformat(r.timestamp)
                hours[dt.hour] += 1
                weekdays[dt.weekday()] += 1
            except Exception:
                pass

        patterns = []
        if hours:
            peak_hour = max(hours, key=hours.get)
            if 6 <= peak_hour <= 11:
                patterns.append("peak_hours_morning")
            elif 12 <= peak_hour <= 17:
                patterns.append("peak_hours_afternoon")
            elif 18 <= peak_hour <= 23:
                patterns.append("peak_hours_evening")
            else:
                patterns.append("peak_hours_night")

        if weekdays:
            wd_total = sum(weekdays.get(d, 0) for d in range(5))
            we_total = sum(weekdays.get(d, 0) for d in (5, 6))
            if wd_total > we_total * 2:
                patterns.append("business_days")
            elif we_total > wd_total:
                patterns.append("weekend_heavy")
            else:
                patterns.append("uniform_weekly")

        self._usage_pattern_cache[service_id] = patterns
        return patterns

    def get_observed_contexts(self, service_id: str) -> dict:
        """Agrège les contextes observés pour un service.

        Retourne un résumé:
        {
            "locations": {"Paris": 10, "London": 5, ...},
            "networks": {"4G": 8, "wifi": 12, ...},
            "device_types": {"mobile": 5, "desktop": 15, ...},
            "total_with_context": 20
        }
        """
        if self._context_cache is None:
            self._context_cache = {}

        if service_id in self._context_cache:
            return self._context_cache[service_id]

        locations = defaultdict(int)
        networks = defaultdict(int)
        devices = defaultdict(int)
        total_with_ctx = 0

        for r in self._records:
            if r.service_id != service_id or not r.context:
                continue
            total_with_ctx += 1
            loc = r.context.get("location")
            if loc:
                locations[loc] += 1
            net = r.context.get("network_type")
            if net:
                networks[net] += 1
            dev = r.context.get("device_type")
            if dev:
                devices[dev] += 1

        result = {
            "locations": dict(locations),
            "networks": dict(networks),
            "device_types": dict(devices),
            "total_with_context": total_with_ctx,
        }
        self._context_cache[service_id] = result
        return result

    # ------------------------------------------------------------------
    # Bulk stats (used by annotator.annotate_all)
    # ------------------------------------------------------------------
    def get_all_stats(self) -> dict:
        """Retourne toutes les stats pré-calculées en un seul appel.

        {
            'interaction_counts': {sid: int, ...},
            'collaboration_counts': {sid: {other: int, ...}, ...},
            'success_rates': {sid: float, ...},
            'last_used': {sid: iso_str, ...},
            'avg_utilities': {sid: float, ...},
        }
        """
        # Force cache build
        _ = self.get_interaction_count("__dummy__")
        _ = self.get_collaboration_counts("__dummy__")
        _ = self.get_success_rate("__dummy__")
        _ = self.get_last_used("__dummy__")

        # Avg utility (not cached, compute once here)
        util_sums = defaultdict(float)
        util_counts = defaultdict(int)
        for r in self._records:
            if r.utility > 0:
                util_sums[r.service_id] += r.utility
                util_counts[r.service_id] += 1
        avg_utils = {
            sid: util_sums[sid] / util_counts[sid]
            for sid in util_counts
        }

        return {
            "interaction_counts": dict(self._interaction_count_cache or {}),
            "collaboration_counts": dict(self._collaboration_cache or {}),
            "success_rates": dict(self._success_rate_cache or {}),
            "last_used": dict(self._last_used_cache or {}),
            "avg_utilities": avg_utils,
        }

    @property
    def total_records(self) -> int:
        return len(self._records)

    @property
    def has_history(self) -> bool:
        return len(self._records) > 0

    def clear(self):
        """Supprime tout l'historique (utile pour les tests)."""
        with self._lock:
            self._records.clear()
            self._invalidate_caches()
            self._save()

    def summary(self) -> dict:
        """Résumé rapide pour l'API /status."""
        unique_services = set(r.service_id for r in self._records)
        unique_compositions = set(r.composition_id for r in self._records if r.composition_id)
        return {
            "total_records": len(self._records),
            "unique_services": len(unique_services),
            "unique_compositions": len(unique_compositions),
            "has_history": self.has_history,
        }
