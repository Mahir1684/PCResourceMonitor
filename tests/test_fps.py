"""Unit tests for FpsCollector (PresentMon integration)."""

from collections import deque
from pathlib import Path
import time
from unittest.mock import MagicMock, patch
import pytest

from backend.monitoring.fps import (
    FpsCollector,
    IGNORED_SYSTEM_PROCESSES,
    IDLE_TIMEOUT_SECONDS,
)


def test_fps_collector_binary_not_found(tmp_path: Path) -> None:
    """When PresentMon.exe is not found, collector returns unavailable status."""
    non_existent = tmp_path / "NonExistentPresentMon.exe"
    collector = FpsCollector(presentmon_path=non_existent, autostart=False)
    # Simulate worker loop check
    collector._path = non_existent
    res = collector.collect()

    assert res["status"] in ("initializing", "unavailable")
    assert res["fps"] is None
    assert res["frame_time_ms"] is None
    assert res["is_presenting"] is False


def test_fps_collector_idle_when_no_frames() -> None:
    """When PresentMon is running but no game has presented, reports Idle / Desktop."""
    collector = FpsCollector(autostart=False)
    collector._status = "ok"
    collector._last_frame_timestamp = 0.0  # long time ago

    res = collector.collect()
    assert res["status"] == "ok"
    assert res["fps"] is None
    assert res["frame_time_ms"] is None
    assert res["active_process"] == "Idle / Desktop"
    assert res["is_presenting"] is False


def test_fps_collector_active_frames() -> None:
    """When game frames are arriving, calculates smoothed FPS and average frame time."""
    collector = FpsCollector(autostart=False)
    collector._status = "ok"
    collector._active_process = "Cyberpunk2077.exe"
    collector._graphics_api = "D3D12"

    now = time.monotonic()
    collector._last_frame_timestamp = now
    # Simulate 60 FPS (16.666 ms per frame)
    for _ in range(30):
        collector._recent_frames.append((now, 16.6666))

    res = collector.collect()
    assert res["status"] == "ok"
    assert res["is_presenting"] is True
    assert res["active_process"] == "Cyberpunk2077.exe"
    assert res["graphics_api"] == "D3D12"
    assert res["fps"] == 60.0
    assert res["frame_time_ms"] == 16.67


def test_fps_collector_parses_csv_stream() -> None:
    """_read_stream parses CSV header and valid frame lines, ignoring system apps."""
    collector = FpsCollector(autostart=False)

    csv_data = [
        "Application,ProcessID,SwapChainAddress,Runtime,SyncInterval,PresentFlags,Dropped,TimeInSeconds,msInPresentAPI,msBetweenPresents,msBetweenDisplayChange,msUntilRenderComplete,msUntilDisplayed\n",
        '"dwm.exe",100,0x1,DXGI,1,0,0,1.0,0.5,16.6,16.6,10.0,16.6\n',
        '"explorer.exe",200,0x2,DXGI,1,0,0,1.0,0.5,16.6,16.6,10.0,16.6\n',
        '"Witcher3.exe",300,0x3,D3D11,1,0,0,1.0,0.5,8.3333,8.3333,5.0,8.3333\n',
        '"Witcher3.exe",300,0x3,D3D11,1,0,0,1.0,0.5,8.3333,8.3333,5.0,8.3333\n',
    ]

    mock_proc = MagicMock()
    mock_proc.stdout = iter(csv_data)
    mock_proc.poll.return_value = 0

    collector._read_stream(mock_proc)

    assert collector._active_process == "Witcher3.exe"
    assert collector._graphics_api == "D3D11"
    assert len(collector._recent_frames) == 2

    res = collector.collect()
    assert res["status"] == "ok"
    assert res["is_presenting"] is True
    assert res["active_process"] == "Witcher3.exe"
    assert res["fps"] == 120.0
    assert res["frame_time_ms"] == 8.33


def test_fps_collector_handles_access_denied() -> None:
    """When PresentMon fails with access denied, reports permission explanation."""
    collector = FpsCollector(autostart=False)

    mock_proc = MagicMock()
    mock_proc.stdout = iter([])
    mock_proc.poll.return_value = 1
    mock_proc.stderr.read.return_value = "error: failed to start trace session: access denied.\nPresentMon requires either administrative privileges..."

    collector._read_stream(mock_proc)

    assert collector._status == "unavailable"
    assert "Performance Log Users" in (collector._reason or "")

    res = collector.collect()
    assert res["status"] == "unavailable"
    assert res["fps"] is None
    assert "Performance Log Users" in res["reason"]
