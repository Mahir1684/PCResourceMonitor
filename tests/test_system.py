"""Unit tests for System metadata and uptime collector."""

from unittest.mock import patch
import pytest

from backend.monitoring.system import SystemCollector, resolve_cpu_name, resolve_os_name


def test_system_collector_success() -> None:
    """Test standard successful system metadata collection."""
    with (
        patch("socket.gethostname", return_value="TEST-RIG"),
        patch("backend.monitoring.system.resolve_os_name", return_value="Windows 11 (Build 10.0.26300)"),
        patch("backend.monitoring.system.resolve_cpu_name", return_value="AMD Ryzen 5 9600X 6-Core Processor"),
        patch("psutil.boot_time", return_value=1700000000.0),
        patch("time.time", return_value=1700036000.0),  # 36,000s = 10 hrs uptime
    ):
        collector = SystemCollector()
        data = collector.collect()

        assert data["status"] == "ok"
        assert data["hostname"] == "TEST-RIG"
        assert data["os"] == "Windows 11 (Build 10.0.26300)"
        assert data["cpu_name"] == "AMD Ryzen 5 9600X 6-Core Processor"
        assert data["uptime_seconds"] == 36000
        assert data["boot_time_timestamp"] == 1700000000.0


def test_resolve_cpu_name_fallback() -> None:
    """Test CPU name resolution when winreg is unavailable."""
    with (
        patch("sys.platform", "linux"),
        patch("platform.processor", return_value="x86_64"),
    ):
        name = resolve_cpu_name()
        assert name == "x86_64"


def test_system_collector_exception_handling() -> None:
    """Test error reporting when psutil boot_time raises an exception."""
    with (
        patch("socket.gethostname", return_value="TEST-RIG"),
        patch("backend.monitoring.system.resolve_os_name", return_value="Windows 11"),
        patch("backend.monitoring.system.resolve_cpu_name", return_value="AMD Ryzen"),
        patch("psutil.boot_time", side_effect=RuntimeError("WMI error")),
    ):
        collector = SystemCollector()
        data = collector.collect()

        assert data["status"] == "error"
        assert data["error"]["code"] == "SYSTEM_COLLECTION_ERROR"
        assert "WMI error" in data["error"]["message"]
