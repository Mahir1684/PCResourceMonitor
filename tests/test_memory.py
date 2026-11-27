"""Unit tests for Memory telemetry collector."""

from unittest.mock import MagicMock, patch
import pytest

from backend.monitoring.memory import MemoryCollector


def test_memory_collector_success() -> None:
    """Test standard successful memory metric collection."""
    mock_vm = MagicMock()
    mock_vm.total = 17179869184
    mock_vm.used = 8589934592
    mock_vm.available = 8589934592
    mock_vm.percent = 50.0

    with patch("psutil.virtual_memory", return_value=mock_vm):
        collector = MemoryCollector()
        data = collector.collect()

        assert data["status"] == "ok"
        assert data["total_bytes"] == 17179869184
        assert data["used_bytes"] == 8589934592
        assert data["available_bytes"] == 8589934592
        assert data["usage_percent"] == 50.0
        assert isinstance(data["sampled_at"], str)


def test_memory_collector_exception_handling() -> None:
    """Test error reporting when memory query raises an exception."""
    with patch("psutil.virtual_memory", side_effect=OSError("OS kernel failure")):
        collector = MemoryCollector()
        data = collector.collect()

        assert data["status"] == "error"
        assert data["error"]["code"] == "MEMORY_COLLECTION_ERROR"
        assert "OS kernel failure" in data["error"]["message"]
