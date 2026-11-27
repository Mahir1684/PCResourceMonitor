"""In-game FPS and frame-timing telemetry collector using PresentMon.

Monitors active 3D applications, frame rates (FPS), frame times (ms), and
graphics runtimes (DXGI, Direct3D, Vulkan) via PresentMon ETW stream.
Runs silently in a background thread with zero console window pop-ups
(CREATE_NO_WINDOW / SW_HIDE).
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import logging
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any


logger = logging.getLogger(__name__)

CREATE_NO_WINDOW = 0x08000000
DEFAULT_TOOLS_DIR = Path(__file__).resolve().parent.parent.parent / "tools"
DEFAULT_PRESENTMON_PATH = DEFAULT_TOOLS_DIR / "PresentMon.exe"

# Non-game system and desktop processes to ignore when tracking 3D presentation
IGNORED_SYSTEM_PROCESSES = {
    "dwm.exe",
    "explorer.exe",
    "shellexperiencehost.exe",
    "startmenuexperiencehost.exe",
    "searchhost.exe",
    "lockapp.exe",
    "applicationframehost.exe",
    "textinputhost.exe",
    "taskmgr.exe",
    "systemsettings.exe",
    "python.exe",
    "pythonw.exe",
    "powershell.exe",
    "cmd.exe",
    "conhost.exe",
    "presentmon.exe",
}

# Timeout in seconds after which an application is considered idle (not presenting)
IDLE_TIMEOUT_SECONDS = 1.5


def _utc_now_iso() -> str:
    """Return the current UTC timestamp formatted as ISO 8601 with Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class FpsCollector:
    """Non-blocking collector for real-time game FPS and frame-time telemetry."""

    def __init__(
        self,
        presentmon_path: Path | str | None = None,
        autostart: bool = True,
    ) -> None:
        self._path = Path(presentmon_path) if presentmon_path else DEFAULT_PRESENTMON_PATH
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._proc: subprocess.Popen[str] | None = None

        # State protected by _lock
        self._status: str = "initializing"
        self._reason: str | None = None
        self._active_process: str | None = None
        self._graphics_api: str | None = None
        self._recent_frames: deque[tuple[float, float]] = deque(maxlen=120)
        self._last_frame_timestamp: float = 0.0

        if autostart:
            self.start()

    @property
    def is_running(self) -> bool:
        """True if the background worker thread is active."""
        with self._lock:
            return self._worker_thread is not None and self._worker_thread.is_alive()

    def start(self) -> None:
        """Start the background PresentMon reader thread."""
        with self._lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="FpsCollector-PresentMon",
                daemon=True,
            )
            self._worker_thread.start()

    def stop(self) -> None:
        """Stop PresentMon and join the reader thread."""
        self._stop_event.set()
        proc = None
        with self._lock:
            proc = self._proc
            self._proc = None

        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass

        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

    def _worker_loop(self) -> None:
        """Background loop spawning and reading from PresentMon.exe."""
        while not self._stop_event.is_set():
            if not self._path.exists():
                with self._lock:
                    self._status = "unavailable"
                    self._reason = f"PresentMon binary not found at '{self._path}'."
                self._stop_event.wait(5.0)
                continue

            # Build command line
            cmd = [
                str(self._path),
                "--output_stdout",
                "--no_console_stats",
                "--stop_existing_session",
                "--v1_metrics",
            ]

            startupinfo = None
            creationflags = 0
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
                creationflags = CREATE_NO_WINDOW

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                    startupinfo=startupinfo,
                    creationflags=creationflags,
                )
            except Exception as exc:
                logger.error("Failed to spawn PresentMon: %s", exc)
                with self._lock:
                    self._status = "error"
                    self._reason = f"Failed to execute PresentMon: {exc}"
                self._stop_event.wait(5.0)
                continue

            with self._lock:
                self._proc = proc
                self._status = "ok"
                self._reason = None

            # Read stdout
            self._read_stream(proc)

            # Process exited or stopped
            if self._stop_event.is_set():
                break

            # Back off slightly before retrying to prevent CPU spin
            self._stop_event.wait(3.0)

    def _read_stream(self, proc: subprocess.Popen[str]) -> None:
        """Parse streaming CSV lines from PresentMon stdout."""
        app_col = 0
        runtime_col = 3
        dropped_col = 6
        ms_between_col = 9
        header_parsed = False

        if proc.stdout is None:
            return

        for line in proc.stdout:
            if self._stop_event.is_set():
                break

            line = line.strip()
            if not line:
                continue

            # Check for error banners
            if line.startswith("error:"):
                logger.warning("PresentMon reported: %s", line)
                with self._lock:
                    self._status = "unavailable"
                    self._reason = line
                continue
            if line.startswith("warning:"):
                continue

            # Split CSV
            parts = [p.strip().strip('"') for p in line.split(",")]
            if not parts:
                continue

            # Parse header
            if not header_parsed:
                if "Application" in parts and "msBetweenPresents" in parts:
                    try:
                        app_col = parts.index("Application")
                        ms_between_col = parts.index("msBetweenPresents")
                        if "Runtime" in parts:
                            runtime_col = parts.index("Runtime")
                        if "Dropped" in parts:
                            dropped_col = parts.index("Dropped")
                        header_parsed = True
                    except ValueError:
                        pass
                continue

            if len(parts) <= max(app_col, ms_between_col):
                continue

            app_name = parts[app_col]
            if not app_name or app_name.lower() in IGNORED_SYSTEM_PROCESSES:
                continue

            # Check dropped
            if dropped_col < len(parts) and parts[dropped_col] == "1":
                continue

            try:
                ms_between = float(parts[ms_between_col])
            except ValueError:
                continue

            if ms_between <= 0.0 or ms_between > 1000.0:
                continue

            runtime = parts[runtime_col] if runtime_col < len(parts) else "Unknown"
            now = time.monotonic()

            with self._lock:
                self._status = "ok"
                self._active_process = app_name
                self._graphics_api = runtime
                self._last_frame_timestamp = now
                self._recent_frames.append((now, ms_between))

        # Check stderr if process terminated unexpectedly
        ret = proc.poll()
        if ret is not None and ret != 0:
            err = ""
            if proc.stderr is not None:
                try:
                    err = proc.stderr.read().strip()
                except Exception:
                    pass
            with self._lock:
                if "access denied" in err.lower():
                    self._status = "unavailable"
                    self._reason = (
                        "PresentMon requires administrative privileges or membership "
                        "in 'Performance Log Users' user group."
                    )
                else:
                    self._status = "unavailable"
                    self._reason = err or f"PresentMon exited with code {ret}."

    def collect(self) -> dict[str, Any]:
        """Return the current FPS snapshot in a non-blocking manner."""
        sampled_at = _utc_now_iso()
        now = time.monotonic()

        with self._lock:
            status = self._status
            reason = self._reason

            # If unavailable/error, report immediately
            if status != "ok":
                return {
                    "status": status,
                    "sampled_at": sampled_at,
                    "fps": None,
                    "frame_time_ms": None,
                    "active_process": None,
                    "graphics_api": None,
                    "is_presenting": False,
                    "reason": reason,
                }

            # Check idle timeout (no frames from a game in last 1.5 seconds)
            if (now - self._last_frame_timestamp) > IDLE_TIMEOUT_SECONDS:
                return {
                    "status": "ok",
                    "sampled_at": sampled_at,
                    "fps": None,
                    "frame_time_ms": None,
                    "active_process": "Idle / Desktop",
                    "graphics_api": None,
                    "is_presenting": False,
                }

            # Filter frames within the last 1.0 second
            recent_times = [ms for t, ms in self._recent_frames if (now - t) <= 1.0]
            if not recent_times:
                recent_times = [ms for _, ms in self._recent_frames]

            if recent_times:
                avg_frame_time = sum(recent_times) / len(recent_times)
                fps = (1000.0 / avg_frame_time) if avg_frame_time > 0 else 0.0
            else:
                avg_frame_time = None
                fps = None

            return {
                "status": "ok",
                "sampled_at": sampled_at,
                "fps": round(fps, 1) if fps is not None else None,
                "frame_time_ms": round(avg_frame_time, 2) if avg_frame_time is not None else None,
                "active_process": self._active_process,
                "graphics_api": self._graphics_api,
                "is_presenting": True,
            }
