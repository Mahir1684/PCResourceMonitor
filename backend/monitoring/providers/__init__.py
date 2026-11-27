"""Hardware and system telemetry provider implementations."""

from backend.monitoring.providers.dxgi_gpu import DxgiGpuProvider
from backend.monitoring.providers.nvidia_nvml import NvmlGpuProvider

__all__ = ["NvmlGpuProvider", "DxgiGpuProvider"]
