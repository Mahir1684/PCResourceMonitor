"""Flask application factory for PCResourceMonitor.

Creates and configures the Flask application, wires the in-memory
SnapshotStore, initializes telemetry collectors, registers the MetricSampler,
and sets up access control and API routes.
"""

from __future__ import annotations

import atexit
import logging
from pathlib import Path
from typing import Any
from flask import Flask

from backend.api.access import init_access_control
from backend.api.routes import api_bp, dashboard_bp
from backend.config import AppConfig, load_config
from backend.monitoring.cpu import CpuCollector
from backend.monitoring.fps import FpsCollector
from backend.monitoring.gpus import GpuCollector
from backend.monitoring.memory import MemoryCollector
from backend.monitoring.network import NetworkCollector
from backend.monitoring.sampler import MetricSampler
from backend.monitoring.snapshot import SnapshotStore
from backend.monitoring.storage import StorageCollector
from backend.monitoring.system import SystemCollector


logger = logging.getLogger(__name__)

DEFAULT_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def create_app(
    config: AppConfig | None = None,
    start_sampler: bool = True,
    collectors: dict[str, Any] | None = None,
    frontend_dir: Path | str | None = None,
) -> Flask:
    """Create and configure a PCResourceMonitor Flask application instance.
    
    Args:
        config: Application configuration. Defaults to load_config().
        start_sampler: Whether to start the background sampler thread immediately.
            Set to False in tests to avoid duplicate background threads.
        collectors: Optional custom/mock collectors dict for dependency injection in tests.
        frontend_dir: Optional custom frontend directory for static assets and dashboard HTML.
    """
    app = Flask(__name__)
    app_config = config or load_config()

    # Configure frontend directory
    app.config["FRONTEND_DIR"] = (
        Path(frontend_dir) if frontend_dir is not None else DEFAULT_FRONTEND_DIR
    )

    # Disable default Flask development banner and debug mode
    app.config["ENV"] = "production"
    app.config["DEBUG"] = False
    app.config["TESTING"] = not start_sampler

    # Initialize store and collectors
    store = SnapshotStore()

    gpu_collector: GpuCollector | None = None
    fps_collector: FpsCollector | None = None
    if collectors is not None:
        active_collectors = collectors
    else:
        cpu_collector = CpuCollector()
        memory_collector = MemoryCollector()
        storage_collector = StorageCollector()
        network_collector = NetworkCollector()
        system_collector = SystemCollector()
        gpu_collector = GpuCollector()
        fps_collector = FpsCollector(autostart=start_sampler)
        if start_sampler:
            atexit.register(fps_collector.stop)

        active_collectors = {
            "cpu": cpu_collector.collect,
            "memory": memory_collector.collect,
            "storage": storage_collector.collect,
            "network": network_collector.collect,
            "system": system_collector.collect,
            "gpus": gpu_collector.collect,
            "fps": fps_collector.collect,
        }

    # Initialize background sampler
    sampler = MetricSampler(
        store=store,
        interval_seconds=app_config.sampling_interval_seconds,
        collectors=active_collectors,
    )

    # Attach to app extensions dictionary for thread-safe access from route handlers
    app.extensions["pc_monitor"] = {
        "config": app_config,
        "store": store,
        "sampler": sampler,
        "gpu_collector": gpu_collector,
        "fps_collector": fps_collector,
    }

    # Initialize access control security hooks
    init_access_control(app, app_config)

    # Register blueprints
    app.register_blueprint(api_bp)
    app.register_blueprint(dashboard_bp)

    # Provide helper method on app instance for explicit cleanup
    def stop_sampler() -> None:
        if sampler.is_running:
            sampler.stop()
        if gpu_collector is not None:
            gpu_collector.shutdown()

    app.stop_sampler = stop_sampler  # type: ignore[attr-defined]

    # Register process exit cleanup hook
    atexit.register(stop_sampler)

    # Prime store with initial sample and start background thread if requested
    if start_sampler:
        try:
            sampler.sample_once()
        except Exception as exc:
            logger.warning("Initial sampling pass encountered error: %s", exc)

        sampler.start()

    return app
