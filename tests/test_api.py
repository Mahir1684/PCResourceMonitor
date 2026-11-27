"""Unit and integration tests for PCResourceMonitor REST API endpoints."""

from unittest.mock import MagicMock, patch
import pytest
from flask.testing import FlaskClient

from backend.app import create_app
from backend.config import load_config
from backend.monitoring.snapshot import (
    SnapshotStore,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_PARTIAL,
)


@pytest.fixture
def test_client() -> FlaskClient:
    """Fixture providing a test client with an unstarted background thread."""
    config = load_config(host="127.0.0.1", port=5001)

    mock_collectors = {
        "cpu": lambda: {"status": STATUS_OK, "usage_percent": 15.0},
        "memory": lambda: {"status": STATUS_OK, "usage_percent": 45.0},
        "storage": lambda: {"status": STATUS_OK, "volumes": []},
        "network": lambda: {"status": STATUS_OK, "interfaces": []},
        "system": lambda: {"status": STATUS_OK, "hostname": "TEST-PC"},
        "gpus": lambda: {"status": STATUS_OK, "devices": []},
        "fps": lambda: {"status": STATUS_OK, "fps": 144.0, "active_process": "Doom.exe"},
    }

    app = create_app(config=config, start_sampler=False, collectors=mock_collectors)
    # Prime one initial sample for predictable responses
    context = app.extensions["pc_monitor"]
    context["sampler"].sample_once()

    with app.test_client() as client:
        yield client


def test_get_status_success(test_client: FlaskClient) -> None:
    """GET /api/v1/status should return HTTP 200 with full schema."""
    resp = test_client.get("/api/v1/status", environ_base={"REMOTE_ADDR": "127.0.0.1"})

    assert resp.status_code == 200
    assert resp.is_json
    data = resp.get_json()

    assert data["schema_version"] == 1
    assert data["sequence"] >= 1
    assert data["overall_status"] == STATUS_OK
    assert "cpu" in data["sections"]
    assert data["sections"]["cpu"]["usage_percent"] == 15.0
    assert "memory" in data["sections"]
    assert "gpus" in data["sections"]
    assert "fps" in data["sections"]
    assert data["sections"]["fps"]["fps"] == 144.0
    assert "Cache-Control" in resp.headers
    assert "no-store" in resp.headers["Cache-Control"]


def test_get_health_success(test_client: FlaskClient) -> None:
    """GET /api/v1/health should report sampler and system health."""
    resp = test_client.get("/api/v1/health", environ_base={"REMOTE_ADDR": "127.0.0.1"})

    assert resp.status_code == 200
    assert resp.is_json
    data = resp.get_json()

    assert "status" in data
    assert "sampler" in data
    assert "is_running" in data["sampler"]
    assert "interval_seconds" in data["sampler"]
    assert "last_sequence" in data["sampler"]


def test_status_endpoint_never_calls_collectors(test_client: FlaskClient) -> None:
    """HTTP requests must strictly read the cached snapshot and never trigger collectors."""
    collector_calls = 0

    def tracked_collector() -> dict:
        nonlocal collector_calls
        collector_calls += 1
        return {"status": STATUS_OK}

    app = create_app(
        start_sampler=False,
        collectors={"test_sec": tracked_collector},
    )
    # Prime store once
    app.extensions["pc_monitor"]["sampler"].sample_once()
    assert collector_calls == 1

    with app.test_client() as client:
        for _ in range(10):
            r = client.get("/api/v1/status", environ_base={"REMOTE_ADDR": "127.0.0.1"})
            assert r.status_code == 200

    # Verification: collector_calls remains 1 despite 10 HTTP requests
    assert collector_calls == 1


def test_partial_status_response() -> None:
    """When some sections fail, status should return 200 with partial overall_status."""
    failing_collectors = {
        "good": lambda: {"status": STATUS_OK},
        "bad": lambda: {"status": STATUS_ERROR, "error": {"code": "ERR"}},
    }
    app = create_app(start_sampler=False, collectors=failing_collectors)
    app.extensions["pc_monitor"]["sampler"].sample_once()

    with app.test_client() as client:
        resp = client.get("/api/v1/status", environ_base={"REMOTE_ADDR": "127.0.0.1"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["overall_status"] == STATUS_PARTIAL


def test_error_status_returns_503() -> None:
    """When all sections fail, status should return HTTP 503."""
    all_failing = {
        "bad1": lambda: {"status": STATUS_ERROR},
        "bad2": lambda: {"status": STATUS_ERROR},
    }
    app = create_app(start_sampler=False, collectors=all_failing)
    app.extensions["pc_monitor"]["sampler"].sample_once()

    with app.test_client() as client:
        resp = client.get("/api/v1/status", environ_base={"REMOTE_ADDR": "127.0.0.1"})
        assert resp.status_code == 503
        data = resp.get_json()
        assert data["overall_status"] == STATUS_ERROR


def test_not_found_returns_structured_json(test_client: FlaskClient) -> None:
    """Unknown API endpoints return structured 404 JSON, not HTML."""
    resp = test_client.get("/api/v1/nonexistent", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert resp.status_code == 404
    assert resp.is_json
    data = resp.get_json()
    assert data["error"]["code"] == "NOT_FOUND"


def test_app_sampler_lifecycle() -> None:
    """Test start_sampler controls whether thread runs and stop_sampler stops it."""
    # App created without background thread
    app_idle = create_app(start_sampler=False, collectors={})
    assert not app_idle.extensions["pc_monitor"]["sampler"].is_running

    # App created with background thread
    app_running = create_app(start_sampler=True, collectors={})
    assert app_running.extensions["pc_monitor"]["sampler"].is_running

    # Clean shutdown
    app_running.stop_sampler()
    assert not app_running.extensions["pc_monitor"]["sampler"].is_running


def test_get_status_with_default_collectors_includes_gpus() -> None:
    """When app is created with default collectors, sections.gpus is present and structured."""
    mock_nvml = MagicMock()
    mock_nvml.get_devices.return_value = []
    mock_dxgi = MagicMock()
    mock_dxgi.get_adapters.return_value = []

    with (
        patch("backend.monitoring.gpus.NvmlGpuProvider", return_value=mock_nvml),
        patch("backend.monitoring.gpus.DxgiGpuProvider", return_value=mock_dxgi),
    ):
        app = create_app(start_sampler=False)
        app.extensions["pc_monitor"]["sampler"].sample_once()

        with app.test_client() as client:
            resp = client.get("/api/v1/status", environ_base={"REMOTE_ADDR": "127.0.0.1"})
            assert resp.status_code == 200
            data = resp.get_json()

            assert "gpus" in data["sections"]
            assert data["sections"]["gpus"]["status"] == "ok"
            assert "devices" in data["sections"]["gpus"]
            assert "cpu" in data["sections"]
            assert "temperature_c" in data["sections"]["cpu"]
            assert "power_watts" in data["sections"]["cpu"]
            assert "core_temperatures_c" in data["sections"]["cpu"]

        app.stop_sampler()
