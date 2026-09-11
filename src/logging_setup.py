"""Central logging configuration, called once from each entry-point script's
__main__ block. Every other module just does `log = logging.getLogger(__name__)`
at import time and logs through it - no per-module setup needed.

Logs go to both console AND a rotating file (data/app.log), not console alone:
per CLAUDE.md, run_admin.ps1 launches the elevated Windows process with
`-WindowStyle Hidden`, so a console-only log would be silently invisible on
every elevated (click/press_key-driven) run - the exact scenario this project
already documented once for a different reason (a hidden console stealing
focus). The file is what's actually there to inspect afterward in that case.
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOG_PATH = DATA_DIR / "app.log"

_configured = False


def configure_logging(level: int = logging.DEBUG) -> None:
    """Idempotent - safe to call even if a script is imported more than once
    (or imports another entry-point module that also calls this)."""
    global _configured
    if _configured:
        return
    _configured = True

    DATA_DIR.mkdir(exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s", datefmt="%H:%M:%S"
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.setLevel(level)

    file_handler = RotatingFileHandler(LOG_PATH, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console)
    root.addHandler(file_handler)

    # PIL logs its own internals at DEBUG (e.g. every PNG chunk parsed) -
    # confirmed live, it drowns out this app's own DEBUG lines - cap it at
    # WARNING regardless of the app's chosen level, so "DEBUG everywhere"
    # means this app's DEBUG output, not every dependency's. PaddleOCR/
    # PaddleX's own startup chatter (model-loading messages, glog warnings)
    # mostly bypasses Python's logging module entirely (raw prints / a C++
    # glog backend) - not suppressible this way, would need env vars
    # (GLOG_minloglevel etc.) instead; not done here since it's cosmetic.
    for noisy in ("PIL",):
        logging.getLogger(noisy).setLevel(logging.WARNING)
