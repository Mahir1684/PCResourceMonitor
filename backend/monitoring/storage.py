"""Storage telemetry collector using psutil.

Discovers mounted storage volumes dynamically (including fixed and removable drives),
collects capacity and usage metrics, and calculates disk I/O throughput when system
performance counters are available.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any

import psutil


logger = logging.getLogger(__name__)

_DRIVE_REMOVABLE = 2
_DRIVE_FIXED = 3


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _classify_drive(mountpoint: str, opts: str) -> tuple[bool, str]:
    """Return (is_removable, drive_type) for a mounted volume."""
    lower_opts = opts.lower() if opts else ""
    if "removable" in lower_opts:
        return True, "removable"

    if sys.platform == "win32":
        try:
            root = mountpoint if mountpoint.endswith("\\") else f"{mountpoint}\\"
            drive_code = ctypes.windll.kernel32.GetDriveTypeW(root)
            if drive_code == _DRIVE_REMOVABLE:
                return True, "removable"
            if drive_code == _DRIVE_FIXED:
                return False, "fixed"
        except Exception as exc:
            logger.debug("GetDriveTypeW failed for %s: %s", mountpoint, exc)

    return False, "fixed"


class StorageCollector:
    """Collector for multi-volume disk capacity and I/O rates."""

    def __init__(self) -> None:
        self._last_time: float | None = None
        self._last_read_bytes: int | None = None
        self._last_write_bytes: int | None = None

    def collect(self) -> dict[str, Any]:
        """Collect storage volumes capacity and overall disk I/O throughput."""
        sampled_at = _utc_now_iso()
        now_mono = time.monotonic()

        volumes: list[dict[str, Any]] = []
        try:
            try:
                partitions = psutil.disk_partitions(all=False)
            except Exception as exc:
                logger.warning("Failed to enumerate disk partitions: %s", exc)
                partitions = []

            for part in partitions:
                opts = part.opts.lower() if part.opts else ""
                # Exclude optical/CD-ROM drives or partitions with no mountpoint
                if "cdrom" in opts or part.fstype.lower() in ("cdrom", "udf", "iso9660"):
                    continue
                if not part.mountpoint:
                    continue

                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    total_b = int(usage.total)
                    if total_b <= 0:
                        continue
                    is_removable, drive_type = _classify_drive(part.mountpoint, part.opts or "")
                    volumes.append({
                        "mount": part.mountpoint,
                        "device": part.device,
                        "fstype": part.fstype,
                        "is_removable": is_removable,
                        "drive_type": drive_type,
                        "total_bytes": total_b,
                        "used_bytes": int(usage.used),
                        "free_bytes": int(usage.free),
                        "usage_percent": float(usage.percent),
                    })
                except (PermissionError, OSError, Exception) as exc:
                    logger.debug("Cannot query volume %s: %s", part.mountpoint, exc)
                    continue

            # Disk I/O Rate Calculation
            read_rate: float | None = None
            write_rate: float | None = None
            io_status = "unavailable"
            io_reason: str | None = None

            try:
                io_counters = psutil.disk_io_counters()
                if io_counters is None:
                    io_reason = "Windows disk performance counters are not available."
                else:
                    curr_read = int(io_counters.read_bytes)
                    curr_write = int(io_counters.write_bytes)

                    if (
                        self._last_time is not None
                        and self._last_read_bytes is not None
                        and self._last_write_bytes is not None
                    ):
                        dt = now_mono - self._last_time
                        if dt > 0:
                            read_diff = curr_read - self._last_read_bytes
                            write_diff = curr_write - self._last_write_bytes

                            if read_diff >= 0 and write_diff >= 0:
                                read_rate = float(read_diff / dt)
                                write_rate = float(write_diff / dt)
                                io_status = "ok"
                            else:
                                io_reason = "Counter reset or rollover detected."
                        else:
                            io_reason = "Sampling interval too small for rate calculation."
                    else:
                        io_reason = "Initial baseline sample recorded."

                    self._last_time = now_mono
                    self._last_read_bytes = curr_read
                    self._last_write_bytes = curr_write
            except Exception as exc:
                logger.debug("Error querying disk I/O counters: %s", exc)
                io_reason = f"Disk I/O error: {exc.__class__.__name__}"

            overall_status = "ok" if volumes else "partial"
            return {
                "status": overall_status,
                "sampled_at": sampled_at,
                "volumes": volumes,
                "io_throughput": {
                    "status": io_status,
                    "read_bytes_per_second": read_rate,
                    "write_bytes_per_second": write_rate,
                    "reason": io_reason,
                },
            }
        except Exception as exc:
            logger.error("Error collecting storage metrics: %s", exc)
            return {
                "status": "error",
                "sampled_at": sampled_at,
                "error": {
                    "code": "STORAGE_COLLECTION_ERROR",
                    "message": str(exc),
                },
            }
