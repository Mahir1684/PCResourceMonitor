"""Unit tests for the LibreHardwareMonitor sensor bridge client."""

import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.error
import pytest

from backend.monitoring.providers.lhm_bridge import LhmBridgeClient


def test_lhm_unconfigured() -> None:
    """When no feed URL or path is configured, returns unavailable gracefully."""
    with patch.dict("os.environ", {}, clear=True):
        client = LhmBridgeClient()
        assert not client.is_configured
        sensors = client.get_cpu_sensors()
        assert sensors["status"] == "unavailable"
        assert sensors["package_temperature_c"] is None
        assert sensors["core_temperatures_c"] == []
        assert sensors["package_power_watts"] is None
        assert "not configured" in sensors["reason"].lower()


def test_lhm_feed_file_not_found(tmp_path: Path) -> None:
    """When feed file path does not exist, returns unavailable with clear reason."""
    missing_file = tmp_path / "nonexistent_sensors.json"
    client = LhmBridgeClient(feed_path=missing_file)
    assert client.is_configured
    sensors = client.get_cpu_sensors()
    assert sensors["status"] == "unavailable"
    assert "not found" in sensors["reason"].lower()


def test_lhm_feed_file_normalized_success(tmp_path: Path) -> None:
    """Reads and validates standard normalized JSON sensor feed file."""
    feed_file = tmp_path / "sensors.json"
    feed_data = {
        "cpu": {
            "package_temperature_c": 54.2,
            "core_temperatures_c": [51.0, 52.5, 50.8, 54.0, 49.5, 53.1],
            "package_power_watts": 68.5,
        }
    }
    feed_file.write_text(json.dumps(feed_data), encoding="utf-8")

    client = LhmBridgeClient(feed_path=feed_file)
    sensors = client.get_cpu_sensors()

    assert sensors["status"] == "ok"
    assert sensors["package_temperature_c"] == 54.2
    assert len(sensors["core_temperatures_c"]) == 6
    assert sensors["core_temperatures_c"][0] == 51.0
    assert sensors["package_power_watts"] == 68.5


def test_lhm_feed_file_raw_tree_success(tmp_path: Path) -> None:
    """Parses hierarchical LHM web server tree structure."""
    feed_file = tmp_path / "lhm_tree.json"
    lhm_tree = {
        "Text": "SensorTree",
        "Children": [
            {
                "Text": "AMD Ryzen 5 9600X",
                "Children": [
                    {
                        "Text": "Temperatures",
                        "Children": [
                            {"Text": "CPU Package", "Value": "55.6 °C"},
                            {"Text": "Core #1", "Value": "51.2 °C"},
                            {"Text": "Core #2", "Value": "53.0 °C"},
                        ],
                    },
                    {
                        "Text": "Powers",
                        "Children": [
                            {"Text": "CPU Package", "Value": "72.4 W"},
                        ],
                    },
                ],
            }
        ],
    }
    feed_file.write_text(json.dumps(lhm_tree), encoding="utf-8")

    client = LhmBridgeClient(feed_path=feed_file)
    sensors = client.get_cpu_sensors()

    assert sensors["status"] == "ok"
    assert sensors["package_temperature_c"] == 55.6
    assert sensors["core_temperatures_c"] == [51.2, 53.0]
    assert sensors["package_power_watts"] == 72.4


def test_lhm_malformed_json(tmp_path: Path) -> None:
    """When feed file contains corrupted JSON, reports unavailable without crashing."""
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("{ incomplete json ...", encoding="utf-8")

    client = LhmBridgeClient(feed_path=corrupt_file)
    sensors = client.get_cpu_sensors()
    assert sensors["status"] == "unavailable"
    assert "malformed" in sensors["reason"].lower()


def test_lhm_out_of_range_validation(tmp_path: Path) -> None:
    """Invalid or physically implausible readings must be discarded, not fabricated."""
    feed_file = tmp_path / "range_test.json"
    feed_data = {
        "cpu": {
            "package_temperature_c": 999.0,  # Impossible temperature
            "core_temperatures_c": [-50.0, 52.0, 300.0],  # Out of range
            "package_power_watts": 50000.0,  # Impossible power
        }
    }
    feed_file.write_text(json.dumps(feed_data), encoding="utf-8")

    client = LhmBridgeClient(feed_path=feed_file)
    sensors = client.get_cpu_sensors()

    assert sensors["package_temperature_c"] is None
    assert sensors["package_power_watts"] is None
    # Only the 52.0 core temperature within physical limits is retained
    assert sensors["core_temperatures_c"] == [52.0]


def test_lhm_http_success() -> None:
    """Mocked HTTP endpoint returns valid telemetry."""
    payload = json.dumps({
        "cpu": {
            "package_temperature_c": 47.8,
            "core_temperatures_c": [45.0, 46.2],
            "package_power_watts": 55.0,
        }
    }).encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.read.return_value = payload
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = LhmBridgeClient(feed_url="http://127.0.0.1:5002/sensors")
        sensors = client.get_cpu_sensors()

        assert sensors["status"] == "ok"
        assert sensors["package_temperature_c"] == 47.8
        assert sensors["core_temperatures_c"] == [45.0, 46.2]
        assert sensors["package_power_watts"] == 55.0


