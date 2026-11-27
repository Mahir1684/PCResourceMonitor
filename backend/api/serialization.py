"""Response serialization and schema normalization for PCResourceMonitor API.

Ensures all responses conform strictly to the public JSON API contract
specified in docs/ARCHITECTURE.md.
"""

from __future__ import annotations

from typing import Any, Mapping


def serialize_status_response(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Serialize the telemetry snapshot for the /api/v1/status endpoint."""
    return {
        "schema_version": int(snapshot.get("schema_version", 1)),
        "sequence": int(snapshot.get("sequence", 0)),
        "generated_at": str(snapshot.get("generated_at", "")),
        "overall_status": str(snapshot.get("overall_status", "initializing")),
        "sections": dict(snapshot.get("sections", {})),
    }


def serialize_health_response(
    sampler_running: bool,
    sampler_interval: float,
    last_sequence: int,
    overall_status: str,
) -> dict[str, Any]:
    """Serialize system and sampler health status for /api/v1/health."""
    if overall_status == "error":
        health_status = "unhealthy"
    elif overall_status in ("partial", "initializing") or not sampler_running:
        health_status = "degraded"
    else:
        health_status = "healthy"

    return {
        "status": health_status,
        "sampler": {
            "is_running": bool(sampler_running),
            "interval_seconds": float(sampler_interval),
            "last_sequence": int(last_sequence),
        },
        "overall_status": str(overall_status),
    }


def serialize_error_response(code: str, message: str) -> dict[str, Any]:
    """Serialize standardized error response payload."""
    return {
        "error": {
            "code": str(code),
            "message": str(message),
        }
    }
