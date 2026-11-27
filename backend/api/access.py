"""Access control and request security middleware.

Enforces source-IP allowlisting on incoming HTTP requests, ignores
client-supplied forwarded headers to prevent address spoofing, and
prohibits wildcard CORS.
"""

from __future__ import annotations

import logging
from typing import Any
from flask import Flask, Request, Response, jsonify, request

from backend.config import AppConfig


logger = logging.getLogger(__name__)


def is_request_authorized(req: Request, config: AppConfig) -> bool:
    """Verify if the request's real remote address is in the allowed client networks.
    
    Strictly uses req.remote_addr and never trusts X-Forwarded-For or X-Real-IP.
    """
    client_ip = req.remote_addr
    if not client_ip:
        logger.warning("Access denied: request has no remote address.")
        return False

    allowed = config.is_client_allowed(client_ip)
    if not allowed:
        logger.warning("Access denied for unauthorized client IP: %s", client_ip)
    return allowed


def init_access_control(app: Flask, config: AppConfig) -> None:
    """Register access control hooks and security headers on the Flask app."""

    @app.before_request
    def check_client_access() -> Response | None:
        # Strictly evaluate request.remote_addr; ignore any forwarded headers
        if not is_request_authorized(request, config):
            client_ip = request.remote_addr or "unknown"
            return (
                jsonify({
                    "error": {
                        "code": "ACCESS_DENIED",
                        "message": f"Access denied for client IP '{client_ip}'.",
                    }
                }),
                403,
            )
        return None

    @app.after_request
    def apply_security_headers(response: Response) -> Response:
        # Prevent caching of live telemetry API responses
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        # Security headers: prevent MIME sniffing, clickjacking, and XSS
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"
        )

        # Explicitly ensure no wildcard CORS is added
        if response.headers.get("Access-Control-Allow-Origin") == "*":
            del response.headers["Access-Control-Allow-Origin"]

        return response
