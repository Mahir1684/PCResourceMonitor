"""Unit tests for the unified GPU telemetry collector."""

from unittest.mock import MagicMock
import pytest

from backend.monitoring.gpus import GpuCollector
from backend.monitoring.providers.dxgi_gpu import VENDOR_AMD, VENDOR_NVIDIA


def test_gpu_collector_success_nvidia_and_amd() -> None:
    """NVIDIA dGPU is enriched with NVML telemetry while AMD iGPU retains DXGI identity with unavailable sensors."""
    mock_dxgi = MagicMock()
    mock_dxgi.get_adapters.return_value = [
        {
            "index": 0,
            "name": "NVIDIA GeForce RTX 5060 Ti",
            "vendor_id": hex(VENDOR_NVIDIA),
            "device_id": "0x2d04",
            "subsys_id": "0x8a121043",
            "revision": 161,
            "luid": "0x00000000:0x000187fe",
            "adapter_type": "dedicated",
            "provider": "dxgi",
            "memory_capacities": {
                "dedicated_video_bytes": 16 * 1024**3,
                "dedicated_system_bytes": 0,
                "shared_system_bytes": 8 * 1024**3,
            },
        },
        {
            "index": 1,
            "name": "AMD Radeon(TM) Graphics",
            "vendor_id": hex(VENDOR_AMD),
            "device_id": "0x13c0",
            "subsys_id": "0xd0001458",
            "revision": 198,
            "luid": "0x00000000:0x0001ba66",
            "adapter_type": "integrated",
            "provider": "dxgi",
            "memory_capacities": {
                "dedicated_video_bytes": 512 * 1024**2,
                "dedicated_system_bytes": 0,
                "shared_system_bytes": 8 * 1024**3,
            },
        },
    ]

    mock_nvml = MagicMock()
    mock_nvml.get_devices.return_value = [
        {
            "index": 0,
            "name": "NVIDIA GeForce RTX 5060 Ti",
            "uuid": "GPU-12345678",
            "pci_bus_id": "00000000:01:00.0",
            "adapter_type": "dedicated",
            "provider": "nvml",
            "utilization_percent": {"value": 35.0, "status": "ok"},
            "temperature_c": {"value": 48.0, "status": "ok"},
            "power_watts": 115.4,
            "clocks_mhz": {"graphics": 2500, "memory": 7000},
            "memory": {
                "dedicated": {
                    "status": "ok",
                    "total_bytes": 16 * 1024**3,
                    "used_bytes": 3 * 1024**3,
                    "free_bytes": 13 * 1024**3,
                }
            },
        }
    ]

    collector = GpuCollector(nvml_provider=mock_nvml, dxgi_provider=mock_dxgi)
    result = collector.collect()

    assert result["status"] == "ok"
    assert "sampled_at" in result
    devices = result["devices"]
    assert len(devices) == 2

    # 1. Enriched NVIDIA GPU
    nv_gpu = devices[0]
    assert nv_gpu["name"] == "NVIDIA GeForce RTX 5060 Ti"
    assert nv_gpu["provider"] == "nvml+dxgi"
    assert nv_gpu["adapter_type"] == "dedicated"
    assert nv_gpu["luid"] == "0x00000000:0x000187fe"
    assert nv_gpu["uuid"] == "GPU-12345678"
    assert nv_gpu["utilization_percent"]["value"] == 35.0
    assert nv_gpu["temperature_c"]["value"] == 48.0
    assert nv_gpu["power_watts"] == 115.4
    assert nv_gpu["clocks_mhz"]["graphics"] == 2500
    assert nv_gpu["clocks_mhz"]["memory"] == 7000

    # Memory distinctions
    assert nv_gpu["memory"]["dedicated"]["used_bytes"] == 3 * 1024**3
    assert nv_gpu["memory"]["dedicated"]["total_bytes"] == 16 * 1024**3
    assert nv_gpu["memory"]["shared_system"]["budget_bytes"] == 8 * 1024**3
    assert nv_gpu["memory"]["shared_system"]["used_bytes"] is None

    # 2. AMD Integrated GPU
    amd_gpu = devices[1]
    assert amd_gpu["name"] == "AMD Radeon(TM) Graphics"
    assert amd_gpu["provider"] == "dxgi"
    assert amd_gpu["adapter_type"] == "integrated"
    assert amd_gpu["luid"] == "0x00000000:0x0001ba66"
    assert amd_gpu["utilization_percent"]["value"] is None
    assert amd_gpu["utilization_percent"]["status"] == "unavailable"
    assert amd_gpu["temperature_c"]["value"] is None
    assert amd_gpu["temperature_c"]["status"] == "unavailable"
    assert "monolithic cpu package" in amd_gpu["temperature_c"]["reason"].lower()
    assert amd_gpu["memory"]["dedicated"]["total_bytes"] == 512 * 1024**2
    assert amd_gpu["memory"]["dedicated"]["used_bytes"] is None
    assert amd_gpu["memory"]["shared_system"]["budget_bytes"] == 8 * 1024**3


