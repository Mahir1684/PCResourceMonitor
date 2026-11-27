"""LibreHardwareMonitor local sensor bridge client.

Provides a lightweight, read-only client to ingest CPU hardware telemetry
(package temperature, individual core temperatures, and package power) from a
local LHM bridge service or local JSON sensor feed.

Designed for non-blocking execution with short timeouts, strict numeric
validation, and safe handling of missing, corrupt, or unconfigured bridge sources.
Never invents or interpolates sensor values.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request


logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 0.5
DEFAULT_COOLDOWN_SECONDS = 2.5

# Validation thresholds for x86 CPU physical operating limits
MIN_VALID_TEMP_C = 0.0
MAX_VALID_TEMP_C = 135.0
MIN_VALID_POWER_W = 0.0
MAX_VALID_POWER_W = 1000.0

# Units that disqualify a value from being considered a temperature or power reading
INCOMPATIBLE_TEMP_UNITS = ("rpm", "%", "mhz", "khz", "ghz", "v", "mv", "w", "a", "fps", "mb", "gb")
INCOMPATIBLE_POWER_UNITS = ("rpm", "%", "°c", "mhz", "khz", "ghz", "v", "mv", "fps", "mb", "gb")


def _has_incompatible_units(val: Any, incompatible: tuple[str, ...]) -> bool:
    """Check if a string value contains an incompatible unit token."""
    if isinstance(val, str):
        val_lower = val.lower()
        return any(u in val_lower for u in incompatible)
    return False


def _parse_numeric(val: Any) -> float | None:
    """Safely extract a float from a numeric value or formatted string (e.g. '52.3 °C')."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        # Extract first decimal number from string
        match = re.search(r"[-+]?\d*\.?\d+", val.strip())
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                return None
    return None


