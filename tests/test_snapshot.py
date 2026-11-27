"""Unit tests for SnapshotStore."""

import concurrent.futures
from datetime import datetime, timezone
import pytest

from backend.monitoring.snapshot import (
    SnapshotStore,
    SCHEMA_VERSION,
    STATUS_INITIALIZING,
    STATUS_OK,
    STATUS_PARTIAL,
    STATUS_ERROR,
)


def test_initial_snapshot_state() -> None:
    """A fresh SnapshotStore should initialize with sequence 0 and initializing status."""
    store = SnapshotStore()
    snap = store.get_snapshot()

    assert snap["schema_version"] == SCHEMA_VERSION
    assert snap["sequence"] == 0
    assert snap["overall_status"] == STATUS_INITIALIZING
    assert snap["sections"] == {}
    assert isinstance(snap["generated_at"], str)
    assert snap["generated_at"].endswith("Z")


def test_initial_snapshot_with_data() -> None:
    """A store initialized with sections should start with sequence 1 and calculated status."""
    initial = {"cpu": {"status": "ok", "usage": 20.0}}
    store = SnapshotStore(initial_sections=initial)
    snap = store.get_snapshot()

    assert snap["sequence"] == 1
    assert snap["overall_status"] == STATUS_OK
    assert "cpu" in snap["sections"]
    assert snap["sections"]["cpu"]["usage"] == 20.0


def test_sequence_increments_monotonically() -> None:
    """Each update to the snapshot store should increment the sequence number by 1."""
    store = SnapshotStore()
    assert store.sequence == 0

    snap1 = store.update_sections({"cpu": {"status": "ok"}})
    assert snap1["sequence"] == 1
    assert store.sequence == 1

    snap2 = store.update_sections({"memory": {"status": "ok"}})
    assert snap2["sequence"] == 2
    assert store.sequence == 2

    snap3 = store.replace_sections({"storage": {"status": "ok"}})
    assert snap3["sequence"] == 3
    assert store.sequence == 3


def test_timestamp_updates() -> None:
    """Updates should refresh the generated_at ISO timestamp."""
    store = SnapshotStore()
    t0 = store.get_snapshot()["generated_at"]
    # Ensure timestamp format parses validly
    dt = datetime.strptime(t0, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert dt.year >= 2026

    snap1 = store.update_sections({"cpu": {"status": "ok"}})
    t1 = snap1["generated_at"]
    assert isinstance(t1, str)
    assert t1.endswith("Z")


def test_overall_status_derivation() -> None:
    """Overall status should reflect individual section statuses accurately."""
    store = SnapshotStore()

    # All OK
    store.update_sections({
        "cpu": {"status": STATUS_OK},
        "memory": {"status": STATUS_OK},
    })
    assert store.get_snapshot()["overall_status"] == STATUS_OK

    # Partial (one OK, one error)
    store.update_sections({
        "gpu": {"status": STATUS_ERROR},
    })
    assert store.get_snapshot()["overall_status"] == STATUS_PARTIAL

    # All Error
    store.replace_sections({
        "cpu": {"status": STATUS_ERROR},
        "gpu": {"status": STATUS_ERROR},
    })
    assert store.get_snapshot()["overall_status"] == STATUS_ERROR

    # Explicit override
    store.update_sections({"cpu": {"status": STATUS_OK}}, overall_status="custom_status")
    assert store.get_snapshot()["overall_status"] == "custom_status"


def test_deep_copy_isolation() -> None:
    """Callers should not be able to mutate internal store state."""
    store = SnapshotStore()
    data = {"cpu": {"status": "ok", "cores": [10, 20]}}
    store.update_sections(data)

    # Mutate the input dictionary after passing to update
    data["cpu"]["cores"].append(99)
    assert store.get_snapshot()["sections"]["cpu"]["cores"] == [10, 20]

    # Mutate the returned snapshot dictionary
    retrieved = store.get_snapshot()
    retrieved["sections"]["cpu"]["cores"].append(100)
    retrieved["overall_status"] = "hacked"

    internal = store.get_snapshot()
    assert internal["sections"]["cpu"]["cores"] == [10, 20]
    assert internal["overall_status"] == STATUS_OK


def test_replace_sections() -> None:
    """replace_sections should discard old sections completely."""
    store = SnapshotStore()
    store.update_sections({"sec1": {"status": "ok"}, "sec2": {"status": "ok"}})
    assert set(store.get_snapshot()["sections"].keys()) == {"sec1", "sec2"}

    store.replace_sections({"sec3": {"status": "ok"}})
    assert set(store.get_snapshot()["sections"].keys()) == {"sec3"}


def test_reset() -> None:
    """reset should clear all sections and restore sequence to 0."""
    store = SnapshotStore()
    store.update_sections({"cpu": {"status": "ok"}})
    assert store.sequence == 1

    store.reset()
    snap = store.get_snapshot()
    assert snap["sequence"] == 0
    assert snap["sections"] == {}
    assert snap["overall_status"] == STATUS_INITIALIZING


def test_concurrent_access() -> None:
    """Multiple threads reading and writing concurrently must remain thread-safe."""
    store = SnapshotStore()
    num_updates = 100

    def writer(idx: int) -> None:
        for i in range(num_updates):
            store.update_sections({f"worker_{idx}": {"count": i, "status": "ok"}})

    def reader() -> None:
        for _ in range(num_updates * 2):
            snap = store.get_snapshot()
            assert snap["sequence"] >= 0
            assert isinstance(snap["sections"], dict)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(writer, 1),
            executor.submit(writer, 2),
            executor.submit(writer, 3),
            executor.submit(reader),
            executor.submit(reader),
        ]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    assert store.sequence == num_updates * 3
