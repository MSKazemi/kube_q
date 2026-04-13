"""
config.py — Configuration loading and logging setup.

Priority order (highest wins):
  CLI flag  >  shell env var  >  ./.env  >  ~/.kube-q/.env  >  hardcoded default
"""

import logging
import logging.handlers
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

CONFIG_DIR = Path.home() / ".kube-q"
LOG_FILE   = CONFIG_DIR / "kube-q.log"


# ── Config dataclass ──────────────────────────────────────────────────────────

@dataclass
class Config:
    """All runtime configuration. CLI args override env vars which override defaults."""
    # Connection
    url:                    str        = "http://localhost:8000"
    api_key:                str | None = None

    # Timeouts (seconds)
    timeout:                float = 120.0   # query (stream + non-stream)
    health_timeout:         float =   5.0   # /healthz check
    namespace_timeout:      float =   3.0   # /v1/namespaces/:ns check
    startup_retry_timeout:  int   = 300     # total wait for API on startup
    startup_retry_interval: int   =   5     # seconds between startup retries

    # Behaviour
    stream:             bool = True
    output:             str  = "rich"   # "rich" | "plain"
    log_level:          str  = "INFO"
    skip_health_check:  bool = False

    # Model
    model: str = "kubeintellect-v2"

    # Display names
    user_name:  str = "You"
    agent_name: str = "kube-q"

    # Cost estimation overrides (USD per 1K tokens)
    cost_per_1k_prompt:      float | None = None
    cost_per_1k_completion:  float | None = None


# ── .env file support ─────────────────────────────────────────────────────────

# Maps KUBE_Q_* env var names → (config field, type).
_ENV_MAP: dict[str, tuple[str, type]] = {
    "KUBE_Q_URL":                    ("url",                    str),
    "KUBE_Q_API_KEY":                ("api_key",                str),
    "KUBE_Q_TIMEOUT":                ("timeout",                float),
    "KUBE_Q_HEALTH_TIMEOUT":         ("health_timeout",         float),
    "KUBE_Q_NAMESPACE_TIMEOUT":      ("namespace_timeout",      float),
    "KUBE_Q_STARTUP_RETRY_TIMEOUT":  ("startup_retry_timeout",  int),
    "KUBE_Q_STARTUP_RETRY_INTERVAL": ("startup_retry_interval", int),
    "KUBE_Q_STREAM":                 ("stream",                 bool),
    "KUBE_Q_OUTPUT":                 ("output",                 str),
    "KUBE_Q_LOG_LEVEL":              ("log_level",              str),
    "KUBE_Q_SKIP_HEALTH_CHECK":      ("skip_health_check",      bool),
    "KUBE_Q_MODEL":                  ("model",                  str),
    "KUBE_Q_USER_NAME":              ("user_name",              str),
    "KUBE_Q_AGENT_NAME":             ("agent_name",             str),
    "KUBE_Q_COST_PER_1K_PROMPT":     ("cost_per_1k_prompt",     float),
    "KUBE_Q_COST_PER_1K_COMPLETION": ("cost_per_1k_completion", float),
}


def _load_dotenv_file(path: Path) -> None:
    """Minimal .env parser — sets env vars not already in the environment.

    Supports KEY=VALUE, KEY="VALUE", KEY='VALUE', and inline # comments.
    Shell-set variables always win (no override).
    """
    if not path.exists():
        return
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.split("#")[0].strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


def _apply_env(cfg: Config) -> None:
    """Override cfg fields from environment variables."""
    for env_key, (field, typ) in _ENV_MAP.items():
        val = os.environ.get(env_key)
        if val is None:
            continue
        if typ is bool:
            setattr(cfg, field, val.lower() not in ("0", "false", "no", "off"))
        else:
            try:
                setattr(cfg, field, typ(val))
            except (ValueError, TypeError):
                print(
                    f"Warning: invalid value for {env_key}={val!r} "
                    f"(expected {typ.__name__}) — ignored",
                    file=sys.stderr,
                )


def load_config() -> Config:
    """Load configuration from .env files and environment variables.

    .env files loaded (lower to higher priority):
      ~/.kube-q/.env    — persistent user-level defaults
      ./.env            — project-local or per-cluster overrides
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Load .env files before reading env vars.
    # Shell-exported variables are never overwritten.
    _load_dotenv_file(CONFIG_DIR / ".env")  # user-level  (lower priority)
    _load_dotenv_file(Path(".env"))          # local        (higher priority)

    cfg = Config()
    _apply_env(cfg)
    return cfg


# ── Logging setup ─────────────────────────────────────────────────────────────

def setup_logging(log_level: str = "INFO", debug: bool = False) -> None:
    """Configure the kube_q logger.

    Always writes to ~/.kube-q/kube-q.log (rotating, 5 MB × 3).
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
