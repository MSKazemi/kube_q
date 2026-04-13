"""
repl.py — prompt_toolkit REPL loop and slash command dispatch for the kube_q CLI.
"""

import datetime
import difflib
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

from kube_q import costs, store
from kube_q.cli.renderer import (
    _fmt_help,
    _print_logo,
    _print_sessions_table,
    _print_token_panel,
    console,
    format_branches,
    format_search_results,
)
from kube_q.core.config import CONFIG_DIR
from kube_q.core.session import (
    SessionState,
)
from kube_q.core.session import (
    load_or_create_user_id as _load_or_create_user_id,
)
from kube_q.core.session import (
    resolve_attachments as _resolve_attachments,
)
from kube_q.core.transport import fetch_namespaces
from kube_q.transport import check_health, non_stream_query, stream_query

# ── REPL configuration dataclass ─────────────────────────────────────────────

@dataclass
class ReplConfig:
    """All configuration for a single run_repl() invocation."""
    url: str = "http://localhost:8000"
    stream: bool = True
    initial_conversation_id: str | None = None
    initial_session_id: str | None = None
    show_header: bool = True
    initial_messages: list[dict] = field(default_factory=list)
    user_id: str | None = None
    quiet: bool = False
    api_key: str | None = None
    ca_cert: str | None = None
    query_timeout: float = 120.0
    health_timeout: float = 5.0
    namespace_timeout: float = 3.0
    startup_retry_timeout: int = 300
    startup_retry_interval: int = 5
    skip_health_check: bool = False
    user_name: str = "You"
    agent_name: str = "kube-q"
    model: str = "kubeintellect-v2"
    cost_prompt_override: float | None = None
    cost_completion_override: float | None = None


# ── Prompt session config ─────────────────────────────────────────────────────

_SLASH_COMMANDS = [
    "/new", "/id", "/state", "/clear", "/save", "/approve", "/deny",
    "/help", "/ns", "/sessions", "/forget", "/tokens", "/cost",
    "/search", "/branch", "/branches", "/title",
    "/quit", "/exit", "/q",
]
_HISTORY_FILE = str(CONFIG_DIR / "history")


def _make_prompt_session() -> PromptSession:
    """Return a PromptSession with chat-style key bindings.

    Enter           = send message  (like Slack / ChatGPT).
    Alt+Enter       = insert newline (hold Alt, press Enter).
    Esc → Enter     = insert newline (universal fallback: press Esc, release, press Enter).
    Paste           = multi-line paste always preserved regardless of newlines.
    """
    kb = KeyBindings()

    @kb.add("enter")  # Enter → send
    def _enter_sends(event: Any) -> None:
        event.current_buffer.validate_and_handle()

    @kb.add("escape", "enter")  # Alt+Enter / Esc+Enter → newline
    def _alt_enter_newline(event: Any) -> None:
        event.current_buffer.insert_text("\n")

    completer = WordCompleter(_SLASH_COMMANDS, sentence=True)
    return PromptSession(
        history=FileHistory(_HISTORY_FILE),
        completer=completer,
        complete_while_typing=False,
        multiline=True,
        key_bindings=kb,
    )


# ── Conversation persistence ──────────────────────────────────────────────────

def _save_conversation(
    messages: list[dict],
    path: str | None,
    user_name: str = "You",
    agent_name: str = "kube-q",
) -> None:
    """Write the conversation to a markdown file."""
    if not path:
        ts = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        path = f"kube-q-{ts}.md"
    lines = [f"# kube-q Conversation\n\n*Saved: {datetime.datetime.now().isoformat()}*\n"]
    for msg in messages:
        role = f"**{user_name}**" if msg["role"] == "user" else f"**{agent_name}**"
        lines.append(f"\n{role}:\n\n{msg['content']}\n\n---")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    console.print(f"[dim]Conversation saved to[/dim] {path}")


# ── REPL ──────────────────────────────────────────────────────────────────────

