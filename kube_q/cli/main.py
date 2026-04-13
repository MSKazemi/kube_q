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
  kq --user-name Alice        # your display name in the prompt (default: You)
  kq --agent-name MyBot       # assistant name in saved conversations (default: kube-q)
  kq --list                   # list recent sessions and exit
  kq --search "pod crash"     # full-text search across session history and exit
  kq --session-id <id>        # resume a previous session by ID
  kq --model gpt-4o           # override model name sent in requests
  kq --no-health-check        # skip startup health check (useful for web/scripted contexts)

Environment variables:
  KUBE_Q_URL=http://...              # set API URL
  KUBE_Q_API_KEY=...                # set API key (required when server auth is enabled)
  KUBE_Q_MODEL=kubeintellect-v2     # model name sent in requests
  KUBE_Q_SKIP_HEALTH_CHECK=true     # skip startup health check

Config (~/.kube-q/.env or ./.env):
  KUBE_Q_URL=http://localhost:8000
  KUBE_Q_API_KEY=                  # required only when server auth is enabled
  KUBE_Q_MODEL=kubeintellect-v2
  KUBE_Q_TIMEOUT=120
  KUBE_Q_STREAM=true
  KUBE_Q_OUTPUT=rich               # rich | plain
  KUBE_Q_LOG_LEVEL=INFO            # DEBUG | INFO | WARNING | ERROR
  KUBE_Q_USER_NAME=You
  KUBE_Q_AGENT_NAME=kube-q
  KUBE_Q_COST_PER_1K_PROMPT=0.003      # override cost rate for /tokens
  KUBE_Q_COST_PER_1K_COMPLETION=0.006  # override cost rate for /tokens

In-REPL commands:
  /new           — start a new conversation (new conversation ID)
  /id            — show current conversation ID
  /state         — show current session state in one line
  /clear         — clear the terminal screen
  /save [file]   — save conversation to markdown file
  /ns <name>     — set active namespace (/ns with no arg clears it)
  /sessions      — list recent sessions (same as kq --list)
  /forget        — delete current session from local history
  /tokens        — show token counts and estimated cost for this session
  /cost          — alias for /tokens
  /search <q>    — full-text search across all past sessions
  /branch        — fork this conversation at the current point
  /branches      — list all forks of this session
  /title <text>  — rename the current session
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
import uuid
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from urllib.parse import urlparse

from kube_q.cli.renderer import (
    _print_sessions_table,
    console,
    format_search_results,
    set_output_plain,
)
from kube_q.cli.repl import ReplConfig, run_repl
from kube_q.cli.store import list_sessions as _list_sessions
from kube_q.cli.store import search_sessions as _search_sessions
from kube_q.core.config import load_config, setup_logging
from kube_q.core.session import load_or_create_user_id as _load_or_create_user_id
from kube_q.core.transport import set_debug
from kube_q.transport import non_stream_query, stream_query

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
    model: str = "kubeintellect-v2",
) -> None:
    conversation_id = str(uuid.uuid4())
    if user_id is None:
        user_id = _load_or_create_user_id()
    messages = [{"role": "user", "content": query}]

    if stream:
        stream_query(url, messages, conversation_id, user_id,
                     api_key=api_key, ca_cert=ca_cert, timeout=timeout, model=model)
    else:
        non_stream_query(url, messages, conversation_id, user_id,
                         api_key=api_key, ca_cert=ca_cert, timeout=timeout, model=model)


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
        default=cfg.url,
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
        "--session-id",
        default=None,
        metavar="ID",
        help="Resume a previous session by ID (loads history from local store)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        default=False,
        help="List recent sessions and exit (no server connection needed)",
    )
    parser.add_argument(
        "--search",
        default=None,
        metavar="QUERY",
        help="Full-text search across session history and exit (no server connection needed)",
    )
    parser.add_argument(
        "--user-id",
        default=None,
        metavar="ID",
        help=(
            "User ID to send with requests (persisted to ~/.kube-q/user-id). "
            "Reads from ~/.kube-q/user-id if not supplied."
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
        default=cfg.api_key,
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
        "--user-name",
        default=cfg.user_name,
        metavar="NAME",
        help=(
            "Display name for you in the prompt and saved conversations "
            "(env: KUBE_Q_USER_NAME, config: user_name, default: You)"
        ),
    )
    parser.add_argument(
        "--agent-name",
        default=cfg.agent_name,
        metavar="NAME",
        help=(
            "Display name for the assistant in saved conversations "
            "(env: KUBE_Q_AGENT_NAME, config: agent_name, default: kube-q)"
        ),
    )
    parser.add_argument(
        "--model",
        default=cfg.model,
        help=(
            "Model name to send in requests "
            "(env: KUBE_Q_MODEL, config: model, default: kubeintellect-v2)"
        ),
    )
    parser.add_argument(
        "--no-health-check",
        dest="skip_health_check",
        action="store_true",
        default=cfg.skip_health_check,
        help=(
            "Skip the startup health check and retry loop — go straight to the prompt. "
            "(env: KUBE_Q_SKIP_HEALTH_CHECK)"
        ),
    )
    parser.add_argument(
        "--debug", "--verbose",
        dest="debug",
        action="store_true",
        default=False,
        help=(
            "Enable debug mode: log raw HTTP requests/responses to stderr "
            "and ~/.kube-q/kube-q.log"
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

    if args.list:
        _print_sessions_table(_list_sessions(20))
        return

    if args.search:
        results = _search_sessions(args.search, limit=20)
        if results:
            format_search_results(results)
        else:
            console.print(f"[dim]No sessions matched '{args.search}'.[/dim]")
        return

    if args.query:
        run_single_query(
            args.url, args.query, stream,
            user_id=user_id, api_key=args.api_key, ca_cert=args.ca_cert,
            timeout=cfg.timeout, model=args.model,
        )
    else:
        run_repl(ReplConfig(
            url=args.url,
            stream=stream,
            initial_conversation_id=args.conversation_id,
            initial_session_id=args.session_id,
            user_id=user_id,
            quiet=args.quiet,
            api_key=args.api_key,
            ca_cert=args.ca_cert,
            query_timeout=cfg.timeout,
            health_timeout=cfg.health_timeout,
            namespace_timeout=cfg.namespace_timeout,
            startup_retry_timeout=cfg.startup_retry_timeout,
            startup_retry_interval=cfg.startup_retry_interval,
            skip_health_check=args.skip_health_check,
            user_name=args.user_name,
            agent_name=args.agent_name,
            model=args.model,
            cost_prompt_override=cfg.cost_per_1k_prompt,
            cost_completion_override=cfg.cost_per_1k_completion,
        ))


if __name__ == "__main__":
    main()
