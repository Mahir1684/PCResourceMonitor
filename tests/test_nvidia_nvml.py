"""Unit tests for NvmlGpuProvider using mocked pynvml."""

from unittest.mock import MagicMock, patch
import pytest
import pynvml

from backend.monitoring.providers.nvidia_nvml import NvmlGpuProvider


def test_nvml_provider_success() -> None:
    """Test standard successful GPU metrics collection via mocked NVML."""
    mock_handle = MagicMock()

    mock_util = MagicMock(gpu=42, memory=18)
    mock_mem = MagicMock(total=17179869184, used=2147483648, free=15032385536)
    mock_pci = MagicMock(busId=b"00000000:01:00.0")

    with (
        patch("pynvml.nvmlInit") as mock_init,
        patch("pynvml.nvmlDeviceGetCount", return_value=1),
        patch("pynvml.nvmlDeviceGetHandleByIndex", return_value=mock_handle),
        patch("pynvml.nvmlDeviceGetName", return_value="NVIDIA GeForce RTX 5060 Ti"),
        patch("pynvml.nvmlDeviceGetUUID", return_value="GPU-12345678-ABCD"),
        patch("pynvml.nvmlDeviceGetPciInfo", return_value=mock_pci),
        patch("pynvml.nvmlDeviceGetUtilizationRates", return_value=mock_util),
        patch("pynvml.nvmlDeviceGetTemperature", return_value=55),
        patch("pynvml.nvmlDeviceGetMemoryInfo", return_value=mock_mem),
        patch("pynvml.nvmlDeviceGetClockInfo", side_effect=[2500, 7000]),
        patch("pynvml.nvmlDeviceGetPowerUsage", return_value=125500),  # 125.5W
    ):
        provider = NvmlGpuProvider()
        devices = provider.get_devices()

        assert len(devices) == 1
        gpu = devices[0]
        assert gpu["name"] == "NVIDIA GeForce RTX 5060 Ti"
        assert gpu["uuid"] == "GPU-12345678-ABCD"
        assert gpu["pci_bus_id"] == "00000000:01:00.0"
        assert gpu["provider"] == "nvml"

        assert gpu["utilization_percent"]["status"] == "ok"
        assert gpu["utilization_percent"]["value"] == 42.0

        assert gpu["temperature_c"]["status"] == "ok"
        assert gpu["temperature_c"]["value"] == 55.0

        assert gpu["memory"]["dedicated"]["status"] == "ok"
        assert gpu["memory"]["dedicated"]["total_bytes"] == 17179869184
        assert gpu["memory"]["dedicated"]["used_bytes"] == 2147483648

        assert gpu["clocks_mhz"]["graphics"] == 2500
        assert gpu["clocks_mhz"]["memory"] == 7000
        assert gpu["power_watts"] == 125.5

        assert provider.is_initialized
        assert mock_init.call_count == 1


def test_nvml_provider_initialization_failure() -> None:
    """When NVML driver/library is absent, provider fails gracefully without raising."""
    with patch("pynvml.nvmlInit", side_effect=pynvml.NVMLError(pynvml.NVML_ERROR_DRIVER_NOT_LOADED)):
        provider = NvmlGpuProvider()
        devices = provider.get_devices()

        assert devices == []
        assert not provider.is_initialized
        assert provider.init_error is not None


def test_nvml_provider_no_devices() -> None:
    """When device count is 0, provider returns empty list."""
    with (
        patch("pynvml.nvmlInit"),
        patch("pynvml.nvmlDeviceGetCount", return_value=0),
    ):
        provider = NvmlGpuProvider()
        devices = provider.get_devices()
        assert devices == []
        assert provider.is_initialized


def test_nvml_provider_unsupported_metrics() -> None:
    """When individual sensors fail, unavailable status is recorded without crashing."""
    mock_handle = MagicMock()
    mock_mem = MagicMock(total=8000000, used=1000000, free=7000000)

    with (
        patch("pynvml.nvmlInit"),
        patch("pynvml.nvmlDeviceGetCount", return_value=1),
        patch("pynvml.nvmlDeviceGetHandleByIndex", return_value=mock_handle),
        patch("pynvml.nvmlDeviceGetName", return_value="RTX 5060 Ti"),
        patch("pynvml.nvmlDeviceGetUUID", return_value="UUID-123"),
        patch("pynvml.nvmlDeviceGetPciInfo", side_effect=Exception("PCI error")),
        patch("pynvml.nvmlDeviceGetUtilizationRates", side_effect=pynvml.NVMLError(pynvml.NVML_ERROR_NOT_SUPPORTED)),
        patch("pynvml.nvmlDeviceGetTemperature", side_effect=pynvml.NVMLError(pynvml.NVML_ERROR_NOT_SUPPORTED)),
        patch("pynvml.nvmlDeviceGetMemoryInfo", return_value=mock_mem),
        patch("pynvml.nvmlDeviceGetClockInfo", side_effect=Exception("Clock error")),
        patch("pynvml.nvmlDeviceGetPowerUsage", side_effect=Exception("Power error")),
    ):
        provider = NvmlGpuProvider()
        devices = provider.get_devices()

        assert len(devices) == 1
        gpu = devices[0]

        assert gpu["utilization_percent"]["status"] == "unavailable"
        assert gpu["utilization_percent"]["value"] is None
        assert "not supported" in gpu["utilization_percent"]["reason"].lower()

        assert gpu["temperature_c"]["status"] == "unavailable"
        assert gpu["temperature_c"]["value"] is None
        assert "not supported" in gpu["temperature_c"]["reason"].lower()

        assert gpu["memory"]["dedicated"]["status"] == "ok"
        assert gpu["clocks_mhz"]["graphics"] is None
        assert gpu["power_watts"] is None


