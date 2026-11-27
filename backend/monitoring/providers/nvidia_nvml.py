"""NVIDIA GPU telemetry provider using NVML via pynvml.

Provides robust, read-only telemetry for NVIDIA graphics processors,
including utilization, temperature, dedicated VRAM metrics, clocks, and power.
Manages NVML session lifecycle efficiently across sampling cycles without
re-initializing on every tick.
"""

from __future__ import annotations

import logging
from typing import Any

import pynvml


logger = logging.getLogger(__name__)


def _decode_nvml_str(val: Any) -> str:
    """Safely decode an NVML string that may be returned as bytes or str."""
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="ignore")
    return str(val) if val is not None else ""


class NvmlGpuProvider:
    """Telemetry provider for NVIDIA GPUs via NVML."""

    def __init__(self) -> None:
        self._initialized: bool = False
        self._init_error: str | None = None

    @staticmethod
    def _is_uninitialized_error(exc: Exception) -> bool:
        """Detect whether an error indicates NVML has become uninitialized or the driver was lost."""
        if isinstance(exc, pynvml.NVMLError):
            err_code = getattr(exc, "value", None)
            uninit_codes = (
                getattr(pynvml, "NVML_ERROR_UNINITIALIZED", 1),
                getattr(pynvml, "NVML_ERROR_DRIVER_NOT_LOADED", 9),
                getattr(pynvml, "NVML_ERROR_GPU_IS_LOST", 15),
            )
            if err_code in uninit_codes:
                return True
        exc_str = str(exc).lower()
        return any(
            marker in exc_str
            for marker in ("uninitialized", "driver not loaded", "gpu is lost", "driver_not_loaded")
        )

    @property
    def is_initialized(self) -> bool:
        """True if NVML was successfully initialized and is ready."""
        return self._initialized

    @property
    def init_error(self) -> str | None:
        """Error message if NVML initialization failed."""
        return self._init_error

    def initialize(self) -> bool:
        """Initialize NVML library. Safe to call repeatedly."""
        if self._initialized:
            return True

        try:
            pynvml.nvmlInit()
            self._initialized = True
            self._init_error = None
            logger.debug("NVML initialized successfully.")
            return True
        except (pynvml.NVMLError, Exception) as exc:
            self._initialized = False
            self._init_error = str(exc)
            logger.debug("NVML initialization failed: %s", exc)
            return False

    def shutdown(self) -> None:
        """Shutdown NVML and release library handles. Safe, idempotent, and teardown-tolerant."""
        if not getattr(self, "_initialized", False):
            return

        self._initialized = False

        mod_pynvml = globals().get("pynvml")
        if mod_pynvml is not None and hasattr(mod_pynvml, "nvmlShutdown"):
            try:
                mod_pynvml.nvmlShutdown()
                if logger is not None:
                    logger.debug("NVML shutdown successfully.")
            except Exception as exc:
                nvml_err = getattr(mod_pynvml, "NVMLError", None)
                if nvml_err is not None and isinstance(exc, nvml_err):
                    if logger is not None:
                        logger.debug("NVML library error during shutdown: %s", exc)
                else:
                    if logger is not None:
                        logger.debug("Error during NVML shutdown: %s", exc)

    def __del__(self) -> None:
        try:
            if getattr(self, "_initialized", False):
                self.shutdown()
        except BaseException:
            pass

    def get_devices(self) -> list[dict[str, Any]]:
        """Collect telemetry for all enumerated NVIDIA GPUs.
        
        Returns an empty list if NVML cannot be initialized or no NVIDIA GPUs are present.
        Each device metric is queried independently to isolate unsupported sensors.
        If an uninitialized / driver lost error is detected, the provider resets its
        internal state so subsequent cycles can recover cleanly.
        """
        if not self._initialized and not self.initialize():
            return []

        devices: list[dict[str, Any]] = []
        try:
            device_count = pynvml.nvmlDeviceGetCount()
        except (pynvml.NVMLError, Exception) as exc:
            logger.warning("Failed to query NVML device count: %s", exc)
            if self._is_uninitialized_error(exc):
                self._initialized = False
                self._init_error = f"NVML lost or uninitialized: {exc}"
            return []

        for idx in range(device_count):
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
            except (pynvml.NVMLError, Exception) as exc:
                logger.warning("Cannot acquire handle for NVIDIA GPU index %d: %s", idx, exc)
                if self._is_uninitialized_error(exc):
                    self._initialized = False
                    self._init_error = f"NVML lost during device handle query: {exc}"
                continue

            # Identity
            try:
                raw_name = pynvml.nvmlDeviceGetName(handle)
                name = _decode_nvml_str(raw_name)
            except (pynvml.NVMLError, Exception) as exc:
                name = f"NVIDIA GPU #{idx}"

            try:
                raw_uuid = pynvml.nvmlDeviceGetUUID(handle)
                uuid = _decode_nvml_str(raw_uuid)
            except (pynvml.NVMLError, Exception):
                uuid = None

            try:
                pci_info = pynvml.nvmlDeviceGetPciInfo(handle)
                bus_id = _decode_nvml_str(getattr(pci_info, "busId", ""))
            except (pynvml.NVMLError, Exception):
                bus_id = None

            # 1. Utilization
            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                util_gpu = float(util.gpu)
                util_data = {"value": util_gpu, "status": "ok"}
            except (pynvml.NVMLError, Exception) as exc:
                if self._is_uninitialized_error(exc):
                    self._initialized = False
                    self._init_error = f"NVML lost during utilization query: {exc}"
                util_data = {
                    "value": None,
                    "status": "unavailable",
                    "reason": f"NVML utilization unavailable: {exc}",
                }

            # 2. Temperature
            try:
                temp_c = float(pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU))
                temp_data = {"value": temp_c, "status": "ok"}
            except (pynvml.NVMLError, Exception) as exc:
                if self._is_uninitialized_error(exc):
                    self._initialized = False
                    self._init_error = f"NVML lost during temperature query: {exc}"
                temp_data = {
                    "value": None,
                    "status": "unavailable",
                    "reason": f"NVML temperature unavailable: {exc}",
                }

            # 3. VRAM Memory
            try:
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                mem_data = {
                    "status": "ok",
                    "total_bytes": int(mem.total),
                    "used_bytes": int(mem.used),
                    "free_bytes": int(mem.free),
                }
            except (pynvml.NVMLError, Exception) as exc:
                if self._is_uninitialized_error(exc):
                    self._initialized = False
                    self._init_error = f"NVML lost during memory query: {exc}"
                mem_data = {
                    "status": "unavailable",
                    "total_bytes": None,
                    "used_bytes": None,
                    "free_bytes": None,
                    "reason": f"NVML memory unavailable: {exc}",
                }

            # 4. Clocks (Graphics and Memory)
            graphics_clock_mhz: int | None = None
            try:
                graphics_clock_mhz = int(
                    pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)
                )
            except (pynvml.NVMLError, Exception):
                pass

            memory_clock_mhz: int | None = None
            try:
                memory_clock_mhz = int(
                    pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
                )
            except (pynvml.NVMLError, Exception):
                pass

            # 5. Power Usage
            power_watts: float | None = None
            try:
                power_mw = pynvml.nvmlDeviceGetPowerUsage(handle)
                power_watts = round(float(power_mw) / 1000.0, 2)
            except (pynvml.NVMLError, Exception):
                pass

            devices.append({
                "index": idx,
                "name": name,
                "uuid": uuid,
                "pci_bus_id": bus_id,
                "adapter_type": "dedicated",
                "provider": "nvml",
                "utilization_percent": util_data,
                "temperature_c": temp_data,
                "power_watts": power_watts,
                "clocks_mhz": {
                    "graphics": graphics_clock_mhz,
                    "memory": memory_clock_mhz,
                },
                "memory": {
                    "dedicated": mem_data,
                },
            })

        return devices
