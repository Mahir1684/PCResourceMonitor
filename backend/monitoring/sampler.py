"""Background metric sampling engine for PCResourceMonitor.

Runs scheduled metric collection in an independent background thread,
protecting snapshot updates with a lock and isolating collector failures
so that a failing sensor never crashes other providers or the server.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from backend.monitoring.snapshot import SnapshotStore


logger = logging.getLogger(__name__)

# Type alias for a metric collector callable returning section data
MetricCollector = Callable[[], dict[str, Any]]


def _utc_now_iso() -> str:
    """Return the current UTC timestamp formatted as ISO 8601 with Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class MetricSampler:
    """Orchestrates periodic background collection of system metrics."""

    def __init__(
        self,
        store: SnapshotStore,
        interval_seconds: float = 1.0,
        collectors: Mapping[str, MetricCollector] | None = None,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError(f"Sampling interval must be positive, got {interval_seconds}.")

        self._store = store
        self._interval = float(interval_seconds)
        self._collectors: dict[str, MetricCollector] = {}
        if collectors:
            self._collectors.update(collectors)

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def interval_seconds(self) -> float:
        """Configured sampling interval in seconds."""
        return self._interval

    @property
    def is_running(self) -> bool:
        """True if the background sampling thread is currently active."""
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def register_collector(self, name: str, collector: MetricCollector) -> None:
        """Register a new named metric collector."""
        if not name or not isinstance(name, str):
            raise ValueError("Collector name must be a non-empty string.")
        if not callable(collector):
            raise TypeError(f"Collector for '{name}' must be callable.")
        with self._lock:
            self._collectors[name] = collector

    def unregister_collector(self, name: str) -> None:
        """Remove a named metric collector."""
        with self._lock:
            self._collectors.pop(name, None)

    def sample_once(self) -> dict[str, Any]:
        """Execute a single sampling pass across all registered collectors.
        
        Collector failures are safely isolated into per-section error payloads.
        Returns the updated snapshot dictionary.
        """
        with self._lock:
            collectors_snapshot = list(self._collectors.items())

        new_sections: dict[str, Any] = {}
        for section_name, collector_fn in collectors_snapshot:
            try:
                result = collector_fn()
                if not isinstance(result, dict):
                    new_sections[section_name] = {
                        "status": "error",
                        "sampled_at": _utc_now_iso(),
                        "error": {
                            "code": "INVALID_COLLECTOR_OUTPUT",
                            "message": f"Collector '{section_name}' returned non-dict type {type(result).__name__}.",
                        },
                    }
                else:
                    new_sections[section_name] = result
            except Exception as exc:
                logger.warning("Collector '%s' raised an exception: %s", section_name, exc)
                new_sections[section_name] = {
                    "status": "error",
                    "sampled_at": _utc_now_iso(),
                    "error": {
                        "code": "COLLECTION_FAILED",
                        "message": f"Collector '{section_name}' failed: {exc.__class__.__name__}",
                    },
                }

        return self._store.update_sections(new_sections)

    def start(self) -> None:
        """Start the background sampling thread."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("Sampler is already running.")

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="pc-resource-sampler",
                daemon=True,
            )
            self._thread.start()
            logger.info("MetricSampler started with %.1fs interval.", self._interval)

    def stop(self, timeout: float | None = 5.0) -> None:
        """Signal the sampling thread to stop and wait for termination."""
        with self._lock:
            thread = self._thread
            if thread is None or not thread.is_alive():
                self._thread = None
                return

            self._stop_event.set()

        # Join outside the lock to avoid deadlock if the thread checks the lock
        thread.join(timeout=timeout)
        with self._lock:
            if thread.is_alive():
                logger.warning("Sampler thread did not terminate within %.1fs timeout.", timeout)
            self._thread = None
            logger.info("MetricSampler stopped.")

    def _run_loop(self) -> None:
        """Internal loop executed on the background worker thread."""
        while not self._stop_event.is_set():
            try:
                self.sample_once()
            except Exception as exc:
                logger.error("Unexpected error in sampling loop: %s", exc)

            # Responsive wait: wakes immediately when stop() sets the event
            self._stop_event.wait(timeout=self._interval)
