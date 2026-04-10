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

Environment variables:
  KUBE_Q_URL=http://...           # set API URL
  KUBE_Q_API_KEY=...             # set API key

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
from urllib.parse import urlparse

from kube_q.render import console, set_output_plain
from kube_q.transport import stream_query, non_stream_query
from kube_q.session import SessionState, _load_or_create_user_id, run_repl


# ── Single-query mode ─────────────────────────────────────────────────────────

def run_single_query(
    url: str,
    query: str,
    stream: bool,
    user_id: str | None = None,
    api_key: str | None = None,
    ca_cert: str | None = None,
) -> None:
    conversation_id = str(uuid.uuid4())
    if user_id is None:
        user_id = _load_or_create_user_id()
    messages = [{"role": "user", "content": query}]

    if stream:
        stream_query(url, messages, conversation_id, user_id, api_key=api_key, ca_cert=ca_cert)
    else:
        non_stream_query(url, messages, conversation_id, user_id, api_key=api_key, ca_cert=ca_cert)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="kq",
        description="kube-q — chat with your Kubernetes cluster.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--url",
        default=os.getenv("KUBE_Q_URL", "http://localhost:8000"),
        help="kube-q API base URL (env: KUBE_Q_URL, default: http://localhost:8000)",
    )
    parser.add_argument(
        "--query", "-q",
        default=None,
        help="Run a single query and exit (non-interactive mode)",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        default=False,
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
        default=os.getenv("KUBE_Q_API_KEY"),
        metavar="KEY",
        help="API key for authentication (env: KUBE_Q_API_KEY)",
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
        default="rich",
        help="Output format: 'rich' (default, markdown rendering) or 'plain' (raw text)",
    )

    args = parser.parse_args()
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
        run_single_query(args.url, args.query, stream, user_id=user_id,
                         api_key=args.api_key, ca_cert=args.ca_cert)
    else:
        run_repl(args.url, stream, args.conversation_id, user_id=user_id,
                 quiet=args.quiet, api_key=args.api_key, ca_cert=args.ca_cert)


if __name__ == "__main__":
    main()
