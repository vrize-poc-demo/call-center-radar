import json
import logging
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "event"):
            payload["event"] = record.event
        if hasattr(record, "context"):
            payload["context"] = record.context
        return json.dumps(payload, sort_keys=True)


def configure_logging(level: str) -> logging.Logger:
    logger = logging.getLogger("call_center_radar")
    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

    return logger


def log_event(
    logger: logging.Logger, event: str, message: str, *, context: dict[str, Any] | None = None
) -> None:
    logger.info(message, extra={"event": event, "context": context or {}})
