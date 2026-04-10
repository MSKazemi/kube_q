#!/usr/bin/env python3
"""
kube-q — interactive terminal interface for the kube-q API.

Usage:
  kq                          # interactive REPL
  kq --query "get all pods"   # single query and exit
  kq --url http://host:8000   # custom API URL
  kq --no-stream              # disable streaming
  kq --user-id myuser         # set persistent user ID
  kq --no-banner              # suppress logo (screen recording)
  kq --api-key <key>          # authenticate with an API key
  kq --ca-cert /path/cert.pem # custom CA cert for TLS
  kq --output plain           # plain text output (no markdown)
  kq --debug                  # show raw HTTP requests/responses
  kq --version                # print version and exit

Environment variables:
  KUBE_Q_URL=http://...           # set API URL
  KUBE_Q_API_KEY=...             # set API key

Config file (~/.kubeintellect/config.yaml):
  url: http://localhost:8000
  timeout: 120          # query timeout in seconds
  health_timeout: 5
  namespace_timeout: 3
  startup_retry_timeout: 300
  startup_retry_interval: 5
  stream: true
  log_level: INFO       # DEBUG | INFO | WARNING | ERROR
  output: rich          # rich | plain

In-REPL commands:
  /new           — start a new conversation (new conversation ID)
  /id            — show current conversation ID
  /state         — show current session state in one line
  /clear         — clear the terminal screen
  /save [file]   — save conversation to markdown file
  /ns <name>     — set active namespace (/ns with no arg clears it)
  /approve       — approve a pending HITL action
  /deny          — deny a pending HITL action
  /help          — show full in-REPL help
  /quit          — exit

Keyboard shortcuts:
  Enter          — send message
  Alt+Enter      — insert newline (for multi-line messages)
  Esc → Enter    — insert newline (universal fallback)
  Tab            — auto-complete slash commands

Attaching files:
  @file.yaml                 — embed a file's contents in your message
  @~/path/to/file.json       — home-relative paths supported
  @"path/with spaces.txt"    — quote paths that contain spaces
  what is wrong? @pod.yaml   — use anywhere in a message; multiple files per message ok
  Supported: yaml, json, py, sh, go, tf, toml, js, ts, txt, log, and more (100 KB limit)
"""

import argparse
import os
import uuid
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from urllib.parse import urlparse

from kube_q.config import load_config, setup_logging
from kube_q.render import console, set_output_plain
from kube_q.session import _load_or_create_user_id, run_repl
from kube_q.transport import non_stream_query, set_debug, stream_query

try:
    __version__ = _pkg_version("kube-q")
except PackageNotFoundError:
    __version__ = "unknown"


# ── Single-query mode ─────────────────────────────────────────────────────────

def run_single_query(
    url: str,
    query: str,
    stream: bool,
    user_id: str | None = None,
    api_key: str | None = None,
    ca_cert: str | None = None,
    timeout: float = 120.0,
) -> None:
    conversation_id = str(uuid.uuid4())
    if user_id is None:
        user_id = _load_or_create_user_id()
    messages = [{"role": "user", "content": query}]

    if stream:
        stream_query(url, messages, conversation_id, user_id,
                     api_key=api_key, ca_cert=ca_cert, timeout=timeout)
    else:
        non_stream_query(url, messages, conversation_id, user_id,
                         api_key=api_key, ca_cert=ca_cert, timeout=timeout)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    # Load config file first so CLI args can override it
    cfg = load_config()

    parser = argparse.ArgumentParser(
        prog="kq",
        description="kube-q — chat with your Kubernetes cluster.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"kube-q {__version__}",
    )
    parser.add_argument(
        "--url",
        default=os.getenv("KUBE_Q_URL", cfg.url),
        help=(
            "kube-q API base URL "
            "(env: KUBE_Q_URL, config: url, default: http://localhost:8000)"
        ),
    )
    parser.add_argument(
        "--query", "-q",
        default=None,
        help="Run a single query and exit (non-interactive mode)",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        default=not cfg.stream,
        help="Disable streaming — wait for full response",
    )
    parser.add_argument(
        "--conversation-id",
        default=None,
        help="Resume an existing conversation by ID",
    )
    parser.add_argument(
        "--user-id",
        default=None,
        metavar="ID",
        help=(
            "User ID to send with requests (persisted to ~/.kube_q_id). "
            "Reads from ~/.kube_q_id if not supplied."
        ),
    )
    parser.add_argument(
        "--no-banner", "--quiet",
        dest="quiet",
        action="store_true",
        default=False,
        help="Suppress logo and header panel (useful for screen recordings)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("KUBE_Q_API_KEY", cfg.api_key),
        metavar="KEY",
        help="API key for authentication (env: KUBE_Q_API_KEY, config: api_key)",
    )
    parser.add_argument(
        "--ca-cert",
        default=None,
        metavar="PATH",
        help="Path to custom CA certificate bundle for TLS verification",
    )
    parser.add_argument(
        "--output",
        choices=["rich", "plain"],
        default=cfg.output,
        help="Output format: 'rich' (default, markdown rendering) or 'plain' (raw text)",
    )
    parser.add_argument(
        "--debug", "--verbose",
        dest="debug",
        action="store_true",
        default=False,
        help=(
            "Enable debug mode: log raw HTTP requests/responses to stderr "
            "and ~/.kubeintellect/kubeintellect.log"
        ),
    )

    args = parser.parse_args()

    # ── Logging ───────────────────────────────────────────────────────────────
    setup_logging(log_level=cfg.log_level, debug=args.debug)
    if args.debug:
        set_debug(True)

    stream = not args.no_stream
    user_id = _load_or_create_user_id(args.user_id)

    if args.output == "plain":
        set_output_plain(True)

    # Warn on plain-HTTP connections to non-local hosts
    parsed_url = urlparse(args.url)
    if parsed_url.scheme == "http":
        host = parsed_url.hostname or ""
        if host not in ("localhost", "127.0.0.1", "::1", ""):
            console.print(
                f"[yellow]Warning:[/yellow] connecting over plain HTTP to "
                f"[bold]{args.url}[/bold] — consider using HTTPS in production."
            )

    if args.query:
        run_single_query(
            args.url, args.query, stream,
            user_id=user_id, api_key=args.api_key, ca_cert=args.ca_cert,
            timeout=cfg.timeout,
        )
    else:
        run_repl(
            args.url, stream, args.conversation_id,
            user_id=user_id, quiet=args.quiet,
            api_key=args.api_key, ca_cert=args.ca_cert,
            query_timeout=cfg.timeout,
            health_timeout=cfg.health_timeout,
            namespace_timeout=cfg.namespace_timeout,
            startup_retry_timeout=cfg.startup_retry_timeout,
            startup_retry_interval=cfg.startup_retry_interval,
        )


if __name__ == "__main__":
    main()
