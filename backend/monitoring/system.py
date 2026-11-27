"""System metadata and uptime collector.

Collects host machine identity, operating system version, CPU processor
name, and system uptime. Uses standard library winreg on Windows for
instantaneous and accurate processor identification without invoking WMI.
"""

from __future__ import annotations

import logging
import platform
import socket
import sys
import time
from datetime import datetime, timezone
from typing import Any

import psutil


logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_cpu_name() -> str | None:
    """Resolve full CPU marketing model name via winreg on Windows or platform fallback."""
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            )
            val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            winreg.CloseKey(key)
            if val and isinstance(val, str):
                return val.strip()
        except Exception as exc:
            logger.debug("winreg CPU query failed: %s", exc)

    # Fallback to platform processor string if winreg unavailable
    proc = platform.processor()
    return proc.strip() if proc else None


def resolve_os_name() -> str:
    """Resolve human-readable operating system string."""
    system = platform.system()
    release = platform.release()
    version = platform.version()

    if system == "Windows":
        return f"Windows {release} (Build {version})"
    return f"{system} {release}"


class SystemCollector:
    """Collector for static system identification and dynamic uptime."""

    def __init__(self) -> None:
        # Cache static metadata on initialization
        self._hostname = socket.gethostname()
        self._os_name = resolve_os_name()
        self._cpu_name = resolve_cpu_name()

    def collect(self) -> dict[str, Any]:
        """Collect current system uptime and host metadata."""
        sampled_at = _utc_now_iso()
        try:
            boot_time = psutil.boot_time()
            uptime_sec = max(0, int(time.time() - boot_time))

            return {
                "status": "ok",
                "sampled_at": sampled_at,
                "hostname": self._hostname,
                "os": self._os_name,
                "cpu_name": self._cpu_name,
                "boot_time_timestamp": float(boot_time),
                "uptime_seconds": uptime_sec,
            }
        except Exception as exc:
            logger.error("Error collecting system metadata: %s", exc)
            return {
                "status": "error",
                "sampled_at": sampled_at,
                "hostname": self._hostname,
                "os": self._os_name,
                "cpu_name": self._cpu_name,
                "error": {
                    "code": "SYSTEM_COLLECTION_ERROR",
                    "message": str(exc),
                },
            }
