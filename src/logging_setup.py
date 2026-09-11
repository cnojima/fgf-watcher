"""Central logging configuration, called once from each entry-point script's
__main__ block. Every other module just does `log = logging.getLogger(__name__)`
at import time and logs through it - no per-module setup needed.

Logs go to both console AND a file, not console alone: per CLAUDE.md,
run_admin.ps1 launches the elevated Windows process with `-WindowStyle
Hidden`, so a console-only log would be silently invisible on every elevated
(click/press_key-driven) run - the exact scenario this project already
documented once for a different reason (a hidden console stealing focus).
The file is what's actually there to inspect afterward in that case.

Each run gets its OWN timestamp-named file under data/logs/, not one shared,
ever-growing app.log - confirmed directly as a real problem: a single shared
log accumulated past 4000+ lines across unrelated runs, making it useless
for diagnosing "what happened in THIS run" without picking through every
other run's output first. A fresh per-run file needs no rotation (its size
is naturally bounded by that one run), so this no longer uses
RotatingFileHandler.
"""
import logging
import time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOG_DIR = DATA_DIR / "logs"

_configured = False
_log_path: Path | None = None


def configure_logging(level: int = logging.DEBUG) -> Path:
    """Idempotent - safe to call even if a script is imported more than once
    (or imports another entry-point module that also calls this). Returns
    this run's log file path (whether just created, or the one an earlier
    call in this same process already set up) - also logged at startup so
    it's visible on the console without needing the return value."""
    global _configured, _log_path
    if _configured:
        return _log_path
    _configured = True

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _log_path = LOG_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}.log"

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s", datefmt="%H:%M:%S"
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.setLevel(level)

    file_handler = logging.FileHandler(_log_path, encoding="utf-8")
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

    logging.getLogger(__name__).info("Logging to %s", _log_path)
    return _log_path
