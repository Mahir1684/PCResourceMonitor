"""Configuration management for PCResourceMonitor backend.

Defines safe configuration defaults and validation rules to ensure
the server only binds to approved local addresses and never exposes
telemetry publicly.
"""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, field
from typing import Any, Sequence


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5001
DEFAULT_SAMPLING_INTERVAL = 1.0
DEFAULT_ALLOWED_CLIENTS = ("127.0.0.1/32", "::1/128")


def _validate_host(host: str) -> str:
    """Validate host IP address. Never allows 0.0.0.0 by default."""
    if not host or not isinstance(host, str):
        raise ValueError("Host must be a non-empty string.")
    
    cleaned = host.strip()
    try:
        ip = ipaddress.ip_address(cleaned)
    except ValueError as exc:
        raise ValueError(f"Invalid host IP address: '{cleaned}'.") from exc

    if ip.is_unspecified:  # 0.0.0.0 or ::
        raise ValueError(
            "Binding to unspecified/wildcard address (0.0.0.0 or ::) is prohibited. "
            "Specify an explicit loopback or private LAN IP address."
        )
    return str(ip)


def _validate_port(port: Any) -> int:
    """Validate port is within valid TCP port range (1-65535)."""
    try:
        val = int(port)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Port must be an integer, got '{port}'.") from exc

    if not (1 <= val <= 65535):
        raise ValueError(f"Port must be between 1 and 65535, got {val}.")
    return val


def _validate_interval(interval: Any) -> float:
    """Validate sampling interval in seconds (> 0)."""
    try:
        val = float(interval)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Sampling interval must be a number, got '{interval}'.") from exc

    if val <= 0:
        raise ValueError(f"Sampling interval must be positive, got {val}.")
    return val


def _normalize_network(entry: str) -> ipaddress.IPv4Network | ipaddress.IPv6Network:
    """Normalize a single IP or CIDR string to an IP network."""
    entry = entry.strip()
    try:
        # strict=False allows host bits to be set e.g. 192.168.1.50/24 -> 192.168.1.0/24
        return ipaddress.ip_network(entry, strict=False)
    except ValueError:
        # Try as single IP address
        try:
            ip = ipaddress.ip_address(entry)
            return ipaddress.ip_network(f"{ip}/{ip.max_prefixlen}")
        except ValueError as exc:
            raise ValueError(f"Invalid client IP/CIDR in allowlist: '{entry}'.") from exc


def _validate_allowed_clients(
    clients: Sequence[str],
) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    """Validate and normalize a sequence of client IP/CIDR entries."""
    if not clients:
        raise ValueError("Allowed clients list cannot be empty. At least loopback must be allowed.")

    normalized = []
    for item in clients:
        if not isinstance(item, str):
            raise ValueError(f"Allowed client entry must be a string, got {type(item).__name__}.")
        normalized.append(_normalize_network(item))
    return tuple(normalized)


@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration."""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    sampling_interval_seconds: float = DEFAULT_SAMPLING_INTERVAL
    allowed_clients: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = field(
        default_factory=lambda: tuple(_normalize_network(c) for c in DEFAULT_ALLOWED_CLIENTS)
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "host", _validate_host(self.host))
        object.__setattr__(self, "port", _validate_port(self.port))
        object.__setattr__(
            self,
            "sampling_interval_seconds",
            _validate_interval(self.sampling_interval_seconds),
        )

    def is_client_allowed(self, client_ip: str) -> bool:
        """Check whether a client IP address matches any allowed network."""
        if not client_ip or not isinstance(client_ip, str):
            return False
        try:
            ip = ipaddress.ip_address(client_ip.strip())
        except ValueError:
            return False

        for net in self.allowed_clients:
            if ip in net:
                return True
        return False


def load_config(
    host: str | None = None,
    port: int | str | None = None,
    sampling_interval: float | str | None = None,
    allowed_clients: Sequence[str] | None = None,
) -> AppConfig:
    """Load and validate configuration from arguments with environment fallbacks."""
    # Host resolution
    env_host = os.environ.get("PC_MONITOR_HOST")
    chosen_host = host if host is not None else (env_host if env_host else DEFAULT_HOST)

    # Port resolution
    env_port = os.environ.get("PC_MONITOR_PORT")
    chosen_port = port if port is not None else (env_port if env_port else DEFAULT_PORT)

    # Interval resolution
    env_interval = os.environ.get("PC_MONITOR_SAMPLING_INTERVAL")
    chosen_interval = (
        sampling_interval
        if sampling_interval is not None
        else (env_interval if env_interval else DEFAULT_SAMPLING_INTERVAL)
    )

    # Allowed clients resolution
    env_clients = os.environ.get("PC_MONITOR_ALLOWED_CLIENTS")
    if allowed_clients is not None:
        client_list = allowed_clients
    elif env_clients:
        client_list = [c.strip() for c in env_clients.split(",") if c.strip()]
    else:
        client_list = list(DEFAULT_ALLOWED_CLIENTS)

    validated_clients = _validate_allowed_clients(client_list)

    return AppConfig(
        host=chosen_host,
        port=_validate_port(chosen_port),
        sampling_interval_seconds=_validate_interval(chosen_interval),
        allowed_clients=validated_clients,
    )
