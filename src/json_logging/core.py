from __future__ import annotations
import json
import logging
import os
import sys
import time
from typing import Any, Dict

ENV_DEBUG = os.getenv("DEBUG", "0") == "1"
ENV_FORCE_JSON = os.getenv("FORCE_JSON", "0") == "1"
ENV_FORCE_LOG_FMT = os.getenv("FORCE_LOG_FMT", "0") == "1"
ENV_RESET_LOGGING = os.getenv("RESET_LOGGING", "1") == "1"
ENV_SERVICE = os.getenv("SERVICE", os.path.basename(sys.argv[0]).replace(".py", ""))
ENV_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
ENV_VERSION = os.getenv("APP_VERSION", "unknown")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z"
        payload: Dict[str, Any] = {
            "ts": ts,
            "level": record.levelname.lower(),
            "service": ENV_SERVICE,
            "version": ENV_VERSION,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "lineno": record.lineno,
            "pid": record.process,
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        for k, v in record.__dict__.items():
            if k in (
                "args",
                "msg",
                "levelname",
                "levelno",
                "name",
                "module",
                "funcName",
                "lineno",
                "created",
                "msecs",
                "process",
                "processName",
                "thread",
                "threadName",
                "exc_info",
            ):
                continue
            if k.startswith("_"):
                continue
            if k not in payload:
                try:
                    json.dumps(v)
                    payload[k] = v
                except Exception:
                    payload[k] = str(v)
        return json.dumps(payload, ensure_ascii=False)


def _make_console_formatter() -> logging.Formatter:
    fmt = "%(asctime)s [%(levelname)s] %(name)s (%(funcName)s#%(lineno)d) %(message)s" if ENV_DEBUG else "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    return logging.Formatter(fmt=fmt, datefmt="%H:%M:%S")


def _should_use_json() -> bool:
    if ENV_FORCE_JSON:
        return True  # if both are set, JSON wins
    if ENV_FORCE_LOG_FMT:
        return False
    return not sys.stdout.isatty()  # JSON if not a TTY


def _attach_handler(root: logging.Logger, handler: logging.Handler, reset: bool) -> None:
    if reset or not root.handlers:
        if reset:
            root.handlers.clear()
        root.addHandler(handler)
        return

    for existing in root.handlers:
        if isinstance(existing, logging.StreamHandler):
            existing.setFormatter(handler.formatter)
            return

    root.addHandler(handler)


def setup_logging(*, reset_handlers: bool | None = None) -> None:
    root = logging.getLogger()
    if getattr(root, "_json_logging_initialized", False):
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if _should_use_json() else _make_console_formatter())

    reset = ENV_RESET_LOGGING if reset_handlers is None else reset_handlers
    _attach_handler(root, handler, reset)
    level = getattr(logging, ENV_LEVEL, logging.INFO)
    root.setLevel(logging.DEBUG if ENV_DEBUG else level)

    # optional: quiet noisy libs
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore.http11").setLevel(logging.WARNING)
    logging.getLogger("httpcore.connection").setLevel(logging.WARNING)
    logging.getLogger("amcrest.http").setLevel(logging.ERROR)
    logging.getLogger("amcrest.event").setLevel(logging.WARNING)
    logging.getLogger("blinkpy.blinkpy").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

    root._json_logging_initialized = True  # type: ignore[attr-defined]


def get_logger(name: str | None = None) -> logging.Logger:
    setup_logging()
    base = logging.getLogger(name or ENV_SERVICE)
    return logging.LoggerAdapter(base, {"version": ENV_VERSION})
