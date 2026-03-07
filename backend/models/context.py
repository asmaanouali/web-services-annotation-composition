"""
Execution context model for adaptive (context-aware) services.

Captures the real context of each request:
  – Location (city, country, GPS coordinates)
  – Network (type, bandwidth, latency)
  – Temporal (hour, day, timezone)
  – Device (type, OS)
  – Current system load

This module is used by:
  1. The annotator — to enrich ContextAnnotation from
     the real history of observed contexts.
  2. The composer — to filter / weight services based on
     the current context.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


# -- Request context --

@dataclass
class LocationContext:
    """Client location information."""
    city: str = ""
    country: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    timezone: str = "UTC"

    def is_set(self) -> bool:
        return bool(self.city or self.country)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "LocationContext":
        if not d:
            return cls()
        return cls(
            city=d.get("city", ""),
            country=d.get("country", ""),
            latitude=float(d.get("latitude", 0)),
            longitude=float(d.get("longitude", 0)),
            timezone=d.get("timezone", "UTC"),
        )


@dataclass
class NetworkContext:
    """Client network conditions."""
    network_type: str = "unknown"        # wifi, 4G, 5G, 3G, ethernet, unknown
    bandwidth_mbps: float = 0.0          # estimated bandwidth
    latency_ms: float = 0.0             # network latency
    is_roaming: bool = False
    connection_quality: str = "good"      # excellent, good, fair, poor

    def is_set(self) -> bool:
        return self.network_type != "unknown"

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "NetworkContext":
        if not d:
            return cls()
        return cls(
            network_type=d.get("network_type", "unknown"),
            bandwidth_mbps=float(d.get("bandwidth_mbps", 0)),
            latency_ms=float(d.get("latency_ms", 0)),
            is_roaming=bool(d.get("is_roaming", False)),
            connection_quality=d.get("connection_quality", "good"),
        )


@dataclass
class TemporalContext:
    """Temporal context of the request."""
    timestamp: str = ""
    hour: int = 0
    weekday: int = 0             # 0=Monday … 6=Sunday
    is_business_hours: bool = True
    is_weekend: bool = False
    period: str = "morning"      # morning, afternoon, evening, night

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_now(cls) -> "TemporalContext":
        now = datetime.utcnow()
        hour = now.hour
        weekday = now.weekday()
        if 6 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 18:
            period = "afternoon"
        elif 18 <= hour < 22:
            period = "evening"
        else:
            period = "night"
        return cls(
            timestamp=now.isoformat(),
            hour=hour,
            weekday=weekday,
            is_business_hours=(9 <= hour <= 17 and weekday < 5),
            is_weekend=(weekday >= 5),
            period=period,
        )

    @classmethod
    def from_dict(cls, d: dict) -> "TemporalContext":
        if not d:
            return cls.from_now()
        return cls(
            timestamp=d.get("timestamp", ""),
            hour=int(d.get("hour", 0)),
            weekday=int(d.get("weekday", 0)),
            is_business_hours=bool(d.get("is_business_hours", True)),
            is_weekend=bool(d.get("is_weekend", False)),
            period=d.get("period", "morning"),
        )


@dataclass
class DeviceContext:
    """Client device information."""
    device_type: str = "desktop"     # mobile, tablet, desktop, iot
    os: str = ""
    screen_size: str = ""            # small, medium, large

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DeviceContext":
        if not d:
            return cls()
        return cls(
            device_type=d.get("device_type", "desktop"),
            os=d.get("os", ""),
            screen_size=d.get("screen_size", ""),
        )


@dataclass
class ExecutionContext:
    """Complete context of a composition request.

    Built from HTTP headers and/or explicit parameters
    provided in the JSON body.
    """
    location: LocationContext = field(default_factory=LocationContext)
    network: NetworkContext = field(default_factory=NetworkContext)
    temporal: TemporalContext = field(default_factory=TemporalContext)
    device: DeviceContext = field(default_factory=DeviceContext)
    # System load observed at the time of the request
    system_load: float = 0.0         # 0.0 – 1.0
    # Session identifier for tracking
    session_id: str = ""

    def to_dict(self):
        return {
            "location": self.location.to_dict(),
            "network": self.network.to_dict(),
            "temporal": self.temporal.to_dict(),
            "device": self.device.to_dict(),
            "system_load": self.system_load,
            "session_id": self.session_id,
        }

    def to_flat_dict(self) -> dict:
        """Flattened version for recording in InteractionRecord.context."""
        flat = {}
        if self.location.is_set():
            flat["location"] = self.location.city or self.location.country
            flat["country"] = self.location.country
            flat["latitude"] = self.location.latitude
            flat["longitude"] = self.location.longitude
        if self.network.is_set():
            flat["network_type"] = self.network.network_type
            flat["bandwidth_mbps"] = self.network.bandwidth_mbps
            flat["latency_ms"] = self.network.latency_ms
            flat["connection_quality"] = self.network.connection_quality
        flat["device_type"] = self.device.device_type
        flat["hour"] = self.temporal.hour
        flat["weekday"] = self.temporal.weekday
        flat["period"] = self.temporal.period
        flat["is_business_hours"] = self.temporal.is_business_hours
        flat["system_load"] = self.system_load
        return flat

    @classmethod
    def from_dict(cls, d: dict) -> "ExecutionContext":
        if not d:
            return cls(temporal=TemporalContext.from_now())
        return cls(
            location=LocationContext.from_dict(d.get("location", {})),
            network=NetworkContext.from_dict(d.get("network", {})),
            temporal=TemporalContext.from_dict(d.get("temporal", {})),
            device=DeviceContext.from_dict(d.get("device", {})),
            system_load=float(d.get("system_load", 0)),
            session_id=d.get("session_id", ""),
        )

    @classmethod
    def from_request(cls, flask_request) -> "ExecutionContext":
        """Extracts the execution context from a Flask request.

        Sources:
        1. JSON body ('context' field)
        2. HTTP headers (X-Location, X-Network-Type, User-Agent, …)
        3. Automatic inference (hour, day)
        """
        ctx = cls(temporal=TemporalContext.from_now())

        # ── From JSON body ──
        data = flask_request.get_json(silent=True) or {}
        ctx_data = data.get("context", {})
        if ctx_data:
            return cls.from_dict(ctx_data)

        # ── From HTTP headers ──
        headers = flask_request.headers

        # Location
        loc_header = headers.get("X-Location", "")
        if loc_header:
            parts = loc_header.split(",")
            ctx.location.city = parts[0].strip() if len(parts) > 0 else ""
            ctx.location.country = parts[1].strip() if len(parts) > 1 else ""

        lat = headers.get("X-Latitude")
        lon = headers.get("X-Longitude")
        if lat and lon:
            try:
                ctx.location.latitude = float(lat)
                ctx.location.longitude = float(lon)
            except ValueError:
                pass

        tz = headers.get("X-Timezone", "")
        if tz:
            ctx.location.timezone = tz

        # Network
        net_type = headers.get("X-Network-Type", "")
        if net_type:
            ctx.network.network_type = net_type
        bw = headers.get("X-Bandwidth-Mbps")
        if bw:
            try:
                ctx.network.bandwidth_mbps = float(bw)
            except ValueError:
                pass
        net_lat = headers.get("X-Network-Latency-Ms")
        if net_lat:
            try:
                ctx.network.latency_ms = float(net_lat)
            except ValueError:
                pass
        cq = headers.get("X-Connection-Quality", "")
        if cq:
            ctx.network.connection_quality = cq

        # Device
        ua = headers.get("User-Agent", "")
        if "Mobile" in ua or "Android" in ua or "iPhone" in ua:
            ctx.device.device_type = "mobile"
        elif "Tablet" in ua or "iPad" in ua:
            ctx.device.device_type = "tablet"
        else:
            ctx.device.device_type = "desktop"

        dev_type = headers.get("X-Device-Type", "")
        if dev_type:
            ctx.device.device_type = dev_type

        return ctx


# ── Adaptation helpers ───────────────────────────────────────────────

def compute_context_score(service, exec_ctx: ExecutionContext, observed_contexts: dict) -> float:
    """Computes a suitability score (0–1) between a service and the current context.

    Used by the composer to weight services during selection.

    Factors:
    - Network compatibility: a service with high response time is
      penalised on a slow network.
    - Temporal compatibility: a service regularly used at this
      time of day is favoured.
    - Location compatibility: if the service has been used from
      the same location before, bonus.
    """
    score = 0.5  # base neutre

    # ── Network compatibility ──
    if exec_ctx.network.is_set() and hasattr(service, "qos"):
        rt = service.qos.response_time
        net_quality = exec_ctx.network.connection_quality
        if net_quality == "poor":
            # Favour lightweight services (low response_time)
            score += 0.2 if rt < 100 else (-0.15 if rt > 500 else 0.0)
        elif net_quality == "excellent":
            score += 0.1  # All services are OK
        elif net_quality == "fair":
            score += 0.1 if rt < 300 else -0.05

        # Bandwidth check
        bw = exec_ctx.network.bandwidth_mbps
        if bw > 0 and rt > 0:
            # If the service has high throughput and bandwidth is low
            if bw < 5 and hasattr(service.qos, "throughput") and service.qos.throughput > 500:
                score -= 0.1

    # ── Temporal compatibility ──
    if observed_contexts and observed_contexts.get("total_with_context", 0) > 0:
        # Check if the current time period matches service usage patterns.
        # Usage patterns are strings like "peak_hours_morning", "business_days",
        # "peak_hours_afternoon", "weekend_activity", etc.
        usage_patterns = observed_contexts.get("usage_patterns", [])
        current_period = exec_ctx.temporal.period  # morning / afternoon / evening / night

        # Period match: service historically used at this time of day
        period_keywords = {
            "morning": ["morning", "business"],
            "afternoon": ["afternoon", "business"],
            "evening": ["evening"],
            "night": ["night"],
        }
        for kw in period_keywords.get(current_period, []):
            if any(kw in p for p in usage_patterns):
                score += 0.1
                break

        # Business hours match
        if exec_ctx.temporal.is_business_hours and any("business" in p for p in usage_patterns):
            score += 0.05
        elif exec_ctx.temporal.is_weekend and any("weekend" in p for p in usage_patterns):
            score += 0.05

    # ── Location compatibility ──
    if exec_ctx.location.is_set() and observed_contexts:
        known_locs = observed_contexts.get("locations", {})
        client_loc = exec_ctx.location.city or exec_ctx.location.country
        if client_loc and client_loc in known_locs:
            score += 0.15  # Already used from this location

    # ── Device compatibility ──
    if observed_contexts:
        known_devs = observed_contexts.get("device_types", {})
        if exec_ctx.device.device_type in known_devs:
            score += 0.05

    return max(0.0, min(1.0, score))


def adapt_qos_constraints_for_context(qos_constraints, exec_ctx: ExecutionContext):
    """Adapts QoS constraints based on the current context.

    For example, on a slow network we relax the response_time threshold
    so as not to exclude all services.

    Returns a modified copy of the constraints (does not mutate the original).
    """
    from models.service import QoS

    adapted = QoS(
        response_time=qos_constraints.response_time,
        availability=qos_constraints.availability,
        throughput=qos_constraints.throughput,
        successability=qos_constraints.successability,
        reliability=qos_constraints.reliability,
        compliance=qos_constraints.compliance,
        best_practices=qos_constraints.best_practices,
        latency=qos_constraints.latency,
        documentation=qos_constraints.documentation,
    )

    if not exec_ctx.network.is_set():
        return adapted

    quality = exec_ctx.network.connection_quality

    if quality == "poor":
        # Degraded network → relax response_time & latency
        if adapted.response_time > 0:
            adapted.response_time = adapted.response_time * 2.0
        if adapted.latency > 0:
            adapted.latency = adapted.latency * 2.0
        # Require better reliability
        adapted.reliability = max(adapted.reliability, 80)
    elif quality == "fair":
        if adapted.response_time > 0:
            adapted.response_time = adapted.response_time * 1.3
        if adapted.latency > 0:
            adapted.latency = adapted.latency * 1.3
    elif quality == "excellent":
        # Fast network → we can be more demanding
        if adapted.response_time > 0:
            adapted.response_time = adapted.response_time * 0.8

    return adapted
