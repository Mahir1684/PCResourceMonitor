"""Physical memory telemetry collector using psutil.

Collects total, used, available physical RAM bytes and utilization percentage.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import psutil


logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class MemoryCollector:
    """Collector for physical RAM telemetry."""

    def collect(self) -> dict[str, Any]:
        """Collect current system physical memory metrics."""
        sampled_at = _utc_now_iso()
        try:
            vm = psutil.virtual_memory()
            return {
                "status": "ok",
                "sampled_at": sampled_at,
                "total_bytes": int(vm.total),
                "used_bytes": int(vm.used),
                "available_bytes": int(vm.available),
                "usage_percent": float(vm.percent),
            }
        except Exception as exc:
            logger.error("Error collecting memory metrics: %s", exc)
            return {
                "status": "error",
                "sampled_at": sampled_at,
                "error": {
                    "code": "MEMORY_COLLECTION_ERROR",
                    "message": str(exc),
                },
            }
