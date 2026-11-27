"""Windows production server startup entrypoint using Waitress WSGI server.

Binds strictly to the configured host address (default 127.0.0.1) and port,
starts the background telemetry sampler, and provides clean signal shutdown.
"""

from __future__ import annotations

import logging
import sys
import waitress

from backend.app import create_app
from backend.config import load_config


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pc_resource_monitor")


def main() -> None:
    """Launch the PCResourceMonitor production WSGI server."""
    config = load_config()

    logger.info("Starting PCResourceMonitor on http://%s:%d", config.host, config.port)
    logger.info("Sampling interval: %.1f seconds", config.sampling_interval_seconds)
    logger.info("Allowed client networks: %s", [str(n) for n in config.allowed_clients])

    app = create_app(config=config, start_sampler=True)

    try:
        waitress.serve(
            app,
            host=config.host,
            port=config.port,
            threads=4,
            ident=None,  # Suppress server signature header
        )
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user (SIGINT).")
    finally:
        logger.info("Stopping telemetry sampler...")
        if hasattr(app, "stop_sampler"):
            app.stop_sampler()
        logger.info("Server terminated cleanly.")


if __name__ == "__main__":
    main()
