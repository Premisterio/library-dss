import logging

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.worker.runner import run_forever

settings = get_settings()
logging.basicConfig(
    level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
run_forever(
    get_sessionmaker(),
    poll_seconds=settings.worker_poll_seconds,
    stale_seconds=settings.job_stale_seconds,
)