class LhmBridgeClient:
    """Client for querying local LibreHardwareMonitor telemetry."""

    def __init__(
        self,
        feed_url: str | None = None,
        feed_path: str | Path | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        # Check explicit parameters, then environment variables
        self._feed_url = feed_url or os.environ.get("LHM_FEED_URL")
        self._feed_path = Path(feed_path) if feed_path else (
            Path(os.environ["LHM_FEED_PATH"]) if "LHM_FEED_PATH" in os.environ else None
        )
        self._timeout = float(timeout_seconds)
        self._cooldown = float(cooldown_seconds)

        # Thread-safe failure cooldown tracking
        self._lock = threading.Lock()
        self._last_failure_time: float = 0.0
        self._cached_failure_result: dict[str, Any] | None = None

    @property
    def is_configured(self) -> bool:
        """True if either a feed URL or feed path is specified."""
        return bool(self._feed_url or self._feed_path)

    @property
    def cooldown_seconds(self) -> float:
        """Configured cooldown duration in seconds."""
        return self._cooldown

    def get_cpu_sensors(self) -> dict[str, Any]:
        """Fetch and normalize CPU hardware sensors from the configured bridge.

        Returns a dictionary with validated numeric fields:
            - package_temperature_c: float | None
            - core_temperatures_c: list[float]
            - package_power_watts: float | None
            - status: 'ok' | 'unavailable'
            - reason: str | None
        """
        if not self.is_configured:
            return {
                "package_temperature_c": None,
                "core_temperatures_c": [],
                "package_power_watts": None,
                "status": "unavailable",
                "reason": "LibreHardwareMonitor bridge not configured.",
            }

        # Check HTTP cooldown if feed_url is used to prevent sampling stalls
        if self._feed_url is not None:
            with self._lock:
                now = time.monotonic()
                if (now - self._last_failure_time) < self._cooldown and self._cached_failure_result is not None:
                    return copy.deepcopy(self._cached_failure_result)

        raw_data: Any = None
        try:
            if self._feed_path is not None:
                if not self._feed_path.exists():
                    return {
                        "package_temperature_c": None,
                        "core_temperatures_c": [],
                        "package_power_watts": None,
                        "status": "unavailable",
                        "reason": f"LHM feed file not found at {self._feed_path}.",
                    }
                content = self._feed_path.read_text(encoding="utf-8")
                raw_data = json.loads(content)

            elif self._feed_url is not None:
                req = urllib.request.Request(
                    self._feed_url,
                    headers={"Accept": "application/json", "User-Agent": "PCResourceMonitor/1.0"},
                )
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    payload_bytes = resp.read()
                    raw_data = json.loads(payload_bytes.decode("utf-8", errors="ignore"))

                # Reset failure state on successful network response
                with self._lock:
                    self._last_failure_time = 0.0
                    self._cached_failure_result = None

        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.debug("LHM bridge connection error: %s", exc)
            fail_result = {
                "package_temperature_c": None,
                "core_temperatures_c": [],
                "package_power_watts": None,
                "status": "unavailable",
                "reason": f"LHM bridge unreachable: {exc.__class__.__name__}",
            }
            if self._feed_url is not None:
                with self._lock:
                    self._last_failure_time = time.monotonic()
                    self._cached_failure_result = copy.deepcopy(fail_result)
            return fail_result

        except json.JSONDecodeError as exc:
            logger.debug("LHM bridge returned invalid JSON: %s", exc)
            fail_result = {
                "package_temperature_c": None,
                "core_temperatures_c": [],
                "package_power_watts": None,
                "status": "unavailable",
                "reason": "LHM bridge returned malformed JSON payload.",
            }
            if self._feed_url is not None:
                with self._lock:
                    self._last_failure_time = time.monotonic()
                    self._cached_failure_result = copy.deepcopy(fail_result)
            return fail_result

        except Exception as exc:
            logger.debug("Unexpected error querying LHM bridge: %s", exc)
            return {
                "package_temperature_c": None,
                "core_temperatures_c": [],
                "package_power_watts": None,
                "status": "unavailable",
                "reason": f"LHM bridge query failed: {exc}",
            }

        if not isinstance(raw_data, dict):
            return {
                "package_temperature_c": None,
                "core_temperatures_c": [],
                "package_power_watts": None,
                "status": "unavailable",
                "reason": "LHM bridge payload is not a JSON object.",
            }

        return self._extract_cpu_metrics(raw_data)

    def _extract_cpu_metrics(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse and validate metrics from either normalized schema or raw LHM tree."""
        # 1. Normalized JSON schema
        if "cpu" in data and isinstance(data["cpu"], dict):
            cpu_obj = data["cpu"]
            raw_pkg_temp = cpu_obj.get("package_temperature_c")
            raw_pkg_power = cpu_obj.get("package_power_watts")
            raw_cores = cpu_obj.get("core_temperatures_c", [])

            # Reject incompatible units in normalized strings
            if _has_incompatible_units(raw_pkg_temp, INCOMPATIBLE_TEMP_UNITS):
                raw_pkg_temp = None
            if _has_incompatible_units(raw_pkg_power, INCOMPATIBLE_POWER_UNITS):
                raw_pkg_power = None

            parsed_temp = _parse_numeric(raw_pkg_temp)
            pkg_temp = (
                round(parsed_temp, 1)
                if parsed_temp is not None and MIN_VALID_TEMP_C <= parsed_temp <= MAX_VALID_TEMP_C
                else None
            )

            parsed_power = _parse_numeric(raw_pkg_power)
            pkg_power = (
                round(parsed_power, 1)
                if parsed_power is not None and MIN_VALID_POWER_W <= parsed_power <= MAX_VALID_POWER_W
                else None
            )

            valid_cores: list[float] = []
            if isinstance(raw_cores, list):
                for c in raw_cores:
                    if not _has_incompatible_units(c, INCOMPATIBLE_TEMP_UNITS):
                        parsed_c = _parse_numeric(c)
                        if parsed_c is not None and MIN_VALID_TEMP_C <= parsed_c <= MAX_VALID_TEMP_C:
                            valid_cores.append(round(parsed_c, 1))

            has_metrics = pkg_temp is not None or pkg_power is not None or bool(valid_cores)
            return {
                "package_temperature_c": pkg_temp,
                "core_temperatures_c": valid_cores,
                "package_power_watts": pkg_power,
                "status": "ok" if has_metrics else "unavailable",
                "reason": None if has_metrics else "CPU hardware sensors not reported in bridge payload.",
            }

        # 2. Raw LHM web server tree (hierarchical "Children" structure)
        pkg_temp = None
        pkg_power = None
        core_temps: list[float] = []

        def _traverse(node: dict[str, Any], parent_text: str = "") -> None:
            nonlocal pkg_temp, pkg_power
            text = str(node.get("Text", "")).strip().lower()
            val_str = str(node.get("Value", "")).strip().lower()
            combined_context = f"{parent_text} {text}".lower()

            # 1. Temperature sensors (must not contain RPM, %, MHz, V, etc.)
            if not _has_incompatible_units(val_str, INCOMPATIBLE_TEMP_UNITS):
                if "°c" in val_str or (("temp" in combined_context or "tctl" in text) and "°" in val_str):
                    if "package" in text or "tctl/tdie" in text or "core (tctl" in text:
                        parsed = _parse_numeric(val_str)
                        if parsed is not None and MIN_VALID_TEMP_C <= parsed <= MAX_VALID_TEMP_C:
                            pkg_temp = round(parsed, 1)
                    elif "core #" in text:
                        parsed = _parse_numeric(val_str)
                        if parsed is not None and MIN_VALID_TEMP_C <= parsed <= MAX_VALID_TEMP_C:
                            core_temps.append(round(parsed, 1))

            # 2. Power sensors (must not contain RPM, %, °C, MHz, V, etc.)
            if not _has_incompatible_units(val_str, INCOMPATIBLE_POWER_UNITS):
                if "w" in val_str or "power" in combined_context:
                    if "package" in text or "cpu package" in text:
                        parsed = _parse_numeric(val_str)
                        if parsed is not None and MIN_VALID_POWER_W <= parsed <= MAX_VALID_POWER_W:
                            pkg_power = round(parsed, 1)

            for child in node.get("Children", []):
                if isinstance(child, dict):
                    _traverse(child, text)

        _traverse(data)

        has_metrics = pkg_temp is not None or pkg_power is not None or bool(core_temps)
        return {
            "package_temperature_c": pkg_temp,
            "core_temperatures_c": core_temps,
            "package_power_watts": pkg_power,
            "status": "ok" if has_metrics else "unavailable",
            "reason": None if has_metrics else "No matching CPU sensors identified in LHM tree.",
        }
