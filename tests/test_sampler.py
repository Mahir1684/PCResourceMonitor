"""Unit tests for MetricSampler."""

import time
import pytest

from backend.monitoring.snapshot import SnapshotStore, STATUS_OK, STATUS_ERROR, STATUS_PARTIAL
from backend.monitoring.sampler import MetricSampler


def test_sampler_interval_validation() -> None:
    """Interval must be a positive float."""
    store = SnapshotStore()
    sampler = MetricSampler(store, interval_seconds=0.5)
    assert sampler.interval_seconds == 0.5

    with pytest.raises(ValueError, match="Sampling interval must be positive"):
        MetricSampler(store, interval_seconds=0)

    with pytest.raises(ValueError, match="Sampling interval must be positive"):
        MetricSampler(store, interval_seconds=-1.0)


def test_register_and_unregister_collectors() -> None:
    """Collectors can be registered and removed safely."""
    store = SnapshotStore()
    sampler = MetricSampler(store)

    sampler.register_collector("cpu", lambda: {"status": STATUS_OK, "usage": 15.0})
    snap = sampler.sample_once()
    assert "cpu" in snap["sections"]
    assert snap["sections"]["cpu"]["usage"] == 15.0

    sampler.unregister_collector("cpu")
    snap = sampler.sample_once()
    assert "cpu" in snap["sections"]  # Retained from store until replaced or overwritten


def test_register_invalid_collector() -> None:
    """Invalid collector names or callables must raise exceptions."""
    store = SnapshotStore()
    sampler = MetricSampler(store)

    with pytest.raises(ValueError, match="Collector name must be a non-empty string"):
        sampler.register_collector("", lambda: {})  # type: ignore

    with pytest.raises(TypeError, match="must be callable"):
        sampler.register_collector("invalid", "not_callable")  # type: ignore


def test_collector_error_isolation() -> None:
    """A failing collector must not crash the sampler and must isolate the failure to its section."""
    store = SnapshotStore()
    sampler = MetricSampler(store)

    def good_collector() -> dict:
        return {"status": STATUS_OK, "data": 42}

    def failing_collector() -> dict:
        raise RuntimeError("Simulated hardware bus disconnect!")

    sampler.register_collector("good", good_collector)
    sampler.register_collector("bad", failing_collector)

    # sample_once must not raise an exception
    snap = sampler.sample_once()

    assert snap["sections"]["good"]["status"] == STATUS_OK
    assert snap["sections"]["good"]["data"] == 42

    assert snap["sections"]["bad"]["status"] == STATUS_ERROR
    assert snap["sections"]["bad"]["error"]["code"] == "COLLECTION_FAILED"
    assert "RuntimeError" in snap["sections"]["bad"]["error"]["message"]
    # Overall status should be partial because good succeeded while bad failed
    assert snap["overall_status"] == STATUS_PARTIAL


def test_collector_invalid_return_type_handling() -> None:
    """If a collector returns a non-dict value, it should be recorded as an error section."""
    store = SnapshotStore()
    sampler = MetricSampler(store)

    sampler.register_collector("bad_type", lambda: "not a dict")  # type: ignore
    snap = sampler.sample_once()

    assert snap["sections"]["bad_type"]["status"] == STATUS_ERROR
    assert snap["sections"]["bad_type"]["error"]["code"] == "INVALID_COLLECTOR_OUTPUT"


def test_background_thread_lifecycle() -> None:
    """Test start and clean stop of background sampler thread."""
    store = SnapshotStore()
    call_count = 0

    def counter_collector() -> dict:
        nonlocal call_count
        call_count += 1
        return {"status": STATUS_OK, "count": call_count}

    sampler = MetricSampler(store, interval_seconds=0.05, collectors={"counter": counter_collector})
    assert not sampler.is_running

    sampler.start()
    assert sampler.is_running

    # Attempting to start again should raise RuntimeError
    with pytest.raises(RuntimeError, match="already running"):
        sampler.start()

    # Wait briefly for multiple sampling cycles
    time.sleep(0.18)

    sampler.stop()
    assert not sampler.is_running
    assert call_count >= 2

    snap = store.get_snapshot()
    assert snap["sequence"] >= 2
    assert snap["sections"]["counter"]["count"] >= 2


def test_stop_when_not_running() -> None:
    """Calling stop on an unstarted sampler should be a safe no-op."""
    store = SnapshotStore()
    sampler = MetricSampler(store)
    assert not sampler.is_running
    sampler.stop()  # Should not raise
    assert not sampler.is_running
