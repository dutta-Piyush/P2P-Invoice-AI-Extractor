import logging
from contextvars import ContextVar
from core.config import settings

_cid: ContextVar[str] = ContextVar("cid", default="-")

class CidFormatter(logging.Formatter):
    """Custom formatter that provides a default value for 'cid' if missing."""
    def format(self, record):
        if not hasattr(record, 'cid'):
            record.cid = _cid.get()
        return super().format(record)

def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    formatter = CidFormatter(
        "%(asctime)s | %(levelname)s | %(cid)s | %(name)s | %(message)s"
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

# Expose for use in main.py
cid = _cid