def test_nvml_provider_lifecycle_management() -> None:
    """NVML session must remain open across multiple queries and close cleanly on shutdown."""
    with (
        patch("pynvml.nvmlInit") as mock_init,
        patch("pynvml.nvmlShutdown") as mock_shutdown,
        patch("pynvml.nvmlDeviceGetCount", return_value=0),
    ):
        provider = NvmlGpuProvider()
        # Query 1
        provider.get_devices()
        # Query 2
        provider.get_devices()
        # Query 3
        provider.get_devices()

        # nvmlInit should be called only once
        assert mock_init.call_count == 1
        # nvmlShutdown should not be called during queries
        assert mock_shutdown.call_count == 0

        # Explicit shutdown
        provider.shutdown()
        assert mock_shutdown.call_count == 1
        assert not provider.is_initialized


def test_nvml_provider_multi_gpu() -> None:
    """Multi-GPU systems must enumerate each GPU independently with correct indices."""
    h0 = MagicMock()
    h1 = MagicMock()

    mem0 = MagicMock(total=16000000000, used=2000000000, free=14000000000)
    mem1 = MagicMock(total=24000000000, used=4000000000, free=20000000000)

    with (
        patch("pynvml.nvmlInit"),
        patch("pynvml.nvmlDeviceGetCount", return_value=2),
        patch("pynvml.nvmlDeviceGetHandleByIndex", side_effect=[h0, h1]),
        patch("pynvml.nvmlDeviceGetName", side_effect=["RTX 5060 Ti", "RTX 4090"]),
        patch("pynvml.nvmlDeviceGetUUID", side_effect=["UUID-0", "UUID-1"]),
        patch("pynvml.nvmlDeviceGetPciInfo", side_effect=[
            MagicMock(busId=b"00000000:01:00.0"),
            MagicMock(busId=b"00000000:02:00.0"),
        ]),
        patch("pynvml.nvmlDeviceGetUtilizationRates", side_effect=[
            MagicMock(gpu=25),
            MagicMock(gpu=85),
        ]),
        patch("pynvml.nvmlDeviceGetTemperature", side_effect=[48, 68]),
        patch("pynvml.nvmlDeviceGetMemoryInfo", side_effect=[mem0, mem1]),
        patch("pynvml.nvmlDeviceGetClockInfo", side_effect=[2500, 7000, 2600, 10500]),
        patch("pynvml.nvmlDeviceGetPowerUsage", side_effect=[110000, 320000]),
    ):
        provider = NvmlGpuProvider()
        devices = provider.get_devices()

        assert len(devices) == 2
        assert devices[0]["index"] == 0
        assert devices[0]["name"] == "RTX 5060 Ti"
        assert devices[0]["utilization_percent"]["value"] == 25.0
        assert devices[0]["temperature_c"]["value"] == 48.0
        assert devices[0]["power_watts"] == 110.0

        assert devices[1]["index"] == 1
        assert devices[1]["name"] == "RTX 4090"
        assert devices[1]["utilization_percent"]["value"] == 85.0
        assert devices[1]["temperature_c"]["value"] == 68.0
        assert devices[1]["power_watts"] == 320.0


