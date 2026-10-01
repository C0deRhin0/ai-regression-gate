import json
import logging
from pathlib import Path

from argate.analysis.secrets import safe_text

logger = logging.getLogger("argate")


def configure(verbose: bool):
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    handler.setLevel(logging.INFO if verbose else logging.WARNING)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def event(name: str, audit_log: Path | None = None, **fields):
    def sanitize(value):
        if isinstance(value, str):
            return safe_text(value)
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        if isinstance(value, dict):
            return {key: sanitize(item) for key, item in value.items()}
        return value
    record = json.dumps(sanitize({"event": name, **fields}), sort_keys=True)
    logger.info(record)
    if audit_log:
        with audit_log.open("a", encoding="utf-8") as stream:
            stream.write(record + "\n")
