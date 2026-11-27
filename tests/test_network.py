"""Unit tests for Network telemetry collector."""

from unittest.mock import MagicMock, patch
import pytest

from backend.monitoring.network import NetworkCollector, is_virtual_or_loopback


def test_is_virtual_or_loopback() -> None:
    """Test filtering logic for virtual and loopback adapters."""
    assert is_virtual_or_loopback("Loopback Pseudo-Interface 1") is True
    assert is_virtual_or_loopback("vEthernet (Default Switch)") is True
    assert is_virtual_or_loopback("Tailscale") is True
    assert is_virtual_or_loopback("OpenVPN Connect DCO Adapter") is True
    assert is_virtual_or_loopback("Local Area Connection* 9") is True
    assert is_virtual_or_loopback("Local Area Connection* 10") is True
    assert is_virtual_or_loopback("Wi-Fi* 1") is True
    assert is_virtual_or_loopback("Bluetooth Network Connection") is True
    assert is_virtual_or_loopback("Ethernet") is False
    assert is_virtual_or_loopback("Wi-Fi") is False
    assert is_virtual_or_loopback("Ethernet 3") is False


def test_network_collector_throughput() -> None:
    """Test rate calculation across successive samples."""
    stats = {
        "Ethernet": MagicMock(isup=True),
        "Tailscale": MagicMock(isup=True),
        "Loopback": MagicMock(isup=True),
    }

    io_sample1 = {
        "Ethernet": MagicMock(bytes_recv=1000000, bytes_sent=500000),
        "Tailscale": MagicMock(bytes_recv=50000, bytes_sent=20000),
    }
    io_sample2 = {
        "Ethernet": MagicMock(bytes_recv=1100000, bytes_sent=550000),  # +100KB recv, +50KB sent
        "Tailscale": MagicMock(bytes_recv=60000, bytes_sent=25000),
    }

    with (
        patch("psutil.net_if_stats", return_value=stats),
        patch("psutil.net_io_counters", side_effect=[io_sample1, io_sample2]),
        patch("time.monotonic", side_effect=[200.0, 201.0]),  # dt = 1.0s
    ):
        collector = NetworkCollector()

        # Baseline sample
        data1 = collector.collect()
        assert data1["status"] == "ok"
        eth1 = next(i for i in data1["interfaces"] if i["name"] == "Ethernet")
        assert eth1["download_bytes_per_second"] is None

        # Second sample
        data2 = collector.collect()
        eth2 = next(i for i in data2["interfaces"] if i["name"] == "Ethernet")
        assert eth2["is_physical"] is True
        assert eth2["download_bytes_per_second"] == 100000.0
        assert eth2["upload_bytes_per_second"] == 50000.0

        ts2 = next(i for i in data2["interfaces"] if i["name"] == "Tailscale")
        assert ts2["is_physical"] is False
        assert ts2["download_bytes_per_second"] == 10000.0

        # Summary should aggregate physical interfaces only
        assert data2["summary"]["primary_interface"] == "Ethernet"
        assert data2["summary"]["download_bytes_per_second"] == 100000.0
        assert data2["summary"]["upload_bytes_per_second"] == 50000.0


def test_network_counter_reset() -> None:
    """Test safe handling when byte counters decrease (interface reset)."""
    stats = {"Ethernet": MagicMock(isup=True)}
    io_sample1 = {"Ethernet": MagicMock(bytes_recv=5000000, bytes_sent=5000000)}
    io_sample2 = {"Ethernet": MagicMock(bytes_recv=1000, bytes_sent=1000)}  # Reset

    with (
        patch("psutil.net_if_stats", return_value=stats),
        patch("psutil.net_io_counters", side_effect=[io_sample1, io_sample2]),
        patch("time.monotonic", side_effect=[200.0, 201.0]),
    ):
        collector = NetworkCollector()
        collector.collect()
        data2 = collector.collect()

        eth = next(i for i in data2["interfaces"] if i["name"] == "Ethernet")
        assert eth["download_bytes_per_second"] is None
        assert eth["upload_bytes_per_second"] is None


def test_primary_interface_selection_prioritizes_active_traffic() -> None:
    """Primary physical adapter selection should prioritize active traffic over idle adapters."""
    stats = {
        "Ethernet": MagicMock(isup=True),
        "Wi-Fi": MagicMock(isup=True),
        "Local Area Connection* 10": MagicMock(isup=True),  # Virtual miniport
    }

    # Sample 1 (baseline)
    io_sample1 = {
        "Ethernet": MagicMock(bytes_recv=1000000, bytes_sent=500000),
        "Wi-Fi": MagicMock(bytes_recv=1000000, bytes_sent=500000),
        "Local Area Connection* 10": MagicMock(bytes_recv=9000000, bytes_sent=9000000),
    }
    # Sample 2: Wi-Fi has active transfer, Ethernet is idle
    io_sample2 = {
        "Ethernet": MagicMock(bytes_recv=1000000, bytes_sent=500000),  # 0 rate
        "Wi-Fi": MagicMock(bytes_recv=1200000, bytes_sent=550000),     # 200KB/s recv, 50KB/s sent
        "Local Area Connection* 10": MagicMock(bytes_recv=9900000, bytes_sent=9900000),
    }

    with (
        patch("psutil.net_if_stats", return_value=stats),
        patch("psutil.net_io_counters", side_effect=[io_sample1, io_sample2]),
        patch("time.monotonic", side_effect=[100.0, 101.0]),
    ):
        collector = NetworkCollector()
        collector.collect()
        data = collector.collect()

        summary = data["summary"]
        # Wi-Fi should be chosen as primary interface because it has active traffic
        assert summary["primary_interface"] == "Wi-Fi"
        assert summary["status"] == "connected"
        assert summary["download_bytes_per_second"] == 200000.0
        assert summary["upload_bytes_per_second"] == 50000.0


def test_network_disconnected_when_all_physical_down() -> None:
    """When all physical network adapters are disconnected, summary indicates disconnected state."""
    stats = {
        "Ethernet": MagicMock(isup=False),
        "Wi-Fi": MagicMock(isup=False),
        "Loopback": MagicMock(isup=True),
    }
    io_sample = {
        "Ethernet": MagicMock(bytes_recv=1000, bytes_sent=500),
        "Wi-Fi": MagicMock(bytes_recv=2000, bytes_sent=1000),
        "Loopback": MagicMock(bytes_recv=9999, bytes_sent=9999),
    }

    with (
        patch("psutil.net_if_stats", return_value=stats),
        patch("psutil.net_io_counters", return_value=io_sample),
        patch("time.monotonic", return_value=100.0),
    ):
        collector = NetworkCollector()
        data = collector.collect()

        summary = data["summary"]
        assert summary["primary_interface"] is None
        assert summary["status"] == "disconnected"
        assert summary["download_bytes_per_second"] is None
        assert summary["upload_bytes_per_second"] is None

