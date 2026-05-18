import json
import logging
import sys

_SKIP_ATTRS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "taskName",
})


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        log: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
        }
        if record.exc_info:
            log["traceback"] = self.formatException(record.exc_info)
        for key, val in record.__dict__.items():
            if key not in _SKIP_ATTRS:
                log[key] = val
        return json.dumps(log, default=str)


class _DevFormatter(logging.Formatter):
    COLORS = {
        "DEBUG":    "\033[36m",   # cyan
        "INFO":     "\033[32m",   # green
        "WARNING":  "\033[33m",   # yellow
        "ERROR":    "\033[31m",   # red
        "CRITICAL": "\033[35m",   # magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        prefix = f"{color}{record.levelname:<8}{self.RESET}"
        name = f"\033[2m{record.name}\033[0m"
        msg = record.getMessage()
        line = f"{prefix} {name}: {msg}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def setup_logging(level: str = "INFO", environment: str = "development") -> None:
    handler = logging.StreamHandler(sys.stdout)

    is_dev = environment == "development"
    handler.setFormatter(_DevFormatter() if is_dev else _JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    if is_dev:
        # In dev: let uvicorn access logs through so each request is visible
        logging.getLogger("uvicorn.access").propagate = True
    else:
        # In prod: suppress uvicorn access log — middleware emits equivalent JSON
        uv_access = logging.getLogger("uvicorn.access")
        uv_access.handlers.clear()
        uv_access.propagate = False