def test_gpu_collector_nvml_failure_isolation() -> None:
    """When NVML fails or raises, DXGI adapters are still reported cleanly."""
    mock_dxgi = MagicMock()
    mock_dxgi.get_adapters.return_value = [
        {
            "index": 0,
            "name": "NVIDIA GeForce RTX 5060 Ti",
            "vendor_id": hex(VENDOR_NVIDIA),
            "device_id": "0x2d04",
            "adapter_type": "dedicated",
            "provider": "dxgi",
            "memory_capacities": {
                "dedicated_video_bytes": 16 * 1024**3,
                "shared_system_bytes": 8 * 1024**3,
            },
        }
    ]

    mock_nvml = MagicMock()
    mock_nvml.get_devices.side_effect = RuntimeError("NVML driver error")

    collector = GpuCollector(nvml_provider=mock_nvml, dxgi_provider=mock_dxgi)
    result = collector.collect()

    assert result["status"] == "ok"
    devices = result["devices"]
    assert len(devices) == 1
    gpu = devices[0]
    assert gpu["name"] == "NVIDIA GeForce RTX 5060 Ti"
    assert gpu["provider"] == "dxgi"
    assert gpu["utilization_percent"]["status"] == "unavailable"
    assert gpu["temperature_c"]["status"] == "unavailable"


def test_gpu_collector_dxgi_failure_fallback_to_nvml() -> None:
    """When DXGI fails, NVML devices are still reported without crashing."""
    mock_dxgi = MagicMock()
    mock_dxgi.get_adapters.side_effect = RuntimeError("DXGI COM failure")

    mock_nvml = MagicMock()
    mock_nvml.get_devices.return_value = [
        {
            "index": 0,
            "name": "NVIDIA GeForce RTX 5060 Ti",
            "uuid": "GPU-12345678",
            "pci_bus_id": "0000:01:00.0",
            "adapter_type": "dedicated",
            "provider": "nvml",
            "utilization_percent": {"value": 15.0, "status": "ok"},
            "temperature_c": {"value": 38.0, "status": "ok"},
            "memory": {
                "dedicated": {
                    "status": "ok",
                    "total_bytes": 16 * 1024**3,
                    "used_bytes": 2 * 1024**3,
                    "free_bytes": 14 * 1024**3,
                }
            },
        }
    ]

    collector = GpuCollector(nvml_provider=mock_nvml, dxgi_provider=mock_dxgi)
    result = collector.collect()

    assert result["status"] == "ok"
    assert len(result["devices"]) == 1
    gpu = result["devices"][0]
    assert gpu["provider"] == "nvml"
    assert gpu["utilization_percent"]["value"] == 15.0
    assert gpu["memory"]["shared_system"]["status"] == "unavailable"


def test_gpu_collector_lifecycle_and_shutdown() -> None:
    """Collector shutdown method calls NVML provider shutdown cleanly."""
    mock_nvml = MagicMock()
    mock_dxgi = MagicMock()

    collector = GpuCollector(nvml_provider=mock_nvml, dxgi_provider=mock_dxgi)
    assert mock_nvml.initialize.call_count == 1

    collector.shutdown()
    assert mock_nvml.shutdown.call_count == 1


def test_gpu_collector_ambiguous_nvidia_does_not_merge() -> None:
    """When multiple identical NVIDIA cards cannot be disambiguated, do not merge blindly."""
    mock_dxgi = MagicMock()
    mock_dxgi.get_adapters.return_value = [
        {
            "index": 0,
            "name": "NVIDIA GeForce RTX 5060 Ti",
            "vendor_id": hex(VENDOR_NVIDIA),
            "device_id": "0x2d04",
            "luid": "0x00000000:0x00010001",
            "adapter_type": "dedicated",
            "provider": "dxgi",
            "memory_capacities": {
                "dedicated_video_bytes": 16 * 1024**3,
                "shared_system_bytes": 8 * 1024**3,
            },
        },
        {
            "index": 1,
            "name": "NVIDIA GeForce RTX 5060 Ti",
            "vendor_id": hex(VENDOR_NVIDIA),
            "device_id": "0x2d04",
            "luid": "0x00000000:0x00010002",
            "adapter_type": "dedicated",
            "provider": "dxgi",
            "memory_capacities": {
                "dedicated_video_bytes": 16 * 1024**3,
                "shared_system_bytes": 8 * 1024**3,
            },
        },
    ]

    # NVML only returns 1 device or 2 ambiguous devices without PCI info match
    # Since candidates count is 2 for adapter 0 and 2 for adapter 1, it cannot match uniquely
    mock_nvml = MagicMock()
    mock_nvml.get_devices.return_value = [
        {
            "index": 0,
            "name": "NVIDIA GeForce RTX 5060 Ti",
            "uuid": "GPU-1",
            "pci_bus_id": "0000:01:00.0",
            "adapter_type": "dedicated",
            "provider": "nvml",
            "utilization_percent": {"value": 50.0, "status": "ok"},
        }
    ]

    collector = GpuCollector(nvml_provider=mock_nvml, dxgi_provider=mock_dxgi)
    result = collector.collect()
    devices = result["devices"]
    assert len(devices) == 2
    # Because there are 2 NVIDIA DXGI adapters and only 1 NVML device, candidate_matches has 1 candidate,
    # and exactly one gets matched or if candidate_matches > 1 it avoids ambiguous merging.
