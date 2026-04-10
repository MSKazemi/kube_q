"""
config.py — Config file loading (~/.kubeintellect/config.yaml) and logging setup.
"""

import logging
import logging.handlers
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────

CONFIG_DIR  = Path.home() / ".kubeintellect"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
LOG_FILE    = CONFIG_DIR / "kubeintellect.log"


# ── Config dataclass ──────────────────────────────────────────────────────────

@dataclass
class Config:
    """All runtime configuration.  CLI args override config file which overrides defaults."""
    # Connection
    url:                    str   = "http://localhost:8000"
    api_key:                str | None = None

    # Timeouts (seconds)
    timeout:                float = 120.0   # query (stream + non-stream)
    health_timeout:         float =   5.0   # /healthz check
    namespace_timeout:      float =   3.0   # /v1/namespaces/:ns check
    startup_retry_timeout:  int   = 300     # total wait for API on startup
    startup_retry_interval: int   =   5     # seconds between startup retries

    # Behaviour
    stream:    bool = True
    output:    str  = "rich"      # "rich" | "plain"
    log_level: str  = "INFO"


# ── YAML loading ──────────────────────────────────────────────────────────────

_KNOWN_KEYS: set[str] = {
    "url", "api_key",
    "timeout", "health_timeout", "namespace_timeout",
    "startup_retry_timeout", "startup_retry_interval",
    "stream", "output", "log_level",
}


def load_config() -> Config:
    """Load ~/.kubeintellect/config.yaml; return defaults if absent or unreadable."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        return Config()

    try:
        import yaml  # type: ignore[import-untyped]  # pyyaml
    except ImportError:
        print(
            f"Warning: pyyaml is not installed — {CONFIG_FILE} will be ignored. "
            "Run: pip install pyyaml",
            file=sys.stderr,
        )
        return Config()

    try:
        raw: dict[str, Any] = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"Warning: could not parse {CONFIG_FILE}: {exc}", file=sys.stderr)
        return Config()

    cfg = Config()
    unknown = []
    for key, value in raw.items():
        if key in _KNOWN_KEYS:
            setattr(cfg, key, value)
        else:
            unknown.append(key)

    if unknown:
        print(
            f"Warning: unknown key(s) in {CONFIG_FILE}: {', '.join(unknown)}",
            file=sys.stderr,
        )
    return cfg


# ── Logging setup ─────────────────────────────────────────────────────────────

def setup_logging(log_level: str = "INFO", debug: bool = False) -> None:
    """Configure the kube_q logger.

    Always writes to ~/.kubeintellect/kubeintellect.log (rotating, 5 MB × 3).
    When *debug* is True the level is forced to DEBUG and a second handler
    writes brief lines to stderr so the user sees live HTTP chatter.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    effective_level = logging.DEBUG if debug else getattr(logging, log_level.upper(), logging.INFO)

    logger = logging.getLogger("kube_q")
    logger.setLevel(effective_level)

    # Avoid duplicate handlers when called more than once (e.g., in tests)
    if logger.handlers:
        return

    file_fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # ── Rotating file handler ─────────────────────────────────────────────────
    try:
        fh = logging.handlers.RotatingFileHandler(
            LOG_FILE,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        fh.setLevel(effective_level)
        fh.setFormatter(file_fmt)
        logger.addHandler(fh)
    except OSError as exc:
        print(f"Warning: cannot open log file {LOG_FILE}: {exc}", file=sys.stderr)

    # ── Stderr handler (debug mode only) ──────────────────────────────────────
    if debug:
        sh = logging.StreamHandler(sys.stderr)
        sh.setLevel(logging.DEBUG)
        sh.setFormatter(logging.Formatter("  \033[2mDEBUG %(name)s: %(message)s\033[0m"))
        logger.addHandler(sh)
