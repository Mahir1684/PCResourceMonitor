"""CPU telemetry collector using psutil.

Collects total CPU utilization, per-core utilization, clock frequency,
and core topology counts in a non-blocking manner.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import psutil

from backend.monitoring.providers.lhm_bridge import LhmBridgeClient


logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CpuCollector:
    """Non-blocking collector for CPU telemetry."""

    def __init__(self, bridge_client: LhmBridgeClient | None = None) -> None:
        self._bridge = bridge_client if bridge_client is not None else LhmBridgeClient()

        # Prime psutil CPU counters on initialization so subsequent
        # non-blocking calls (interval=None) calculate deltas accurately.
        try:
            psutil.cpu_percent(interval=None)
            psutil.cpu_percent(interval=None, percpu=True)
        except Exception as exc:
            logger.debug("Failed to prime CPU counters: %s", exc)

    def collect(self) -> dict[str, Any]:
        """Collect current CPU utilization, frequency, core topology, and hardware sensors."""
        sampled_at = _utc_now_iso()
        try:
            total_percent = float(psutil.cpu_percent(interval=None))
            per_core = [float(p) for p in psutil.cpu_percent(interval=None, percpu=True)]

            freq = psutil.cpu_freq()
            freq_mhz = float(freq.current) if (freq and freq.current is not None) else None

            cores_phys = psutil.cpu_count(logical=False)
            cores_log = psutil.cpu_count(logical=True)

            # Query hardware sensors from local bridge (non-blocking / short timeout)
            try:
                bridge_sensors = self._bridge.get_cpu_sensors()
            except Exception as exc:
                logger.debug("Exception querying CPU bridge: %s", exc)
                bridge_sensors = {
                    "package_temperature_c": None,
                    "core_temperatures_c": [],
                    "package_power_watts": None,
                    "status": "unavailable",
                    "reason": f"Bridge query error: {exc}",
                }

            pkg_temp = bridge_sensors.get("package_temperature_c")
            core_temps = bridge_sensors.get("core_temperatures_c", [])
            pkg_power = bridge_sensors.get("package_power_watts")
            bridge_reason = (
                bridge_sensors.get("reason")
                or "Hardware sensor data unavailable from bridge."
            )

            if pkg_temp is not None:
                temp_data: dict[str, Any] = {"value": pkg_temp, "status": "ok"}
            else:
                temp_data = {
                    "value": None,
                    "status": "unavailable",
                    "reason": bridge_reason,
                }

            if pkg_power is not None:
                power_data: dict[str, Any] = {"value": pkg_power, "status": "ok"}
            else:
                power_data = {
                    "value": None,
                    "status": "unavailable",
                    "reason": bridge_reason,
                }

            return {
                "status": "ok",
                "sampled_at": sampled_at,
                "usage_percent": total_percent,
                "per_core_percent": per_core,
                "frequency_mhz": freq_mhz,
                "cores_physical": cores_phys,
                "cores_logical": cores_log,
                "temperature_c": temp_data,
                "core_temperatures_c": core_temps,
                "power_watts": power_data,
            }
        except Exception as exc:
            logger.error("Error collecting CPU metrics: %s", exc)
            return {
                "status": "error",
                "sampled_at": sampled_at,
                "error": {
                    "code": "CPU_COLLECTION_ERROR",
                    "message": str(exc),
                },
            }
