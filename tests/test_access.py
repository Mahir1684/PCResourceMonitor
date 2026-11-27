"""Unit tests for access control, security headers, and spoofing prevention."""

import pytest
from flask.testing import FlaskClient

from backend.app import create_app
from backend.config import load_config


def test_loopback_client_allowed_by_default() -> None:
    """Loopback client (127.0.0.1) is authorized under default configuration."""
    app = create_app(start_sampler=False, collectors={})
    with app.test_client() as client:
        resp = client.get("/api/v1/health", environ_base={"REMOTE_ADDR": "127.0.0.1"})
        assert resp.status_code == 200


def test_unauthorized_client_rejected_with_403() -> None:
    """An unauthorized external/LAN IP is rejected with HTTP 403 and error JSON."""
    app = create_app(start_sampler=False, collectors={})
    with app.test_client() as client:
        resp = client.get("/api/v1/health", environ_base={"REMOTE_ADDR": "192.168.1.50"})
        assert resp.status_code == 403
        assert resp.is_json
        data = resp.get_json()
        assert data["error"]["code"] == "ACCESS_DENIED"


def test_forwarded_headers_spoofing_prevented() -> None:
    """Spoofed X-Forwarded-For or X-Real-IP headers must be ignored."""
    app = create_app(start_sampler=False, collectors={})
    with app.test_client() as client:
        # An attacker connecting from unauthorized IP trying to spoof 127.0.0.1 via headers
        resp = client.get(
            "/api/v1/health",
            headers={"X-Forwarded-For": "127.0.0.1", "X-Real-IP": "127.0.0.1"},
            environ_base={"REMOTE_ADDR": "10.10.10.10"},
        )
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["error"]["code"] == "ACCESS_DENIED"


def test_configured_subnet_allowlist() -> None:
    """Test explicit private LAN subnet allowlisting."""
    cfg = load_config(
        host="192.168.1.10",
        allowed_clients=["127.0.0.1/32", "192.168.1.0/24"],
    )
    app = create_app(config=cfg, start_sampler=False, collectors={})

    with app.test_client() as client:
        # Client on the allowed 192.168.1.0/24 subnet
        resp_allowed = client.get(
            "/api/v1/health",
            environ_base={"REMOTE_ADDR": "192.168.1.105"},
        )
        assert resp_allowed.status_code == 200

        # Client on an unlisted 10.0.0.0 subnet
        resp_denied = client.get(
            "/api/v1/health",
            environ_base={"REMOTE_ADDR": "10.0.0.5"},
        )
        assert resp_denied.status_code == 403


def test_no_wildcard_cors_header() -> None:
    """API responses must never include Access-Control-Allow-Origin: *."""
    app = create_app(start_sampler=False, collectors={})
    with app.test_client() as client:
        resp = client.get(
            "/api/v1/health",
            headers={"Origin": "http://malicious-site.com"},
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("Access-Control-Allow-Origin") != "*"


def test_security_headers_present() -> None:
    """Security headers (nosniff, clickjacking, XSS, and no-cache) must be attached to API responses."""
    app = create_app(start_sampler=False, collectors={})
    with app.test_client() as client:
        resp = client.get("/api/v1/health", environ_base={"REMOTE_ADDR": "127.0.0.1"})
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
        assert "default-src 'self'" in resp.headers.get("Content-Security-Policy", "")
        assert "no-store" in resp.headers.get("Cache-Control", "")
