from __future__ import annotations
import json, logging, os, sys, time
from typing import Any, Dict

ENV_DEBUG   = os.getenv("DEBUG", "0") == "1"
ENV_JSON    = os.getenv("FORCE_JSON", "0") == "1"
ENV_SERVICE = os.getenv("SERVICE", os.path.basename(sys.argv[0]).replace(".py",""))
ENV_LEVEL   = os.getenv("LOG_LEVEL", "INFO").upper()

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z"
        payload: Dict[str, Any] = {
            "ts": ts,
            "level": record.levelname.lower(),
            "service": ENV_SERVICE,
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
            if k in ("args","msg","levelname","levelno","name","module","funcName","lineno",
                     "created","msecs","process","processName","thread","threadName","exc_info"):
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
    fmt = "%(asctime)s [%(levelname)s] %(name)s (%(funcName)s#%(lineno)d) %(message)s" if ENV_DEBUG \
          else "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    return logging.Formatter(fmt=fmt, datefmt="%H:%M:%S")

def setup_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_json_logging_initialized", False):
        return

    handler = logging.StreamHandler(sys.stdout)
    use_json = (not sys.stdout.isatty()) or ENV_JSON
    handler.setFormatter(JsonFormatter() if use_json else _make_console_formatter())

    root.handlers.clear()
    root.addHandler(handler)
    level = getattr(logging, ENV_LEVEL, logging.INFO)
    root.setLevel(logging.DEBUG if ENV_DEBUG else level)

    # optional: quiet noisy libs
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.INFO)

    root._json_logging_initialized = True  # type: ignore[attr-defined]

def get_logger(name: str | None = None) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name or ENV_SERVICE)
