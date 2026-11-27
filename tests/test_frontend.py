"""Integration tests for Flask frontend delivery and static asset routing.

Verifies:
- GET / and GET /index.html serve the primary HTML5 dashboard shell.
- GET /css/dashboard.css and GET /js/dashboard.js serve static assets with correct MIME types.
- Missing routes and nonexistent assets return structured JSON 404 responses.
- Path traversal attempts are rejected.
- Client-IP access control allowlist applies to dashboard and static routes.
- API endpoints /api/v1/status and /api/v1/health remain intact.
"""

from pathlib import Path
import pytest
from flask.testing import FlaskClient

from backend.app import create_app
from backend.config import load_config
from backend.monitoring.snapshot import STATUS_OK


@pytest.fixture
def client() -> FlaskClient:
    """Fixture providing a test client configured with loopback access only."""
    config = load_config(host="127.0.0.1", port=5001, allowed_clients=["127.0.0.1/32"])
    mock_collectors = {
        "cpu": lambda: {"status": STATUS_OK, "usage_percent": 10.0},
        "memory": lambda: {"status": STATUS_OK, "usage_percent": 30.0},
        "storage": lambda: {"status": STATUS_OK, "volumes": []},
        "network": lambda: {"status": STATUS_OK, "interfaces": []},
        "system": lambda: {"status": STATUS_OK, "hostname": "TEST-HOST"},
        "gpus": lambda: {"status": STATUS_OK, "devices": []},
    }
    app = create_app(config=config, start_sampler=False, collectors=mock_collectors)
    # Prime store once for status endpoint
    app.extensions["pc_monitor"]["sampler"].sample_once()

    with app.test_client() as test_client:
        yield test_client


def test_serve_dashboard_root(client: FlaskClient) -> None:
    """GET / should serve frontend/index.html with 200 OK and text/html."""
    resp = client.get("/", environ_base={"REMOTE_ADDR": "127.0.0.1"})

    assert resp.status_code == 200
    assert "text/html" in resp.headers["Content-Type"]
    html_text = resp.get_data(as_text=True)
    assert "<title>PC Resource Monitor" in html_text
    assert 'id="card-cpu"' in html_text
    assert 'id="hud-status-badge"' in html_text
    assert 'href="css/dashboard.css"' in html_text
    assert 'src="js/dashboard.js"' in html_text


def test_serve_dashboard_index_alias(client: FlaskClient) -> None:
    """GET /index.html should serve the dashboard shell identically."""
    resp = client.get("/index.html", environ_base={"REMOTE_ADDR": "127.0.0.1"})

    assert resp.status_code == 200
    assert "text/html" in resp.headers["Content-Type"]
    html_text = resp.get_data(as_text=True)
    assert 'id="card-cpu"' in html_text


def test_serve_css_asset(client: FlaskClient) -> None:
    """GET /css/dashboard.css should serve the stylesheet with text/css."""
    resp = client.get("/css/dashboard.css", environ_base={"REMOTE_ADDR": "127.0.0.1"})

    assert resp.status_code == 200
    assert "text/css" in resp.headers["Content-Type"]
    css_text = resp.get_data(as_text=True)
    assert ".hud-header" in css_text
    assert ".dash-card" in css_text


def test_serve_js_asset(client: FlaskClient) -> None:
    """GET /js/dashboard.js should serve the client script with javascript MIME type."""
    resp = client.get("/js/dashboard.js", environ_base={"REMOTE_ADDR": "127.0.0.1"})

    assert resp.status_code == 200
    content_type = resp.headers["Content-Type"]
    assert "javascript" in content_type
    js_text = resp.get_data(as_text=True)
    assert "function pollStatus()" in js_text
    assert "classifyGpus" in js_text


