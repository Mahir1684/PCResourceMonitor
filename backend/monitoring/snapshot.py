"""Thread-safe in-memory snapshot store for system metrics.

Holds the latest normalized telemetry snapshot and sequence number,
ensuring HTTP requests read instantaneous cached state without querying
hardware synchronously.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import threading
from typing import Any, Mapping


SCHEMA_VERSION = 1

STATUS_INITIALIZING = "initializing"
STATUS_OK = "ok"
STATUS_PARTIAL = "partial"
STATUS_ERROR = "error"


def _format_utc_timestamp(dt: datetime | None = None) -> str:
    """Format a datetime in ISO 8601 UTC format ending in Z."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _calculate_overall_status(sections: Mapping[str, Any]) -> str:
    """Derive overall status from individual section statuses."""
    if not sections:
        return STATUS_INITIALIZING

    statuses = []
    for sec_data in sections.values():
        if isinstance(sec_data, dict):
            statuses.append(sec_data.get("status", STATUS_OK))
        else:
            statuses.append(STATUS_OK)

    if all(s == STATUS_OK for s in statuses):
        return STATUS_OK
    if all(s == STATUS_ERROR for s in statuses):
        return STATUS_ERROR
    return STATUS_PARTIAL


class SnapshotStore:
    """Thread-safe store for telemetry snapshots."""

    def __init__(self, initial_sections: Mapping[str, Any] | None = None) -> None:
        self._lock = threading.Lock()
        self._sequence: int = 0
        self._sections: dict[str, Any] = {}
        
        if initial_sections:
            self._sections = copy.deepcopy(dict(initial_sections))
            self._sequence = 1
            self._overall_status = _calculate_overall_status(self._sections)
        else:
            self._overall_status = STATUS_INITIALIZING

        self._generated_at = _format_utc_timestamp()

    @property
    def sequence(self) -> int:
        """Current snapshot sequence number."""
        with self._lock:
            return self._sequence

    def get_snapshot(self) -> dict[str, Any]:
        """Return a thread-safe, deep-copied dictionary of the current snapshot."""
        with self._lock:
            return {
                "schema_version": SCHEMA_VERSION,
                "sequence": self._sequence,
                "generated_at": self._generated_at,
                "overall_status": self._overall_status,
                "sections": copy.deepcopy(self._sections),
            }

    def update_sections(
        self,
        new_sections: Mapping[str, Any],
        overall_status: str | None = None,
    ) -> dict[str, Any]:
        """Merge new section readings into the snapshot and increment sequence.
        
        Returns the updated snapshot.
        """
        with self._lock:
            self._sequence += 1
            self._generated_at = _format_utc_timestamp()

            # Merge sections (incoming section overwrites existing section entry)
            for name, data in new_sections.items():
                self._sections[name] = copy.deepcopy(data)

            if overall_status is not None:
                self._overall_status = overall_status
            else:
                self._overall_status = _calculate_overall_status(self._sections)

            return {
                "schema_version": SCHEMA_VERSION,
                "sequence": self._sequence,
                "generated_at": self._generated_at,
                "overall_status": self._overall_status,
                "sections": copy.deepcopy(self._sections),
            }

    def replace_sections(
        self,
        all_sections: Mapping[str, Any],
        overall_status: str | None = None,
    ) -> dict[str, Any]:
        """Replace all sections in the snapshot and increment sequence."""
        with self._lock:
            self._sequence += 1
            self._generated_at = _format_utc_timestamp()
            self._sections = copy.deepcopy(dict(all_sections))

            if overall_status is not None:
                self._overall_status = overall_status
            else:
                self._overall_status = _calculate_overall_status(self._sections)

            return {
                "schema_version": SCHEMA_VERSION,
                "sequence": self._sequence,
                "generated_at": self._generated_at,
                "overall_status": self._overall_status,
                "sections": copy.deepcopy(self._sections),
            }

    def reset(self) -> None:
        """Reset the store back to initial empty state."""
        with self._lock:
            self._sequence = 0
            self._sections.clear()
            self._overall_status = STATUS_INITIALIZING
            self._generated_at = _format_utc_timestamp()
