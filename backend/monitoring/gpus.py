"""Unified GPU telemetry collector.

Combines DXGI display adapter discovery with NVIDIA NVML real-time sensor
telemetry. Accurately correlates devices using hardware identity, enriches
dedicated GPUs with utilization/temperature/VRAM metrics, preserves DXGI memory
budget distinctions, and reports honest unavailable states for unexposed
integrated graphics sensors.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from backend.monitoring.providers.dxgi_gpu import (
    VENDOR_AMD,
    VENDOR_NVIDIA,
    DxgiGpuProvider,
)
from backend.monitoring.providers.nvidia_nvml import NvmlGpuProvider


logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    """Return the current UTC timestamp formatted as ISO 8601 with Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class GpuCollector:
    """Non-blocking collector for unified GPU telemetry."""

    def __init__(
        self,
        nvml_provider: NvmlGpuProvider | None = None,
        dxgi_provider: DxgiGpuProvider | None = None,
    ) -> None:
        self._nvml = nvml_provider if nvml_provider is not None else NvmlGpuProvider()
        self._dxgi = dxgi_provider if dxgi_provider is not None else DxgiGpuProvider()

        # Prime NVML session once during collector initialization
        try:
            self._nvml.initialize()
        except Exception as exc:
            logger.debug("Initial NVML setup exception: %s", exc)

    def shutdown(self) -> None:
        """Cleanly release NVML library resources."""
        nvml = getattr(self, "_nvml", None)
        if nvml is not None:
            try:
                nvml.shutdown()
            except Exception as exc:
                if logger is not None:
                    logger.debug("Exception during GPU collector NVML shutdown: %s", exc)

    def __del__(self) -> None:
        try:
            self.shutdown()
        except BaseException:
            pass

    def collect(self) -> dict[str, Any]:
        """Collect and correlate telemetry for all system display adapters.

        Returns a normalized dictionary containing all physical GPU devices,
        enriched with real-time sensors where supported and explicit unavailable
        metadata where unsupported.
        """
        sampled_at = _utc_now_iso()
        try:
            # 1. Enumerate DXGI display adapters
            dxgi_adapters: list[dict[str, Any]] = []
            try:
                dxgi_adapters = self._dxgi.get_adapters()
            except Exception as exc:
                logger.warning("DXGI adapter enumeration failed: %s", exc)

            # 2. Collect NVML telemetry
            nvml_devices: list[dict[str, Any]] = []
            try:
                nvml_devices = self._nvml.get_devices()
            except Exception as exc:
                logger.warning("NVML device telemetry failed: %s", exc)

            unified_devices: list[dict[str, Any]] = []
            unmatched_nvml = list(nvml_devices)

            # 3. Correlate adapters
            for adapter in dxgi_adapters:
                name = adapter.get("name", "")
                vendor_id_str = adapter.get("vendor_id", "")
                is_nvidia = (
                    vendor_id_str == hex(VENDOR_NVIDIA)
                    or "nvidia" in name.lower()
                    or "geforce" in name.lower()
                )

                matched_nvml_dev = None
                if is_nvidia and unmatched_nvml:
                    # Match by name or single-device identity
                    candidate_matches = [
                        d for d in unmatched_nvml
                        if d.get("name", "").lower() in name.lower()
                        or name.lower() in d.get("name", "").lower()
                    ]
                    if len(candidate_matches) == 1:
                        matched_nvml_dev = candidate_matches[0]
                        unmatched_nvml.remove(matched_nvml_dev)
                    elif (
                        len(unmatched_nvml) == 1
                        and len([
                            a for a in dxgi_adapters
                            if "nvidia" in a.get("name", "").lower()
                            or a.get("vendor_id") == hex(VENDOR_NVIDIA)
                        ]) == 1
                    ):
                        matched_nvml_dev = unmatched_nvml.pop(0)

                mem_caps = adapter.get("memory_capacities", {})
                dedicated_vram = mem_caps.get("dedicated_video_bytes")
                shared_ram = mem_caps.get("shared_system_bytes")

                if matched_nvml_dev is not None:
                    # Enriched NVIDIA GPU
                    nvml_mem = matched_nvml_dev.get("memory", {}).get("dedicated", {})
                    unified_devices.append({
                        "index": adapter.get("index", 0),
                        "name": name,
                        "vendor_id": adapter.get("vendor_id"),
                        "device_id": adapter.get("device_id"),
                        "subsys_id": adapter.get("subsys_id"),
                        "revision": adapter.get("revision"),
                        "luid": adapter.get("luid"),
                        "uuid": matched_nvml_dev.get("uuid"),
                        "pci_bus_id": matched_nvml_dev.get("pci_bus_id"),
                        "adapter_type": adapter.get("adapter_type", "dedicated"),
                        "provider": "nvml+dxgi",
                        "utilization_percent": matched_nvml_dev.get(
                            "utilization_percent",
                            {
                                "value": None,
                                "status": "unavailable",
                                "reason": "Utilization not reported by NVML.",
                            },
                        ),
                        "temperature_c": matched_nvml_dev.get(
                            "temperature_c",
                            {
                                "value": None,
                                "status": "unavailable",
                                "reason": "Temperature not reported by NVML.",
                            },
                        ),
                        "power_watts": matched_nvml_dev.get("power_watts"),
                        "clocks_mhz": matched_nvml_dev.get(
                            "clocks_mhz",
                            {"graphics": None, "memory": None},
                        ),
                        "memory": {
                            "dedicated": {
                                "status": nvml_mem.get("status", "ok"),
                                "total_bytes": nvml_mem.get("total_bytes", dedicated_vram),
                                "used_bytes": nvml_mem.get("used_bytes"),
                                "free_bytes": nvml_mem.get("free_bytes"),
                            },
                            "shared_system": {
                                "status": "ok",
                                "budget_bytes": shared_ram,
                                "used_bytes": None,
                                "note": "Reported DXGI adapter memory budget.",
                            },
                        },
                    })
                else:
                    # AMD integrated or unmerged adapter
                    is_amd = (
                        vendor_id_str == hex(VENDOR_AMD)
                        or "amd" in name.lower()
                        or "radeon" in name.lower()
                    )
                    temp_reason = (
                        "Integrated Radeon APU shares monolithic CPU package diode; no discrete GPU thermal diode exists."
                        if is_amd
                        else "Hardware temperature sensor unavailable for this display adapter."
                    )

                    unified_devices.append({
                        "index": adapter.get("index", 0),
                        "name": name,
                        "vendor_id": adapter.get("vendor_id"),
                        "device_id": adapter.get("device_id"),
                        "subsys_id": adapter.get("subsys_id"),
                        "revision": adapter.get("revision"),
                        "luid": adapter.get("luid"),
                        "uuid": None,
                        "pci_bus_id": None,
                        "adapter_type": adapter.get("adapter_type", "integrated"),
                        "provider": "dxgi",
                        "utilization_percent": {
                            "value": None,
                            "status": "unavailable",
                            "reason": "Real-time utilization not exposed by DXGI.",
                        },
                        "temperature_c": {
                            "value": None,
                            "status": "unavailable",
                            "reason": temp_reason,
                        },
                        "power_watts": None,
                        "clocks_mhz": {
                            "graphics": None,
                            "memory": None,
                        },
                        "memory": {
                            "dedicated": {
                                "status": "ok",
                                "total_bytes": dedicated_vram,
                                "used_bytes": None,
                                "free_bytes": None,
                                "note": "Reported DXGI adapter dedicated video memory capacity.",
                            },
                            "shared_system": {
                                "status": "ok",
                                "budget_bytes": shared_ram,
                                "used_bytes": None,
                                "note": "Reported DXGI adapter memory budget.",
                            },
                        },
                    })

            # If DXGI returned no adapters (e.g. non-Windows host), fallback to NVML
            if not dxgi_adapters and nvml_devices:
                for dev in nvml_devices:
                    dev_mem = dev.get("memory", {}).get("dedicated", {})
                    unified_devices.append({
                        "index": dev.get("index", 0),
                        "name": dev.get("name", "NVIDIA GPU"),
                        "vendor_id": hex(VENDOR_NVIDIA),
                        "device_id": None,
                        "subsys_id": None,
                        "revision": None,
                        "luid": None,
                        "uuid": dev.get("uuid"),
                        "pci_bus_id": dev.get("pci_bus_id"),
                        "adapter_type": dev.get("adapter_type", "dedicated"),
                        "provider": "nvml",
                        "utilization_percent": dev.get(
                            "utilization_percent",
                            {"value": None, "status": "unavailable"},
                        ),
                        "temperature_c": dev.get(
                            "temperature_c",
                            {"value": None, "status": "unavailable"},
                        ),
                        "power_watts": dev.get("power_watts"),
                        "clocks_mhz": dev.get(
                            "clocks_mhz",
                            {"graphics": None, "memory": None},
                        ),
                        "memory": {
                            "dedicated": dev_mem,
                            "shared_system": {
                                "status": "unavailable",
                                "budget_bytes": None,
                                "used_bytes": None,
                                "reason": "DXGI display adapter query unavailable.",
                            },
                        },
                    })

            return {
                "status": "ok",
                "sampled_at": sampled_at,
                "devices": unified_devices,
            }

        except Exception as exc:
            logger.error("Error collecting GPU telemetry: %s", exc)
            return {
                "status": "error",
                "sampled_at": sampled_at,
                "error": {
                    "code": "GPU_COLLECTION_ERROR",
                    "message": str(exc),
                },
            }
