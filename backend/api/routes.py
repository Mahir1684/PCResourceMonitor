"""REST API route handlers for PCResourceMonitor.

Provides read-only JSON endpoints for live telemetry status and service health.
Endpoints read directly from the in-memory snapshot store and never invoke
hardware collectors inside the request thread.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from flask import Blueprint, Response, current_app, jsonify, send_from_directory

from backend.api.serialization import (
    serialize_error_response,
    serialize_health_response,
    serialize_status_response,
)


logger = logging.getLogger(__name__)

api_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")
dashboard_bp = Blueprint("dashboard", __name__)


def _get_frontend_dir() -> Path:
    """Retrieve the configured frontend directory from current_app."""
    fdir = current_app.config.get("FRONTEND_DIR")
    if fdir is not None:
        return Path(fdir)
    return Path(__file__).resolve().parent.parent.parent / "frontend"


@dashboard_bp.route("/", methods=["GET"])
def serve_dashboard() -> Response:
    """Serve the primary HTML5 dashboard shell for iPad Safari."""
    frontend_dir = _get_frontend_dir()
    return send_from_directory(frontend_dir, "index.html")


@dashboard_bp.route("/index.html", methods=["GET"])
def serve_index_html() -> Response:
    """Explicit alias for the primary dashboard shell."""
    frontend_dir = _get_frontend_dir()
    return send_from_directory(frontend_dir, "index.html")


@dashboard_bp.route("/css/<path:filename>", methods=["GET"])
def serve_css(filename: str) -> Response:
    """Serve same-origin CSS stylesheets with directory traversal protection."""
    frontend_dir = _get_frontend_dir()
    return send_from_directory(frontend_dir / "css", filename)


@dashboard_bp.route("/js/<path:filename>", methods=["GET"])
def serve_js(filename: str) -> Response:
    """Serve same-origin ES5 JavaScript scripts with directory traversal protection."""
    frontend_dir = _get_frontend_dir()
    return send_from_directory(frontend_dir / "js", filename)


@dashboard_bp.route("/assets/<path:filename>", methods=["GET"])
def serve_assets(filename: str) -> Response:
    """Serve local static assets with directory traversal protection."""
    frontend_dir = _get_frontend_dir()
    return send_from_directory(frontend_dir / "assets", filename)


def _get_monitor_context() -> tuple[Any, Any]:
    """Retrieve the SnapshotStore and MetricSampler from Flask app extensions."""
    context = current_app.extensions.get("pc_monitor", {})
    store = context.get("store")
    sampler = context.get("sampler")
    if store is None or sampler is None:
        raise RuntimeError("PCResourceMonitor context is not initialized on current_app.")
    return store, sampler


@api_bp.route("/status", methods=["GET"])
def get_status() -> tuple[Response, int]:
    """Return the latest normalized system metrics snapshot."""
    store, _ = _get_monitor_context()
    snapshot = store.get_snapshot()
    payload = serialize_status_response(snapshot)

    # Return 503 if no usable snapshot exists or all sections failed
    status_code = 503 if snapshot.get("overall_status") == "error" else 200
    return jsonify(payload), status_code


@api_bp.route("/health", methods=["GET"])
def get_health() -> tuple[Response, int]:
    """Report API and background sampler operational health."""
    store, sampler = _get_monitor_context()
    snapshot = store.get_snapshot()

    overall_status = snapshot.get("overall_status", "initializing")
    is_running = sampler.is_running
    interval = sampler.interval_seconds
    sequence = store.sequence

    payload = serialize_health_response(
        sampler_running=is_running,
        sampler_interval=interval,
        last_sequence=sequence,
        overall_status=overall_status,
    )

    status_code = 503 if payload["status"] == "unhealthy" else 200
    return jsonify(payload), status_code


@api_bp.app_errorhandler(404)
def handle_not_found(error: Exception) -> tuple[Response, int]:
    """Handle 404 with structured JSON payload."""
    return jsonify(serialize_error_response("NOT_FOUND", "Requested resource was not found.")), 404


@api_bp.app_errorhandler(405)
def handle_method_not_allowed(error: Exception) -> tuple[Response, int]:
    """Handle 405 with structured JSON payload."""
    return (
        jsonify(serialize_error_response("METHOD_NOT_ALLOWED", "HTTP method is not allowed.")),
        405,
    )


@api_bp.app_errorhandler(500)
def handle_internal_error(error: Exception) -> tuple[Response, int]:
    """Handle 500 without leaking stack traces or internal secrets."""
    logger.error("Internal server error: %s", error)
    return (
        jsonify(
            serialize_error_response(
                "INTERNAL_SERVER_ERROR",
                "An unexpected internal server error occurred.",
            )
        ),
        500,
    )
