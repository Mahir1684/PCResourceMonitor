"""Unit tests for Storage telemetry collector."""

from unittest.mock import MagicMock, patch
import pytest

from backend.monitoring.storage import StorageCollector


def test_storage_collector_multi_volume() -> None:
    """Test dynamic discovery of multiple fixed storage volumes."""
    part1 = MagicMock(device="C:\\", mountpoint="C:\\", fstype="NTFS", opts="rw,fixed")
    part2 = MagicMock(device="D:\\", mountpoint="D:\\", fstype="NTFS", opts="rw,fixed")
    cdrom = MagicMock(device="E:\\", mountpoint="E:\\", fstype="", opts="ro,cdrom")

    usage_c = MagicMock(total=1000000000, used=400000000, free=600000000, percent=40.0)
    usage_d = MagicMock(total=2000000000, used=1500000000, free=500000000, percent=75.0)

    def mock_usage(path: str) -> MagicMock:
        return usage_c if path == "C:\\" else usage_d

    with (
        patch("psutil.disk_partitions", return_value=[part1, part2, cdrom]),
        patch("psutil.disk_usage", side_effect=mock_usage),
        patch("psutil.disk_io_counters", return_value=None),
    ):
        collector = StorageCollector()
        data = collector.collect()

        assert data["status"] == "ok"
        assert len(data["volumes"]) == 2
        mounts = [v["mount"] for v in data["volumes"]]
        assert "C:\\" in mounts
        assert "D:\\" in mounts
        assert "E:\\" not in mounts  # CD-ROM excluded
        for vol in data["volumes"]:
            assert vol["is_removable"] is False
            assert vol["drive_type"] == "fixed"
        assert data["io_throughput"]["status"] == "unavailable"
        assert "not available" in data["io_throughput"]["reason"]


def test_storage_collector_io_throughput_calculation() -> None:
    """Test throughput calculation between two successive samples."""
    part = MagicMock(device="C:\\", mountpoint="C:\\", fstype="NTFS", opts="rw,fixed")
    usage = MagicMock(total=1000, used=500, free=500, percent=50.0)

    io_sample1 = MagicMock(read_bytes=1000000, write_bytes=500000)
    io_sample2 = MagicMock(read_bytes=2000000, write_bytes=1000000)  # +1MB read, +500KB write

    with (
        patch("psutil.disk_partitions", return_value=[part]),
        patch("psutil.disk_usage", return_value=usage),
        patch("psutil.disk_io_counters", side_effect=[io_sample1, io_sample2]),
        patch("time.monotonic", side_effect=[100.0, 101.0]),  # dt = 1.0s
    ):
        collector = StorageCollector()

        # First sample establishes baseline
        data1 = collector.collect()
        assert data1["io_throughput"]["status"] == "unavailable"
        assert data1["io_throughput"]["read_bytes_per_second"] is None

        # Second sample calculates rate
        data2 = collector.collect()
        assert data2["io_throughput"]["status"] == "ok"
        assert data2["io_throughput"]["read_bytes_per_second"] == 1000000.0
        assert data2["io_throughput"]["write_bytes_per_second"] == 500000.0


def test_storage_collector_counter_reset() -> None:
    """Test that counter resets/rollovers do not produce negative rates."""
    part = MagicMock(device="C:\\", mountpoint="C:\\", fstype="NTFS", opts="rw,fixed")
    usage = MagicMock(total=1000, used=500, free=500, percent=50.0)

    io_sample1 = MagicMock(read_bytes=5000000, write_bytes=5000000)
    io_sample2 = MagicMock(read_bytes=1000, write_bytes=1000)  # Counter reset to near 0

    with (
        patch("psutil.disk_partitions", return_value=[part]),
        patch("psutil.disk_usage", return_value=usage),
        patch("psutil.disk_io_counters", side_effect=[io_sample1, io_sample2]),
        patch("time.monotonic", side_effect=[100.0, 101.0]),
    ):
        collector = StorageCollector()
        collector.collect()
        data2 = collector.collect()

        assert data2["io_throughput"]["status"] == "unavailable"
        assert data2["io_throughput"]["read_bytes_per_second"] is None
        assert "reset or rollover" in data2["io_throughput"]["reason"]


def test_storage_collector_includes_removable_drives() -> None:
    """Test that removable USB volumes and fixed drives are included while optical media is excluded."""
    fixed_part = MagicMock(device="C:\\", mountpoint="C:\\", fstype="NTFS", opts="rw,fixed")
    removable_part = MagicMock(device="F:\\", mountpoint="F:\\", fstype="FAT32", opts="rw,removable")
    cdrom_part = MagicMock(device="G:\\", mountpoint="G:\\", fstype="", opts="ro,cdrom")

    mock_usage = MagicMock(total=500000000, used=200000000, free=300000000, percent=40.0)

    with (
        patch("sys.platform", "win32"),
        patch("psutil.disk_partitions", return_value=[fixed_part, removable_part, cdrom_part]),
        patch("psutil.disk_usage", return_value=mock_usage),
        patch("psutil.disk_io_counters", return_value=None),
    ):
        collector = StorageCollector()
        data = collector.collect()

        assert data["status"] == "ok"
        by_mount = {v["mount"]: v for v in data["volumes"]}
        assert "C:\\" in by_mount
        assert by_mount["C:\\"]["is_removable"] is False
        assert by_mount["C:\\"]["drive_type"] == "fixed"
        assert "F:\\" in by_mount  # Removable USB drive included
        assert by_mount["F:\\"]["is_removable"] is True
        assert by_mount["F:\\"]["drive_type"] == "removable"
        assert "G:\\" not in by_mount  # CD-ROM excluded


def test_storage_collector_unreadable_partition_isolated() -> None:
    """Test that an unreadable or unready partition does not fail the entire collector."""
    part_c = MagicMock(device="C:\\", mountpoint="C:\\", fstype="NTFS", opts="rw,fixed")
    part_unready = MagicMock(device="E:\\", mountpoint="E:\\", fstype="FAT32", opts="rw,removable")
    part_d = MagicMock(device="D:\\", mountpoint="D:\\", fstype="NTFS", opts="rw,fixed")

    usage_ok = MagicMock(total=500000000, used=200000000, free=300000000, percent=40.0)

    def mock_disk_usage(mount: str) -> MagicMock:
        if mount == "E:\\":
            raise OSError("Device not ready")
        return usage_ok

    with (
        patch("sys.platform", "win32"),
        patch("psutil.disk_partitions", return_value=[part_c, part_unready, part_d]),
        patch("psutil.disk_usage", side_effect=mock_disk_usage),
        patch("psutil.disk_io_counters", return_value=None),
    ):
        collector = StorageCollector()
        data = collector.collect()

        assert data["status"] == "ok"
        mounts = [v["mount"] for v in data["volumes"]]
        assert "C:\\" in mounts
        assert "D:\\" in mounts
        assert "E:\\" not in mounts  # Unready drive safely skipped
