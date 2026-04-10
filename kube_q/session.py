"""
cli_session.py — SessionState dataclass, REPL loop, slash command dispatch.
"""

import datetime
import difflib
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

from kube_q.render import console, _print_logo, _fmt_help, print_response
from kube_q.transport import stream_query, non_stream_query, check_health


# ── Prompt session config ─────────────────────────────────────────────────────

_SLASH_COMMANDS = [
    "/new", "/id", "/state", "/clear", "/save", "/approve", "/deny",
    "/help", "/ns", "/quit", "/exit", "/q",
]
_HISTORY_FILE = os.path.expanduser("~/.kube_q_history")


def _make_prompt_session() -> PromptSession:
    """Return a PromptSession with chat-style key bindings.

    Enter           = send message  (like Slack / ChatGPT).
    Alt+Enter       = insert newline (hold Alt, press Enter).
    Esc → Enter     = insert newline (universal fallback: press Esc, release, press Enter).
    Paste           = multi-line paste always preserved regardless of newlines.
    """
    kb = KeyBindings()

    @kb.add("enter")  # Enter → send
    def _enter_sends(event):
        event.current_buffer.validate_and_handle()

    @kb.add("escape", "enter")  # Alt+Enter / Esc+Enter → newline
    def _alt_enter_newline(event):
        event.current_buffer.insert_text("\n")

    completer = WordCompleter(_SLASH_COMMANDS, sentence=True)
    return PromptSession(
        history=FileHistory(_HISTORY_FILE),
        completer=completer,
        complete_while_typing=False,
        multiline=True,
        key_bindings=kb,
    )


# ── File attachment (@filename resolution) ───────────────────────────────────

_ATTACH_RE = re.compile(r'@((?:"[^"]*"|\'[^\']*\'|\S+))')
_MAX_ATTACH_BYTES = 100 * 1024  # 100 KB

_EXT_LANG: dict[str, str] = {
    ".yaml": "yaml",  ".yml": "yaml",
    ".json": "json",
    ".py":   "python",
    ".sh":   "bash",  ".bash": "bash", ".zsh": "bash",
    ".toml": "toml",
    ".go":   "go",
    ".js":   "javascript",  ".ts": "typescript",
    ".rs":   "rust",
    ".java": "java",
    ".xml":  "xml",
    ".html": "html",  ".htm": "html",
    ".tf":   "hcl",
    ".md":   "markdown",
    ".txt":  "",  ".log": "",  ".env": "",
}


def _resolve_attachments(text: str) -> tuple[str, list[str], list[str]]:
    """Replace @filename tokens with their file contents as fenced code blocks.

    Supports bare paths (@file.yaml) and quoted paths (@"my file.yaml").
    Returns (expanded_text, attached_summaries, error_messages).
    """
    attached: list[str] = []
    errors: list[str] = []

    def _expand(match: re.Match) -> str:
        raw = match.group(1).strip("\"'")
        path = Path(raw).expanduser().resolve()

        if not path.exists():
            errors.append(f"[red]@{raw}:[/red] file not found")
            return match.group(0)
        if not path.is_file():
            errors.append(f"[red]@{raw}:[/red] not a regular file")
            return match.group(0)

        size = path.stat().st_size
        if size > _MAX_ATTACH_BYTES:
            errors.append(
                f"[red]@{raw}:[/red] file too large "
                f"({size // 1024} KB — limit is {_MAX_ATTACH_BYTES // 1024} KB)"
            )
            return match.group(0)

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            errors.append(f"[red]@{raw}:[/red] could not read: {e}")
            return match.group(0)

        lang = _EXT_LANG.get(path.suffix.lower(), "")
        attached.append(f"{path.name} ({size / 1024:.1f} KB)")
        return f"\n```{lang}\n# {path.name}\n{content.rstrip()}\n```\n"

    expanded = _ATTACH_RE.sub(_expand, text)
    return expanded, attached, errors


# ── User-ID persistence ───────────────────────────────────────────────────────

_USER_ID_FILE = os.path.expanduser("~/.kube_q_id")


def _load_or_create_user_id(explicit: str | None = None) -> str:
    """Return user_id: --user-id arg > persisted ~/.kube_q_id > generate+save new."""
    if explicit:
        with open(_USER_ID_FILE, "w") as f:
            f.write(explicit)
        os.chmod(_USER_ID_FILE, 0o600)
        return explicit
    if os.path.exists(_USER_ID_FILE):
        with open(_USER_ID_FILE) as f:
            uid = f.read().strip()
        if uid:
            return uid
    uid = f"cli-user-{str(uuid.uuid4())[:8]}"
    with open(_USER_ID_FILE, "w") as f:
        f.write(uid)
    os.chmod(_USER_ID_FILE, 0o600)
    return uid


# ── Session state ─────────────────────────────────────────────────────────────

@dataclass
class SessionState:
    """Holds all mutable state for one interactive session or demo run."""
    conversation_id: str
    user_id: str
    messages: list[dict] = field(default_factory=list)
    hitl_pending: bool = False
    pending_action_id: str | None = None
    current_namespace: str | None = None


# ── Conversation persistence ──────────────────────────────────────────────────

def _save_conversation(messages: list[dict], path: str | None) -> None:
    """Write the conversation to a markdown file."""
    if not path:
        ts = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        path = f"kube-q-{ts}.md"
    lines = [f"# kube-q Conversation\n\n*Saved: {datetime.datetime.now().isoformat()}*\n"]
    for msg in messages:
        role = "**You**" if msg["role"] == "user" else "**kube-q**"
        lines.append(f"\n{role}:\n\n{msg['content']}\n\n---")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    console.print(f"[dim]Conversation saved to[/dim] {path}")


