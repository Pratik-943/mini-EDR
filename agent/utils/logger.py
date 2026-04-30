from loguru import logger
from pathlib import Path


def _setup_logger():
    """Configure loguru to write logs to agent/logs/agent.log with rotation and retention."""
    base_dir = Path(__file__).resolve().parents[1]
    logs_dir = base_dir / "logs"
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        # best-effort: if we can't create, loguru will try to write and fail later
        pass

    log_file = logs_dir / "agent.log"

    # Remove default handlers to avoid duplicate sinks
    logger.remove()

    # File sink: rotate at 5 MB, keep 10 days, INFO level
    logger.add(
        str(log_file),
        rotation="5 MB",
        retention="10 days",
        level="INFO",
        encoding="utf-8",
    )

    # HTTP Forwarder Sink
    try:
        from agent.utils.forwarder import http_sink
        logger.add(http_sink, level="INFO")
    except ImportError:
        pass


# Initialize on import
_setup_logger()


def get_logger():
    """Return the configured loguru logger."""
    return logger
