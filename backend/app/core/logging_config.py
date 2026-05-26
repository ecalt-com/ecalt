"""
Centralised logging configuration for the ECALT backend.

Usage in any module:
    from app.core.logging_config import get_logger
    logger = get_logger(__name__)

Or the standard stdlib pattern works identically:
    import logging
    logger = logging.getLogger(__name__)

setup_logging() must be called once at startup (main.py does this).
It uses logging.config.dictConfig so it survives uvicorn --reload cycles.
"""

import json
import logging
import logging.config
import sys
from typing import Any

# Fields that are standard LogRecord attributes — excluded from the extras
# block so we don't double-print them.
_SKIP_ATTRS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "taskName",
})


# ── Formatters ────────────────────────────────────────────────────────────────

class _JsonFormatter(logging.Formatter):
    """Structured JSON — one object per line. Used in production."""

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        entry: dict = {
            "ts":      self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level":   record.levelname,
            "logger":  record.name,
            "message": record.message,
        }
        if record.exc_info:
            entry["traceback"] = self.formatException(record.exc_info)
        # Append any extra={} fields passed at the call site
        for key, val in record.__dict__.items():
            if key not in _SKIP_ATTRS:
                entry[key] = val
        return json.dumps(entry, default=str)


class _DevFormatter(logging.Formatter):
    """Coloured, human-readable format for local development.

    Renders extra={} fields as  key=value  pairs after the message so
    context passed via logger.info("msg", extra={"key": "val"}) is visible.
    """

    _COLORS = {
        "DEBUG":    "\033[36m",   # cyan
        "INFO":     "\033[32m",   # green
        "WARNING":  "\033[33m",   # yellow
        "ERROR":    "\033[31m",   # red
        "CRITICAL": "\033[35m",   # magenta
    }
    _RESET = "\033[0m"
    _DIM   = "\033[2m"

    def format(self, record: logging.LogRecord) -> str:
        color  = self._COLORS.get(record.levelname, "")
        level  = f"{color}{record.levelname:<8}{self._RESET}"
        name   = f"{self._DIM}{record.name}{self._RESET}"
        msg    = record.getMessage()

        # Collect extra fields (anything not in the standard set)
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in _SKIP_ATTRS
        }
        extras_str = ""
        if extras:
            extras_str = "  " + "  ".join(
                f"{self._DIM}{k}{self._RESET}={color}{v}{self._RESET}"
                for k, v in extras.items()
            )

        line = f"{level} {name}: {msg}{extras_str}"

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


# ── dictConfig builder ────────────────────────────────────────────────────────

def _build_dictconfig(level: str, environment: str) -> dict[str, Any]:
    """
    Returns a logging.config.dictConfig-compatible dict.

    Using dictConfig (instead of manually attaching handlers) is the only
    approach that reliably survives uvicorn --reload, because uvicorn itself
    calls dictConfig internally and the two configs then merge cleanly via
    disable_existing_loggers=False.
    """
    is_dev = environment == "development"

    # Reference the formatter classes by their fully-qualified name so
    # dictConfig can instantiate them with "()".
    fmt_class = (
        f"{__name__}._DevFormatter"
        if is_dev
        else f"{__name__}._JsonFormatter"
    )

    return {
        "version": 1,
        # False = loggers created before this call (e.g. at import time via
        # logging.getLogger(__name__)) are NOT disabled. Critical for modules
        # that set up their logger at module load before setup_logging() runs.
        "disable_existing_loggers": False,
        "formatters": {
            "ecalt": {"()": fmt_class},
        },
        "handlers": {
            "console": {
                "class":     "logging.StreamHandler",
                "stream":    "ext://sys.stdout",
                "formatter": "ecalt",
            },
        },
        "root": {
            "handlers": ["console"],
            "level":    level.upper(),
        },
        "loggers": {
            # ── uvicorn ───────────────────────────────────────────────────────
            # In dev: let uvicorn.access propagate so each request line is visible.
            # In prod: suppress it — the request middleware already emits JSON logs.
            "uvicorn":        {"level": "INFO",    "propagate": True,    "handlers": []},
            "uvicorn.error":  {"level": "INFO",    "propagate": True,    "handlers": []},
            "uvicorn.access": {
                "level":     "INFO",
                "propagate": is_dev,
                "handlers":  [],
            },

            # ── noisy third-party libraries ───────────────────────────────────
            "httpx":          {"level": "WARNING", "propagate": True,    "handlers": []},
            "httpcore":       {"level": "WARNING", "propagate": True,    "handlers": []},
            "stripe":         {"level": "WARNING", "propagate": True,    "handlers": []},
            "razorpay":       {"level": "WARNING", "propagate": True,    "handlers": []},
            "apscheduler":    {"level": "WARNING", "propagate": True,    "handlers": []},
            "passlib":        {"level": "WARNING", "propagate": True,    "handlers": []},
            "multipart":      {"level": "WARNING", "propagate": True,    "handlers": []},
        },
    }


# ── Public API ────────────────────────────────────────────────────────────────

def setup_logging(level: str = "INFO", environment: str = "development") -> None:
    """
    Configure logging for the entire application.

    Called twice in main.py:
      1. At module import (before uvicorn touches anything).
      2. Inside the lifespan handler (after uvicorn has done its own setup).

    The second call is what actually sticks — it re-applies our config on top
    of whatever uvicorn set up, including on --reload cycles.
    """
    logging.config.dictConfig(_build_dictconfig(level, environment))


def get_logger(name: str) -> logging.Logger:
    """
    Convenience wrapper. Preferred usage in new modules:

        from app.core.logging_config import get_logger
        logger = get_logger(__name__)

    Identical to logging.getLogger(name) — just makes the import explicit
    and self-documenting.
    """
    return logging.getLogger(name)
