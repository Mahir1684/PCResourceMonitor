"""Unit tests for CPU telemetry collector."""

from unittest.mock import MagicMock, patch
import pytest

from backend.monitoring.cpu import CpuCollector


def test_cpu_collector_success() -> None:
    """Test standard successful CPU metric collection."""
    mock_freq = MagicMock()
    mock_freq.current = 4200.0

    with (
        patch("psutil.cpu_percent", side_effect=[0.0, [10.0, 20.0], 25.5, [20.0, 31.0]]),
        patch("psutil.cpu_freq", return_value=mock_freq),
        patch("psutil.cpu_count", side_effect=[6, 12]),
    ):
        collector = CpuCollector()
        data = collector.collect()

        assert data["status"] == "ok"
        assert data["usage_percent"] == 25.5
        assert data["per_core_percent"] == [20.0, 31.0]
        assert data["frequency_mhz"] == 4200.0
        assert data["cores_physical"] == 6
        assert data["cores_logical"] == 12
        assert data["temperature_c"]["status"] == "unavailable"
        assert data["temperature_c"]["value"] is None
        assert data["power_watts"]["status"] == "unavailable"
        assert data["power_watts"]["value"] is None
        assert data["core_temperatures_c"] == []


def test_cpu_collector_with_active_bridge() -> None:
    """When LHM bridge provides CPU hardware sensors, they enrich the telemetry snapshot."""
    mock_bridge = MagicMock()
    mock_bridge.get_cpu_sensors.return_value = {
        "package_temperature_c": 58.2,
        "core_temperatures_c": [55.0, 56.5, 54.0, 57.2, 53.8, 56.0],
        "package_power_watts": 76.8,
        "status": "ok",
        "reason": None,
    }

    mock_freq = MagicMock()
    mock_freq.current = 4800.0

    with (
        patch("psutil.cpu_percent", side_effect=[0.0, [], 40.0, [35.0, 45.0]]),
        patch("psutil.cpu_freq", return_value=mock_freq),
        patch("psutil.cpu_count", side_effect=[6, 12]),
    ):
        collector = CpuCollector(bridge_client=mock_bridge)
        data = collector.collect()

        assert data["status"] == "ok"
        assert data["usage_percent"] == 40.0
        assert data["temperature_c"]["status"] == "ok"
        assert data["temperature_c"]["value"] == 58.2
        assert data["core_temperatures_c"] == [55.0, 56.5, 54.0, 57.2, 53.8, 56.0]
        assert data["power_watts"]["status"] == "ok"
        assert data["power_watts"]["value"] == 76.8


def test_cpu_collector_bridge_failure_isolation() -> None:
    """When the bridge client fails or raises, core psutil metrics still succeed."""
    mock_bridge = MagicMock()
    mock_bridge.get_cpu_sensors.side_effect = RuntimeError("Bridge communication failure")

    with (
        patch("psutil.cpu_percent", side_effect=[0.0, [], 18.0, [18.0]]),
        patch("psutil.cpu_freq", return_value=None),
        patch("psutil.cpu_count", side_effect=[4, 8]),
    ):
        collector = CpuCollector(bridge_client=mock_bridge)
        data = collector.collect()

        assert data["status"] == "ok"
        assert data["usage_percent"] == 18.0
        assert data["temperature_c"]["status"] == "unavailable"
        assert "Bridge communication failure" in data["temperature_c"]["reason"]
        assert data["power_watts"]["status"] == "unavailable"
        assert data["core_temperatures_c"] == []


def test_cpu_collector_missing_frequency() -> None:
    """Test graceful handling when CPU frequency cannot be read."""
    with (
        patch("psutil.cpu_percent", side_effect=[0.0, [], 15.0, [15.0]]),
        patch("psutil.cpu_freq", return_value=None),
        patch("psutil.cpu_count", side_effect=[4, 8]),
    ):
        collector = CpuCollector()
        data = collector.collect()

        assert data["status"] == "ok"
        assert data["frequency_mhz"] is None


def test_cpu_collector_exception_handling() -> None:
    """Test error reporting when psutil raises an exception."""
    with patch("psutil.cpu_percent", side_effect=RuntimeError("psutil hardware access error")):
        collector = CpuCollector()
        data = collector.collect()

        assert data["status"] == "error"
        assert data["error"]["code"] == "CPU_COLLECTION_ERROR"
        assert "psutil hardware access error" in data["error"]["message"]