def run_repl(cfg: ReplConfig) -> None:
    """Run the interactive REPL loop using the provided configuration."""
    url = cfg.url
    stream = cfg.stream
    initial_conversation_id = cfg.initial_conversation_id
    initial_session_id = cfg.initial_session_id
    show_header = cfg.show_header
    initial_messages = cfg.initial_messages
    user_id = cfg.user_id
    quiet = cfg.quiet
    api_key = cfg.api_key
    ca_cert = cfg.ca_cert
    query_timeout = cfg.query_timeout
    health_timeout = cfg.health_timeout
    namespace_timeout = cfg.namespace_timeout
    startup_retry_timeout = cfg.startup_retry_timeout
    startup_retry_interval = cfg.startup_retry_interval
    skip_health_check = cfg.skip_health_check
    user_name = cfg.user_name
    agent_name = cfg.agent_name
    model = cfg.model
    cost_prompt_override = cfg.cost_prompt_override
    cost_completion_override = cfg.cost_completion_override

    # initial_session_id takes precedence over initial_conversation_id
    effective_id = initial_session_id or initial_conversation_id
    resolved_user_id = user_id or _load_or_create_user_id()

    state = SessionState(
        conversation_id=effective_id or str(uuid.uuid4()),
        user_id=resolved_user_id,
        messages=list(initial_messages) if initial_messages else [],
    )

    # Hydrate from store when resuming a named session
    if initial_session_id and not initial_messages:
        stored = store.load_messages(initial_session_id)
        if stored:
            state.messages = stored
            console.print(f"[dim]Resumed {len(stored)} messages.[/dim]")
    _prepend_ns_once = False
    _pending_retry: str = ""  # pre-fills next prompt after a failed send

    if show_header and not quiet:
        if skip_health_check:
            connected = True
            reason = ""
        else:
            connected, reason = check_health(
                url, api_key=api_key, ca_cert=ca_cert, timeout=health_timeout
            )

        if not connected:
            deadline = time.monotonic() + startup_retry_timeout

            console.print(f"[yellow]Cannot reach {url}/healthz[/yellow]")
            console.print(f"[dim]  Reason: {reason}[/dim]")
            console.print(
                f"[dim]  Retrying every {startup_retry_interval}s "
                f"for up to {startup_retry_timeout // 60} min…[/dim]\n"
            )

            attempt = 0
            try:
                while not connected and time.monotonic() < deadline:
                    remaining = int(deadline - time.monotonic())
                    attempt += 1
                    status_text = Text.assemble(
                        (" Waiting for API… ", "cyan"),
                        (f"attempt {attempt}", "dim"),
                        (f"  ({remaining}s remaining)", "dim"),
                    )
                    with Live(
                        Spinner("dots", text=status_text),
                        console=console,
                        refresh_per_second=4,
                        transient=True,
                    ):
                        time.sleep(min(startup_retry_interval, max(0, remaining)))

                    connected, reason = check_health(
                        url, api_key=api_key, ca_cert=ca_cert, timeout=health_timeout
                    )
            except KeyboardInterrupt:
                console.print(
                    "\n[dim]Startup wait cancelled — continuing without API connection.[/dim]\n"
                )
                connected = False
                reason = "Cancelled by user"

            if connected:
                console.print(f"[green]Connected to {url}[/green]\n")
            else:
                console.print(
                    f"[red]Still cannot reach {url}/healthz.[/red]"
                )
                console.print(f"[dim]  Last reason: {reason}[/dim]")
                console.print(
                    "[dim]  Continuing anyway — queries will fail until the API is up.[/dim]\n"
                )

        _print_logo(connected=connected)
        console.print(Panel.fit(
            f"[dim]API:[/dim] {url}   "
            f"[dim]Conversation:[/dim] {state.conversation_id}\n"
            f"[dim]Type [yellow]/help[/yellow] for commands · "
            f"[yellow]Enter[/yellow] to send · "
            f"[yellow]Alt+Enter[/yellow] for newline[/dim]",
            border_style="dim cyan",
        ))
        console.print()

    pt_session = _make_prompt_session()

    while True:
        if state.hitl_pending:
            prompt = FormattedText([("bold fg:ansiyellow", "HITL> ")])
        elif state.current_namespace:
            prompt = FormattedText(
                [("bold fg:ansigreen", f"{user_name} [{state.current_namespace}]: ")]
            )
        else:
            prompt = FormattedText([("bold fg:ansigreen", f"{user_name}: ")])

        try:
            user_input = pt_session.prompt(prompt, default=_pending_retry).strip()
            _pending_retry = ""
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/quit", "/exit", "/q"):
            console.print("[dim]Goodbye.[/dim]")
            break

        if user_input.lower() == "/help":
            _fmt_help()
            continue

        if user_input.lower() == "/new":
            cleared = len(state.messages)
            state.conversation_id = str(uuid.uuid4())
            state.messages = []
            state.hitl_pending = False
            state.pending_action_id = None
            s = "s" if cleared != 1 else ""
            cleared_note = f"  [dim]({cleared} message{s} cleared)[/dim]" if cleared else ""
            console.print(
                f"[dim]New conversation started:[/dim] {state.conversation_id}{cleared_note}"
            )
            continue

        if user_input.lower() == "/id":
            console.print(f"[dim]Conversation ID:[/dim] {state.conversation_id}")
            continue

        if user_input.lower() == "/state":
            ns = state.current_namespace
            ns_line = (
                f"  [dim]Namespace    [/dim] {ns}"
                if ns
                else "  [dim]Namespace    [/dim] [dim italic](none)[/dim italic]"
            )
            hitl_line = (
                f"  [dim]HITL pending [/dim] [bold yellow]yes — action_id={state.pending_action_id}[/bold yellow]"  # noqa: E501
                if state.hitl_pending
                else "  [dim]HITL pending [/dim] no"
            )
            tok = store.get_session_tokens(state.conversation_id)
            last_u = store.get_last_usage(state.conversation_id)
            last_model = last_u.get("model") if last_u else None
            cost = costs.estimate_cost(
                last_model,
                tok["total_prompt_tokens"],
                tok["total_completion_tokens"],
                cost_prompt_override,
                cost_completion_override,
            )
            cost_part = f" (~{costs.format_cost(cost)})" if tok["total_tokens"] else ""
            tokens_line = f"  [dim]Tokens       [/dim] {tok['total_tokens']:,}{cost_part}"
            console.print(Panel(
                f"  [dim]Conversation [/dim] {state.conversation_id}\n"
                f"  [dim]User ID      [/dim] {state.user_id}\n"
                f"  [dim]Messages     [/dim] {len(state.messages)}\n"
                f"{tokens_line}\n"
                f"{ns_line}\n"
                f"{hitl_line}",
                title="[bold cyan]Session State[/bold cyan]",
                border_style="dim cyan",
                expand=False,
                padding=(0, 1),
            ))
            continue

        if user_input.lower() == "/clear":
            os.system("clear")
            continue

        if user_input.lower().startswith("/save"):
            parts = user_input.split(maxsplit=1)
            save_path = parts[1] if len(parts) > 1 else None
            if state.messages:
                console.print(
                    "[dim yellow]Note: conversations may contain sensitive cluster data "
                    "— save to a secure location.[/dim yellow]"
                )
            _save_conversation(
                state.messages, save_path, user_name=user_name, agent_name=agent_name
            )
            continue

        if user_input.lower().startswith("/ns"):
            parts = user_input.split(maxsplit=1)
            ns_arg = parts[1].strip() if len(parts) > 1 else ""
            if not ns_arg:
                state.current_namespace = None
                _prepend_ns_once = False
                console.print("[dim]Namespace cleared.[/dim]")
            else:
                # Validate against the cluster namespace list from the backend.
                _known = fetch_namespaces(
                    url, state.user_id, api_key=api_key,
                    ca_cert=ca_cert, timeout=namespace_timeout
                )
                _ns_valid: bool | None = (
                    ns_arg in _known if _known is not None else None
                )

                if _ns_valid is False:
                    console.print(
                        f"[red]Namespace '{ns_arg}' not found in the cluster.[/red] "
                        "Use [bold]list all ns[/bold] to see available namespaces."
                    )
                else:
                    state.current_namespace = ns_arg
                    _prepend_ns_once = True
                    console.print(f"[dim]Active namespace set to[/dim] [bold]{ns_arg}[/bold]")
            continue

        if user_input.lower() == "/sessions":
            _print_sessions_table(store.list_sessions(20))
            continue

        if user_input.lower() == "/forget":
            console.print(
                f"[yellow]This will delete session [bold]{state.conversation_id}[/bold] "
                "from local history (server-side data is not affected).[/yellow]"
            )
            try:
                confirm = pt_session.prompt(
                    FormattedText([("bold fg:ansiyellow", "Delete? [y/N] ")])
                ).strip().lower()
            except (EOFError, KeyboardInterrupt):
                confirm = ""
            if confirm == "y":
                store.delete_session(state.conversation_id)
                new_id = str(uuid.uuid4())
                state.conversation_id = new_id
                state.messages = []
                state.hitl_pending = False
                state.pending_action_id = None
                console.print(f"[dim]Session deleted. New session started:[/dim] {new_id}")
            else:
                console.print("[dim]Cancelled.[/dim]")
            continue

        if user_input.lower() in ("/tokens", "/cost"):
            _print_token_panel(
                state.conversation_id, cost_prompt_override, cost_completion_override
            )
            continue

        if user_input.lower().startswith("/search"):
            parts = user_input.split(maxsplit=1)
            query = parts[1].strip() if len(parts) > 1 else ""
            if not query:
                console.print("[yellow]Usage: /search <query>[/yellow]")
            else:
                results = store.search_sessions(query)
                if results:
                    format_search_results(results)
                else:
                    console.print(f"[dim]No sessions matched '{query}'.[/dim]")
            continue

        if user_input.lower() == "/branch":
            new_id = str(uuid.uuid4())
            n = len(state.messages)
            store.branch_session(state.conversation_id, new_id, n)
            state.conversation_id = new_id
            console.print(f"[dim]Branched at message {n}. New session:[/dim] {new_id}")
            console.print("[dim]Original session preserved. Use /sessions to see both.[/dim]")
            continue

        if user_input.lower() == "/branches":
            branches = store.list_branches(state.conversation_id)
            format_branches(branches, state.conversation_id)
            continue

        if user_input.lower().startswith("/title"):
            parts = user_input.split(maxsplit=1)
            new_title = parts[1].strip() if len(parts) > 1 else ""
            if not new_title:
                console.print("[yellow]Usage: /title <text>[/yellow]")
            else:
                store.rename_session(state.conversation_id, new_title)
                console.print(f"[dim]Session title set to '{new_title}'[/dim]")
            continue

        if user_input.lower() == "/approve":
            user_input = "approve"
            state.hitl_pending = False

        elif user_input.lower() == "/deny":
            user_input = "deny"
            state.hitl_pending = False

        # Catch typos in unknown slash commands
        elif user_input.startswith("/"):
            cmd = user_input.split()[0].lower()
            suggestions = difflib.get_close_matches(cmd, _SLASH_COMMANDS, n=1, cutoff=0.6)
            if suggestions:
                console.print(
                    f"[yellow]Unknown command.[/yellow] "
                    f"Did you mean [bold]{suggestions[0]}[/bold]?"
                )
            else:
                console.print(
                    f"[yellow]Unknown command [bold]{cmd}[/bold]. "
                    f"Type [bold]/help[/bold] for available commands.[/yellow]"
                )
            continue

        # Save original (pre-expansion) input for retry pre-fill
        original_input = user_input

        # Resolve @filename attachments
        user_input, attached, attach_errors = _resolve_attachments(user_input)
        for err in attach_errors:
            console.print(err)
        if attached:
            console.print(f"[dim]Attached: {', '.join(attached)}[/dim]")

        if _prepend_ns_once and state.current_namespace:
            user_input = f"[context: namespace={state.current_namespace}] {user_input}"
            _prepend_ns_once = False
        state.messages.append({"role": "user", "content": user_input})

        request_id = f"req-{uuid.uuid4()}"
        state.last_request_id = request_id

        if stream:
            response_text, state.hitl_pending, action_id, usage = stream_query(
                url, state.messages, state.conversation_id, state.user_id,
                api_key=api_key, ca_cert=ca_cert, timeout=query_timeout,
                request_id=request_id, model=model,
            )
        else:
            response_text, state.hitl_pending, action_id, usage = non_stream_query(
                url, state.messages, state.conversation_id, state.user_id,
                api_key=api_key, ca_cert=ca_cert, timeout=query_timeout,
                request_id=request_id, model=model,
            )

        if not response_text:
            state.messages.pop()
            _pending_retry = original_input
            console.print(
                "[dim]  Request failed — your message is ready to resend. "
                "Press Enter or edit before sending.[/dim]"
            )
            continue

        if state.hitl_pending and action_id:
            state.pending_action_id = action_id
        elif not state.hitl_pending:
            state.pending_action_id = None

        state.messages.append({"role": "assistant", "content": response_text})

        # ── Persist to local store (best-effort) ──────────────────────────────
        store.upsert_session(state.conversation_id, state.user_id, state.current_namespace)
        store.append_message(state.conversation_id, "user", user_input, request_id)
        store.append_message(state.conversation_id, "assistant", response_text, request_id)
        if len(state.messages) == 2:  # first exchange
            store.set_session_title(state.conversation_id, user_input[:60])
        if usage:
            store.log_tokens(
                state.conversation_id,
                state.last_request_id,
                usage.get("model"),
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
            )

        if state.hitl_pending:
            console.print(Panel(
                "[bold yellow]Action requires approval.[/bold yellow]\n"
                "Type [yellow]/approve[/yellow] to proceed or [yellow]/deny[/yellow] to cancel.",
                border_style="yellow",
                expand=False,
            ))