def test_nvml_provider_partial_enumeration_failure() -> None:
    """When one GPU fails handle acquisition, remaining GPUs must still be returned."""
    h1 = MagicMock()
    mem1 = MagicMock(total=16000000000, used=2000000000, free=14000000000)

    with (
        patch("pynvml.nvmlInit"),
        patch("pynvml.nvmlDeviceGetCount", return_value=2),
        patch(
            "pynvml.nvmlDeviceGetHandleByIndex",
            side_effect=[pynvml.NVMLError(pynvml.NVML_ERROR_UNKNOWN), h1],
        ),
        patch("pynvml.nvmlDeviceGetName", return_value="RTX 5060 Ti"),
        patch("pynvml.nvmlDeviceGetUUID", return_value="UUID-1"),
        patch("pynvml.nvmlDeviceGetPciInfo", return_value=MagicMock(busId=b"0000:01:00.0")),
        patch("pynvml.nvmlDeviceGetUtilizationRates", return_value=MagicMock(gpu=15)),
        patch("pynvml.nvmlDeviceGetTemperature", return_value=40),
        patch("pynvml.nvmlDeviceGetMemoryInfo", return_value=mem1),
        patch("pynvml.nvmlDeviceGetClockInfo", side_effect=[2000, 7000]),
        patch("pynvml.nvmlDeviceGetPowerUsage", return_value=85000),
    ):
        provider = NvmlGpuProvider()
        devices = provider.get_devices()

        assert len(devices) == 1
        assert devices[0]["index"] == 1
        assert devices[0]["name"] == "RTX 5060 Ti"
        assert devices[0]["utilization_percent"]["value"] == 15.0


def test_nvml_provider_string_decoding() -> None:
    """NVML strings returned as either bytes or str must decode cleanly."""
    h0 = MagicMock()
    mem0 = MagicMock(total=16000000000, used=2000000000, free=14000000000)

    with (
        patch("pynvml.nvmlInit"),
        patch("pynvml.nvmlDeviceGetCount", return_value=1),
        patch("pynvml.nvmlDeviceGetHandleByIndex", return_value=h0),
        patch("pynvml.nvmlDeviceGetName", return_value=b"NVIDIA GeForce RTX 5060 Ti"),
        patch("pynvml.nvmlDeviceGetUUID", return_value=b"GPU-BYTES-UUID-1234"),
        patch("pynvml.nvmlDeviceGetPciInfo", return_value=MagicMock(busId=b"0000:01:00.0")),
        patch("pynvml.nvmlDeviceGetUtilizationRates", return_value=MagicMock(gpu=10)),
        patch("pynvml.nvmlDeviceGetTemperature", return_value=35),
        patch("pynvml.nvmlDeviceGetMemoryInfo", return_value=mem0),
        patch("pynvml.nvmlDeviceGetClockInfo", side_effect=[1500, 5000]),
        patch("pynvml.nvmlDeviceGetPowerUsage", return_value=50000),
    ):
        provider = NvmlGpuProvider()
        devices = provider.get_devices()

        assert len(devices) == 1
        assert devices[0]["name"] == "NVIDIA GeForce RTX 5060 Ti"
        assert devices[0]["uuid"] == "GPU-BYTES-UUID-1234"
        assert devices[0]["pci_bus_id"] == "0000:01:00.0"


def test_nvml_provider_uninitialized_recovery() -> None:
    """When driver is lost or uninitialized, state resets and retries on next cycle."""
    provider = NvmlGpuProvider()

    with (
        patch("pynvml.nvmlInit") as mock_init,
        patch(
            "pynvml.nvmlDeviceGetCount",
            side_effect=[
                pynvml.NVMLError(pynvml.NVML_ERROR_UNINITIALIZED),
                0,
            ],
        ),
    ):
        # Cycle 1: initialized initially, but query raises UNINITIALIZED
        provider.initialize()
        assert provider.is_initialized

        devices_c1 = provider.get_devices()
        assert devices_c1 == []
        # State should be reset to not initialized
        assert not provider.is_initialized
        assert "uninitialized" in str(provider.init_error).lower()

        # Cycle 2: next query must trigger nvmlInit retry
        devices_c2 = provider.get_devices()
        assert devices_c2 == []
        assert provider.is_initialized
        # nvmlInit was called twice: once manually, once during recovery
        assert mock_init.call_count == 2


def test_nvml_repeated_shutdown_idempotent() -> None:
    """Repeated shutdown calls must be idempotent and only invoke nvmlShutdown once."""
    with (
        patch("pynvml.nvmlInit"),
        patch("pynvml.nvmlShutdown") as mock_shutdown,
    ):
        provider = NvmlGpuProvider()
        provider.initialize()
        assert provider.is_initialized

        provider.shutdown()
        assert not provider.is_initialized
        assert mock_shutdown.call_count == 1

        # Second and third calls must be silent no-ops
        provider.shutdown()
        provider.shutdown()
        assert mock_shutdown.call_count == 1


def test_nvml_shutdown_partial_module_teardown() -> None:
    """During Python interpreter exit when module globals are torn down, shutdown must not crash."""
    with patch("pynvml.nvmlInit"):
        provider = NvmlGpuProvider()
        provider.initialize()
        assert provider.is_initialized

    # Simulate interpreter exit where pynvml global is cleared to None
    with patch("backend.monitoring.providers.nvidia_nvml.pynvml", None):
        provider.shutdown()
        assert not provider.is_initialized

        # __del__ under cleared global must also be completely silent
        provider.__del__()
