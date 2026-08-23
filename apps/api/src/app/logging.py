import json
import logging
from contextvars import ContextVar, Token
from typing import Any

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


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
    event_context = dict(context or {})
    request_id = _request_id.get()
    if request_id is not None:
        event_context.setdefault("request_id", request_id)
    logger.info(message, extra={"event": event, "context": event_context})


def bind_request_id(request_id: str) -> Token:
    return _request_id.set(request_id)


def reset_request_id(token: Token) -> None:
    _request_id.reset(token)