# ── REPL ──────────────────────────────────────────────────────────────────────

def run_repl(
    url: str,
    stream: bool,
    initial_conversation_id: str | None = None,
    show_header: bool = True,
    initial_messages: list[dict] | None = None,
    user_id: str | None = None,
    quiet: bool = False,
    api_key: str | None = None,
    ca_cert: str | None = None,
    query_timeout: float = 120.0,
    health_timeout: float = 5.0,
    namespace_timeout: float = 3.0,
    startup_retry_timeout: int = 300,
    startup_retry_interval: int = 5,
) -> None:
    state = SessionState(
        conversation_id=initial_conversation_id or str(uuid.uuid4()),
        user_id=user_id or _load_or_create_user_id(),
        messages=list(initial_messages) if initial_messages else [],
    )
    _prepend_ns_once = False
    _pending_retry: str = ""  # pre-fills next prompt after a failed send

    if show_header and not quiet:
        connected, reason = check_health(url, api_key=api_key, ca_cert=ca_cert, timeout=health_timeout)

        if not connected:
            deadline = time.monotonic() + startup_retry_timeout

            console.print(f"[yellow]Cannot reach {url}/healthz[/yellow]")
            console.print(f"[dim]  Reason: {reason}[/dim]")
            console.print(f"[dim]  Retrying every {startup_retry_interval}s for up to {startup_retry_timeout // 60} min…[/dim]\n")

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

                    connected, reason = check_health(url, api_key=api_key, ca_cert=ca_cert, timeout=health_timeout)
            except KeyboardInterrupt:
                console.print("\n[dim]Startup wait cancelled — continuing without API connection.[/dim]\n")
                connected = False
                reason = "Cancelled by user"

            if connected:
                console.print(f"[green]Connected to {url}[/green]\n")
            else:
                console.print(
                    f"[red]Still cannot reach {url}/healthz.[/red]"
                )
                console.print(f"[dim]  Last reason: {reason}[/dim]")
                console.print("[dim]  Continuing anyway — queries will fail until the API is up.[/dim]\n")

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
            prompt = FormattedText([("bold fg:ansigreen", f"You [{state.current_namespace}]: ")])
        else:
            prompt = FormattedText([("bold fg:ansigreen", "You: ")])

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
            cleared_note = f"  [dim]({cleared} message{'s' if cleared != 1 else ''} cleared)[/dim]" if cleared else ""
            console.print(f"[dim]New conversation started:[/dim] {state.conversation_id}{cleared_note}")
            continue

        if user_input.lower() == "/id":
            console.print(f"[dim]Conversation ID:[/dim] {state.conversation_id}")
            continue

        if user_input.lower() == "/state":
            ns_line = f"  [dim]Namespace    [/dim] {state.current_namespace}" if state.current_namespace else f"  [dim]Namespace    [/dim] [dim italic](none)[/dim]"
            hitl_line = f"  [dim]HITL pending [/dim] [bold yellow]yes — action_id={state.pending_action_id}[/bold yellow]" if state.hitl_pending else f"  [dim]HITL pending [/dim] no"
            console.print(Panel(
                f"  [dim]Conversation [/dim] {state.conversation_id}\n"
                f"  [dim]User ID      [/dim] {state.user_id}\n"
                f"  [dim]Messages     [/dim] {len(state.messages)}\n"
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
            _save_conversation(state.messages, save_path)
            continue

        if user_input.lower().startswith("/ns"):
            parts = user_input.split(maxsplit=1)
            ns_arg = parts[1].strip() if len(parts) > 1 else ""
            if not ns_arg:
                state.current_namespace = None
                _prepend_ns_once = False
                console.print("[dim]Namespace cleared.[/dim]")
            else:
                try:
                    _ns_headers: dict[str, str] = {"X-User-ID": state.user_id}
                    if api_key:
                        _ns_headers["Authorization"] = f"Bearer {api_key}"
                    with httpx.Client(timeout=namespace_timeout) as _hc:
                        _r = _hc.get(f"{url}/v1/namespaces/{ns_arg}", headers=_ns_headers)
                    if _r.status_code not in (200, 204):
                        console.print(
                            f"[yellow]Warning: namespace '{ns_arg}' not found — set anyway?[/yellow] "
                            "(namespace set regardless)"
                        )
                except Exception:
                    pass
                state.current_namespace = ns_arg
                _prepend_ns_once = True
                console.print(f"[dim]Active namespace set to[/dim] [bold]{ns_arg}[/bold]")
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

        if stream:
            response_text, state.hitl_pending, action_id = stream_query(
                url, state.messages, state.conversation_id, state.user_id,
                pending_action_id=state.pending_action_id,
                api_key=api_key, ca_cert=ca_cert, timeout=query_timeout,
            )
        else:
            response_text, state.hitl_pending, action_id = non_stream_query(
                url, state.messages, state.conversation_id, state.user_id,
                pending_action_id=state.pending_action_id,
                api_key=api_key, ca_cert=ca_cert, timeout=query_timeout,
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

        if state.hitl_pending:
            console.print(Panel(
                "[bold yellow]Action requires approval.[/bold yellow]\n"
                "Type [yellow]/approve[/yellow] to proceed or [yellow]/deny[/yellow] to cancel.",
                border_style="yellow",
                expand=False,
            ))
