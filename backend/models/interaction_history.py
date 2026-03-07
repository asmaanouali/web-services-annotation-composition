"""
Service interaction history store.

Records each real invocation / composition and provides
aggregation methods used by the annotator to produce
**history-based** annotations, not synthetic ones.

Persistence: local JSON file (interaction_history.json).
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
    """A single interaction record."""
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
    Thread-safe store for interaction history.

    Typical usage:
        store = InteractionHistoryStore()
        store.record(InteractionRecord(service_id="s1", ...))
        stats = store.get_service_stats("s1")
    """

    def __init__(self, path: str = None):
        self._path = path or _HISTORY_FILE
        self._lock = threading.Lock()
        self._records: list[InteractionRecord] = []
        # Caches invalidated on each record()
        self._collaboration_cache: dict | None = None
        self._interaction_count_cache: dict | None = None
        self._success_rate_cache: dict | None = None
        self._last_used_cache: dict | None = None
        self._usage_pattern_cache: dict | None = None
        self._context_cache: dict | None = None
        self._avg_utility_cache: dict | None = None
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
        """Records an interaction and invalidates caches."""
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
        """Records all interactions of a composition at once."""
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
        """Imports history from training data (best solutions).

        Allows starting with a non-empty history even before
        the first real composition.
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
        self._avg_utility_cache = None

    # ------------------------------------------------------------------
    # Query helpers (used by annotator)
    # ------------------------------------------------------------------
    def get_interaction_count(self, service_id: str) -> int:
        """Total number of recorded invocations for this service."""
        if self._interaction_count_cache is None:
            cache = defaultdict(int)
            for r in self._records:
                cache[r.service_id] += 1
            self._interaction_count_cache = dict(cache)
        return self._interaction_count_cache.get(service_id, 0)

    def get_collaboration_counts(self, service_id: str) -> dict:
        """Returns {other_service_id: count} — how many times
        each pair was composed together."""
        if self._collaboration_cache is None:
            cache = defaultdict(lambda: defaultdict(int))
            for r in self._records:
                for co in r.co_services:
                    cache[r.service_id][co] += 1
            self._collaboration_cache = {k: dict(v) for k, v in cache.items()}
        return self._collaboration_cache.get(service_id, {})

    def get_success_rate(self, service_id: str) -> float:
        """Success rate (0.0 – 1.0) of the service in compositions."""
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
        """Average observed utility when this service is involved."""
        if self._avg_utility_cache is None:
            sums = defaultdict(float)
            counts = defaultdict(int)
            for r in self._records:
                if r.utility > 0:
                    sums[r.service_id] += r.utility
                    counts[r.service_id] += 1
            self._avg_utility_cache = {
                sid: sums[sid] / counts[sid]
                for sid in counts
            }
        return self._avg_utility_cache.get(service_id, 0.0)

    def get_last_used(self, service_id: str) -> str | None:
        """ISO timestamp of the last usage."""
        if self._last_used_cache is None:
            cache = {}
            for r in self._records:
                prev = cache.get(r.service_id)
                if prev is None or r.timestamp > prev:
                    cache[r.service_id] = r.timestamp
            self._last_used_cache = cache
        return self._last_used_cache.get(service_id)

    def get_usage_patterns(self, service_id: str) -> list:
        """Infers real usage patterns (hours, days)."""
        if self._usage_pattern_cache is None:
            self._build_usage_pattern_cache()

        return self._usage_pattern_cache.get(service_id, [])

    def _build_usage_pattern_cache(self):
        """Builds the usage pattern cache for all services in a single pass."""
        hours_by_sid = defaultdict(lambda: defaultdict(int))
        weekdays_by_sid = defaultdict(lambda: defaultdict(int))
        for r in self._records:
            try:
                dt = datetime.fromisoformat(r.timestamp)
                hours_by_sid[r.service_id][dt.hour] += 1
                weekdays_by_sid[r.service_id][dt.weekday()] += 1
            except Exception:
                pass

        cache = {}
        for sid in set(hours_by_sid) | set(weekdays_by_sid):
            patterns = []
            hours = hours_by_sid.get(sid)
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

            weekdays = weekdays_by_sid.get(sid)
            if weekdays:
                wd_total = sum(weekdays.get(d, 0) for d in range(5))
                we_total = sum(weekdays.get(d, 0) for d in (5, 6))
                if wd_total > we_total * 2:
                    patterns.append("business_days")
                elif we_total > wd_total:
                    patterns.append("weekend_heavy")
                else:
                    patterns.append("uniform_weekly")

            cache[sid] = patterns
        self._usage_pattern_cache = cache

    def get_observed_contexts(self, service_id: str) -> dict:
        """Aggregates observed contexts for a service.

        Returns a summary:
        {
            "locations": {"Paris": 10, "London": 5, ...},
            "networks": {"4G": 8, "wifi": 12, ...},
            "device_types": {"mobile": 5, "desktop": 15, ...},
            "total_with_context": 20
        }
        """
        if self._context_cache is None:
            self._build_context_cache()

        return self._context_cache.get(service_id, {
            "locations": {},
            "networks": {},
            "device_types": {},
            "total_with_context": 0,
        })

    def _build_context_cache(self):
        """Builds the observed context cache for all services in a single pass."""
        locations = defaultdict(lambda: defaultdict(int))
        networks = defaultdict(lambda: defaultdict(int))
        devices = defaultdict(lambda: defaultdict(int))
        totals = defaultdict(int)
        sids_seen = set()

        for r in self._records:
            sids_seen.add(r.service_id)
            if not r.context:
                continue
            totals[r.service_id] += 1
            loc = r.context.get("location")
            if loc:
                locations[r.service_id][loc] += 1
            net = r.context.get("network_type")
            if net:
                networks[r.service_id][net] += 1
            dev = r.context.get("device_type")
            if dev:
                devices[r.service_id][dev] += 1

        cache = {}
        for sid in sids_seen:
            cache[sid] = {
                "locations": dict(locations[sid]),
                "networks": dict(networks[sid]),
                "device_types": dict(devices[sid]),
                "total_with_context": totals[sid],
            }
        self._context_cache = cache

    # ------------------------------------------------------------------
    # Bulk stats (used by annotator.annotate_all)
    # ------------------------------------------------------------------
    def get_all_stats(self) -> dict:
        """Returns all pre-computed stats in a single call.

        {
            'interaction_counts': {sid: int, ...},
            'collaboration_counts': {sid: {other: int, ...}, ...},
            'success_rates': {sid: float, ...},
            'last_used': {sid: iso_str, ...},
            'avg_utilities': {sid: float, ...},
            'observed_contexts': {sid: {...}, ...},
            'usage_patterns': {sid: [...], ...},
        }
        """
        # Force all caches to build (single pass each, idempotent)
        _ = self.get_interaction_count("__dummy__")
        _ = self.get_collaboration_counts("__dummy__")
        _ = self.get_success_rate("__dummy__")
        _ = self.get_last_used("__dummy__")
        _ = self.get_avg_utility("__dummy__")
        _ = self.get_observed_contexts("__dummy__")
        _ = self.get_usage_patterns("__dummy__")

        return {
            "interaction_counts": dict(self._interaction_count_cache or {}),
            "collaboration_counts": dict(self._collaboration_cache or {}),
            "success_rates": dict(self._success_rate_cache or {}),
            "last_used": dict(self._last_used_cache or {}),
            "avg_utilities": dict(self._avg_utility_cache or {}),
            "observed_contexts": dict(self._context_cache or {}),
            "usage_patterns": dict(self._usage_pattern_cache or {}),
        }

    @property
    def total_records(self) -> int:
        return len(self._records)

    @property
    def has_history(self) -> bool:
        return len(self._records) > 0

    def clear(self):
        """Deletes all history (useful for tests)."""
        with self._lock:
            self._records.clear()
            self._invalidate_caches()
            self._save()

    def summary(self) -> dict:
        """Quick summary for the /status API."""
        unique_services = set(r.service_id for r in self._records)
        unique_compositions = set(r.composition_id for r in self._records if r.composition_id)
        return {
            "total_records": len(self._records),
            "unique_services": len(unique_services),
            "unique_compositions": len(unique_compositions),
            "has_history": self.has_history,
        }
