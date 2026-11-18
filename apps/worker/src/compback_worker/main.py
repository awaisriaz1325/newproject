"""Worker entrypoint: polls the Postgres job queue and dispatches handlers."""

from __future__ import annotations

import signal
import sys
import time
from types import FrameType

from compback_core.config import get_settings
from compback_core.logs import configure_logging, get_logger

log = get_logger(__name__)
_running = True


def _stop(signum: int, _frame: FrameType | None) -> None:
    global _running  # noqa: PLW0603 - process-wide shutdown flag
    log.info("worker_stopping", signal=signum)
    _running = False


def run(poll_interval: float = 1.0, once: bool = False) -> int:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json, f"{settings.service_name}-worker")
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log.info("worker_started")
    from compback_worker.runner import run_once  # noqa: PLC0415 - avoid import cost at module load

    while _running:
        processed = run_once()
        if once:
            return processed
        if processed == 0:
            time.sleep(poll_interval)
    return 0


if __name__ == "__main__":
    sys.exit(0 if run() >= 0 else 1)
