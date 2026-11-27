"""Network telemetry collector using psutil.

Discovers network interfaces, queries per-interface byte counters,
calculates download/upload throughput rates via monotonic time deltas,
and separates physical interfaces from virtual/tunnel/loopback adapters.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import psutil


logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Substrings identifying virtual, tunnel, or loopback network adapters
VIRTUAL_OR_LOOPBACK_KEYWORDS = (
    "loopback",
    "pseudo",
    "vethernet",
    "wsl",
    "hyper-v",
    "default switch",
    "teredo",
    "tailscale",
    "radmin",
    "openvpn",
    "wireguard",
    "tap",
    "tun",
    "vmware",
    "virtualbox",
    "host-only",
    "bluetooth",
    "*",  # Windows Wi-Fi Direct and Hosted Network virtual miniports
)


def is_virtual_or_loopback(interface_name: str) -> bool:
    """Check if an interface name indicates a virtual, tunnel, or loopback adapter."""
    lower = interface_name.lower()
    return any(keyword in lower for keyword in VIRTUAL_OR_LOOPBACK_KEYWORDS)


def _primary_candidate_key(item: dict[str, Any]) -> tuple[int, int, int, str]:
    """Deterministic sorting key for selecting primary active physical network adapter.

    Priority order:
    1. Has active traffic (download or upload rate > 0).
    2. Preferred physical name (contains 'ethernet' or 'wi-fi').
    3. Cumulative historical bytes transferred.
    4. Alphabetical tie-breaker.
    """
    down = item["download_bytes_per_second"] or 0.0
    up = item["upload_bytes_per_second"] or 0.0
    has_active_traffic = 1 if (down + up) > 0 else 0
    name_lower = item["name"].lower()
    is_preferred_name = 1 if ("ethernet" in name_lower or "wi-fi" in name_lower) else 0
    total_bytes = item["total_bytes_received"] + item["total_bytes_sent"]
    return (has_active_traffic, is_preferred_name, total_bytes, item["name"])


class NetworkCollector:
    """Collector for network interfaces and throughput rates."""

    def __init__(self) -> None:
        self._last_time: float | None = None
        # Maps interface name -> (bytes_recv, bytes_sent)
        self._last_counters: dict[str, tuple[int, int]] = {}

    def collect(self) -> dict[str, Any]:
        """Collect per-interface metrics and calculate throughput rates."""
        sampled_at = _utc_now_iso()
        now_mono = time.monotonic()

        try:
            io_pernic = psutil.net_io_counters(pernic=True)
            stats_pernic = psutil.net_if_stats()

            dt: float | None = None
            if self._last_time is not None:
                elapsed = now_mono - self._last_time
                if elapsed > 0:
                    dt = elapsed

            interfaces: list[dict[str, Any]] = []
            curr_counters: dict[str, tuple[int, int]] = {}

            for name, io in io_pernic.items():
                curr_recv = int(io.bytes_recv)
                curr_sent = int(io.bytes_sent)
                curr_counters[name] = (curr_recv, curr_sent)

                is_virtual = is_virtual_or_loopback(name)
                is_physical = not is_virtual

                stat = stats_pernic.get(name)
                is_up = bool(stat.isup) if stat else False

                down_rate: float | None = None
                up_rate: float | None = None

                if dt is not None and name in self._last_counters:
                    prev_recv, prev_sent = self._last_counters[name]
                    diff_recv = curr_recv - prev_recv
                    diff_sent = curr_sent - prev_sent

                    # Handle counter resets / rollovers safely
                    if diff_recv >= 0 and diff_sent >= 0:
                        down_rate = float(diff_recv / dt)
                        up_rate = float(diff_sent / dt)

                interfaces.append({
                    "name": name,
                    "is_up": is_up,
                    "is_physical": is_physical,
                    "download_bytes_per_second": down_rate,
                    "upload_bytes_per_second": up_rate,
                    "total_bytes_received": curr_recv,
                    "total_bytes_sent": curr_sent,
                })

            self._last_time = now_mono
            self._last_counters = curr_counters

            # Evaluate candidate active physical interfaces
            active_physical = [i for i in interfaces if i["is_physical"] and i["is_up"]]

            primary_interface: str | None = None
            summary_status = "disconnected"
            summary_down: float | None = None
            summary_up: float | None = None

            if active_physical:
                best = max(active_physical, key=_primary_candidate_key)
                primary_interface = best["name"]

                if dt is not None:
                    summary_status = "connected"
                    summary_down = sum(
                        (i["download_bytes_per_second"] or 0.0) for i in active_physical
                    )
                    summary_up = sum(
                        (i["upload_bytes_per_second"] or 0.0) for i in active_physical
                    )
                else:
                    summary_status = "baseline"

            return {
                "status": "ok",
                "sampled_at": sampled_at,
                "interfaces": interfaces,
                "summary": {
                    "primary_interface": primary_interface,
                    "status": summary_status,
                    "download_bytes_per_second": summary_down,
                    "upload_bytes_per_second": summary_up,
                },
                "rate_scope": "per-interface cumulative OS counters",
            }
        except Exception as exc:
            logger.error("Error collecting network metrics: %s", exc)
            return {
                "status": "error",
                "sampled_at": sampled_at,
                "error": {
                    "code": "NETWORK_COLLECTION_ERROR",
                    "message": str(exc),
                },
            }