def test_missing_asset_returns_json_404(client: FlaskClient) -> None:
    """Nonexistent CSS/JS files should return HTTP 404 with structured JSON."""
    resp = client.get("/css/nonexistent.css", environ_base={"REMOTE_ADDR": "127.0.0.1"})

    assert resp.status_code == 404
    assert resp.is_json
    data = resp.get_json()
    assert data["error"]["code"] == "NOT_FOUND"

    resp_js = client.get("/js/missing.js", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert resp_js.status_code == 404
    assert resp_js.is_json
    assert resp_js.get_json()["error"]["code"] == "NOT_FOUND"


def test_unknown_route_returns_json_404(client: FlaskClient) -> None:
    """Unknown URL paths should return HTTP 404 with structured JSON."""
    resp = client.get("/some/unknown/path", environ_base={"REMOTE_ADDR": "127.0.0.1"})

    assert resp.status_code == 404
    assert resp.is_json
    data = resp.get_json()
    assert data["error"]["code"] == "NOT_FOUND"


def test_directory_traversal_rejected(client: FlaskClient) -> None:
    """Directory traversal attempts via asset paths must return HTTP 404."""
    resp = client.get("/css/../index.html", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert resp.status_code == 404
    assert resp.is_json
    assert resp.get_json()["error"]["code"] == "NOT_FOUND"

    resp_traversal = client.get("/js/../../backend/app.py", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert resp_traversal.status_code == 404
    assert resp_traversal.is_json


def test_access_control_applied_to_frontend(client: FlaskClient) -> None:
    """Unauthorized remote IP addresses must receive HTTP 403 on dashboard and static assets."""
    # Unauthorized IP accessing GET /
    resp_root = client.get("/", environ_base={"REMOTE_ADDR": "192.168.1.99"})
    assert resp_root.status_code == 403
    assert resp_root.is_json
    assert resp_root.get_json()["error"]["code"] == "ACCESS_DENIED"

    # Unauthorized IP accessing GET /css/dashboard.css
    resp_css = client.get("/css/dashboard.css", environ_base={"REMOTE_ADDR": "192.168.1.99"})
    assert resp_css.status_code == 403
    assert resp_css.is_json
    assert resp_css.get_json()["error"]["code"] == "ACCESS_DENIED"

    # Unauthorized IP accessing GET /js/dashboard.js
    resp_js = client.get("/js/dashboard.js", environ_base={"REMOTE_ADDR": "192.168.1.99"})
    assert resp_js.status_code == 403
    assert resp_js.is_json
    assert resp_js.get_json()["error"]["code"] == "ACCESS_DENIED"


def test_api_routes_intact_with_frontend(client: FlaskClient) -> None:
    """API endpoints /api/v1/status and /api/v1/health remain fully functional alongside dashboard."""
    resp_status = client.get("/api/v1/status", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert resp_status.status_code == 200
    assert resp_status.is_json
    assert resp_status.get_json()["schema_version"] == 1
    assert "cpu" in resp_status.get_json()["sections"]

    resp_health = client.get("/api/v1/health", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert resp_health.status_code == 200
    assert resp_health.is_json
    assert resp_health.get_json()["status"] in ("healthy", "degraded")


def test_custom_frontend_directory_injection(tmp_path: Path) -> None:
    """create_app accepts a custom frontend_dir for isolated testing."""
    custom_dir = tmp_path / "custom_frontend"
    custom_dir.mkdir()
    (custom_dir / "index.html").write_text("<h1>Custom Test Dashboard</h1>", encoding="utf-8")
    css_dir = custom_dir / "css"
    css_dir.mkdir()
    (css_dir / "custom.css").write_text("body { background: red; }", encoding="utf-8")

    config = load_config(host="127.0.0.1", port=5001)
    app = create_app(config=config, start_sampler=False, frontend_dir=custom_dir)

    with app.test_client() as custom_client:
        r_root = custom_client.get("/", environ_base={"REMOTE_ADDR": "127.0.0.1"})
        assert r_root.status_code == 200
        assert "Custom Test Dashboard" in r_root.get_data(as_text=True)

        r_css = custom_client.get("/css/custom.css", environ_base={"REMOTE_ADDR": "127.0.0.1"})
        assert r_css.status_code == 200
        assert "background: red" in r_css.get_data(as_text=True)