def test_lhm_http_network_errors() -> None:
    """Network connection errors or timeouts are safely handled."""
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        client = LhmBridgeClient(feed_url="http://127.0.0.1:5002/sensors")
        sensors = client.get_cpu_sensors()

        assert sensors["status"] == "unavailable"
        assert sensors["package_temperature_c"] is None
        assert "unreachable" in sensors["reason"].lower()


def test_lhm_http_cooldown_and_cache_invalidation() -> None:
    """Failed HTTP request enters cooldown, caching unavailable result and preventing repeated stalls."""
    mock_urlopen = MagicMock(side_effect=urllib.error.URLError("Timeout"))

    client = LhmBridgeClient(feed_url="http://127.0.0.1:5002/sensors", cooldown_seconds=2.5)

    with (
        patch("urllib.request.urlopen", mock_urlopen),
        patch("time.monotonic", side_effect=[100.0, 101.0, 102.0, 103.0, 103.5]),
    ):
        # 1. First call fails and enters cooldown
        res1 = client.get_cpu_sensors()
        assert res1["status"] == "unavailable"
        assert mock_urlopen.call_count == 1

        # 2. Second call 1 second later (within 2.5s cooldown) returns cached result without urlopen
        res2 = client.get_cpu_sensors()
        assert res2["status"] == "unavailable"
        assert mock_urlopen.call_count == 1  # Not called again!

        # 3. Third call 2 seconds later (still within cooldown: 102 - 100 = 2.0 < 2.5)
        res3 = client.get_cpu_sensors()
        assert res3["status"] == "unavailable"
        assert mock_urlopen.call_count == 1

        # 4. Fourth call at 103.0s (3.0s > 2.5s cooldown expired) -> retries urlopen
        # Now mock urlopen succeeding
        success_payload = json.dumps({"cpu": {"package_temperature_c": 50.0}}).encode("utf-8")
        mock_success_resp = MagicMock()
        mock_success_resp.read.return_value = success_payload
        mock_success_resp.__enter__.return_value = mock_success_resp
        mock_urlopen.side_effect = None
        mock_urlopen.return_value = mock_success_resp

        res4 = client.get_cpu_sensors()
        assert res4["status"] == "ok"
        assert res4["package_temperature_c"] == 50.0
        assert mock_urlopen.call_count == 2


def test_lhm_rejects_incompatible_units_normalized_and_tree(tmp_path: Path) -> None:
    """Values containing RPM, %, MHz, or V must be rejected, preserving only valid °C and W."""
    # 1. Normalized feed containing strings with incompatible units
    feed_file = tmp_path / "incompatible_units.json"
    feed_file.write_text(
        json.dumps({
            "cpu": {
                "package_temperature_c": "1500 RPM",
                "core_temperatures_c": ["50 %", "4200 MHz", "1.25 V", 52.5],
                "package_power_watts": "85 %",
            }
        }),
        encoding="utf-8",
    )
    client = LhmBridgeClient(feed_path=feed_file)
    sensors = client.get_cpu_sensors()

    assert sensors["package_temperature_c"] is None
    assert sensors["package_power_watts"] is None
    assert sensors["core_temperatures_c"] == [52.5]  # Only the valid 52.5 is kept

    # 2. Raw LHM tree containing false-positive sensor names with incompatible units
    tree_file = tmp_path / "tree_incompatible.json"
    tree_file.write_text(
        json.dumps({
            "Text": "SensorTree",
            "Children": [
                {
                    "Text": "AMD Ryzen 5 9600X",
                    "Children": [
                        {
                            "Text": "Temperatures Context",
                            "Children": [
                                {"Text": "CPU Fan Temp Control", "Value": "1800 RPM"},
                                {"Text": "Core Temp Limit", "Value": "80 %"},
                                {"Text": "Core Temp Frequency", "Value": "4200 MHz"},
                                {"Text": "CPU Temp Diode Voltage", "Value": "1.3 V"},
                                {"Text": "CPU Package", "Value": "56.4 °C"},
                            ],
                        },
                        {
                            "Text": "Powers Context",
                            "Children": [
                                {"Text": "Power Limit", "Value": "100 %"},
                                {"Text": "CPU Package", "Value": "68.2 W"},
                            ],
                        },
                    ],
                }
            ],
        }),
        encoding="utf-8",
    )
    client_tree = LhmBridgeClient(feed_path=tree_file)
    sensors_tree = client_tree.get_cpu_sensors()

    assert sensors_tree["status"] == "ok"
    assert sensors_tree["package_temperature_c"] == 56.4
    assert sensors_tree["package_power_watts"] == 68.2
