"""
cli_render.py — Display utilities: Rich console, ANSI helpers, logo, markdown rendering.
"""

import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

# ── Rich console ──────────────────────────────────────────────────────────────

console = Console(highlight=False)

# ── ANSI colour helpers (used for input() prompts only) ──────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"


def c(text: str, *codes: str) -> str:
    """Wrap text in ANSI escape codes (no-op if stdout is not a TTY)."""
    if not sys.stdout.isatty():
        return text
    return "".join(codes) + text + RESET


# ── Logo ──────────────────────────────────────────────────────────────────────

_LOGO_ART = (
    "\033[1;36m  _          _               \033[0m\n"
    "\033[1;36m | | ___   _| |__   ___      \033[0m\n"
    "\033[1;36m | |/ / | | | '_ \\ / _ \\  ─ q\033[0m\n"
    "\033[1;36m |   <| |_| | |_) |  __/    \033[0m\n"
    "\033[1;36m |_|\\_\\\\__,_|_.__/ \\___|    \033[0m\n"
    "\033[2m   Your AI co-pilot for Kubernetes.\033[0m"
)


def _print_logo(connected: bool = True) -> None:
    if sys.stdout.isatty():
        art = _LOGO_ART if connected else _LOGO_ART.replace("\033[1;36m", "\033[1;31m")
        print()
        print(art)
        print()


# ── Output format ─────────────────────────────────────────────────────────────

_plain_output: bool = False


def set_output_plain(plain: bool) -> None:
    """Switch between rich markdown rendering (default) and plain text output."""
    global _plain_output
    _plain_output = plain


# ── Response rendering ────────────────────────────────────────────────────────

# Maximum number of lines before auto-paging, regardless of actual terminal height.
_PAGER_LINE_THRESHOLD = 40


def _should_use_pager(text: str) -> bool:
    if not sys.stdout.isatty():
        return False
    terminal_height = console.height or 24
    threshold = max(min(terminal_height - 4, _PAGER_LINE_THRESHOLD), 10)
    return text.count("\n") > threshold


def print_response(text: str) -> None:
    """Render assistant response, paging long output. Respects --output plain."""
    if _plain_output:
        print(text)
        return
    md = Markdown(text)
    if _should_use_pager(text):
        with console.pager(styles=False):
            console.print(md)
    else:
        console.print()
        console.print(md)
        console.print()


# ── Help panel ────────────────────────────────────────────────────────────────

def format_search_results(results: list[dict]) -> None:
    """Print a Rich table of FTS5 search results.

    Columns: Session (8-char), Title, Updated, Msgs, Match.
    >>> <<< markers in snippets are rendered as bold-yellow Rich markup.
    """
    from rich.table import Table

    if not results:
        console.print("[dim]No results found.[/dim]")
        return

    table = Table(
        "Session", "Title", "Updated", "Msgs", "Match",
        title="[bold cyan]Search Results[/bold cyan]",
        border_style="dim cyan",
        show_lines=True,
    )
    for r in results:
        snippet = r.get("snippet") or ""
        # Replace FTS5 markers with Rich markup
        snippet = snippet.replace(">>>", "[bold yellow]").replace("<<<", "[/bold yellow]")
        title = r.get("title") or "[dim](untitled)[/dim]"
        updated = (r.get("updated_at") or "")[:16].replace("T", " ")
        table.add_row(
            (r.get("session_id") or "")[:8],
            title,
            updated,
            str(r.get("message_count", 0)),
            snippet,
        )
    console.print(table)


def format_branches(branches: list[dict], current_id: str) -> None:
    """Print a Rich table of branched sessions.

    Columns: Session (8-char), Title, Branched at, Msgs, Updated.
    The current session row is prefixed with a → marker.
    """
    from rich.table import Table

    if not branches:
        console.print("[dim]No branches of this session.[/dim]")
        return

    table = Table(
        "", "Session", "Title", "Branched at", "Msgs", "Updated",
        title="[bold cyan]Branches[/bold cyan]",
        border_style="dim cyan",
        show_lines=False,
    )
    for b in branches:
        marker = "[bold cyan]→[/bold cyan]" if b["session_id"] == current_id else ""
        title = b.get("title") or "[dim](untitled)[/dim]"
        updated = (b.get("updated_at") or "")[:16].replace("T", " ")
        bp = str(b.get("branch_point") or "—")
        table.add_row(
            marker,
            (b.get("session_id") or "")[:8],
            title,
            bp,
            str(b.get("message_count", 0)),
            updated,
        )
    console.print(table)


def _fmt_help() -> None:
    console.print(Panel(
        # ── Sending messages ──────────────────────────────────────────────────
        "[bold cyan]Sending messages[/bold cyan]\n\n"
        "  [yellow]Enter[/yellow]              Send your message\n"
        "  [yellow]Alt+Enter[/yellow]          Insert a newline  [dim](hold Alt, press Enter)[/dim]\n"  # noqa: E501
        "  [yellow]Esc  →  Enter[/yellow]      Insert a newline  [dim](press Esc, release, then Enter — works everywhere)[/dim]\n"  # noqa: E501
        "  Paste multi-line text freely — all newlines are preserved before you send\n\n"

        # ── File attachments ──────────────────────────────────────────────────
        "[bold cyan]Attaching files[/bold cyan]\n\n"
        "  Type [yellow]@path/to/file[/yellow] anywhere in your message to attach a file.\n"
        "  Its contents are embedded as a code block and sent with your message.\n\n"
        "  [yellow]@deployment.yaml[/yellow]           Attach a file in the current directory\n"
        "  [yellow]@~/configs/service.json[/yellow]    Attach using a home-relative path\n"
        "  [yellow]@\"/path/with spaces/file.txt\"[/yellow]   Quote paths that contain spaces\n\n"
        "  You can attach multiple files in a single message:\n"
        "  [dim]What's wrong here? @pod.yaml @service.yaml[/dim]\n\n"
        "  Supported types: YAML, JSON, Python, Shell, Go, Terraform, text, logs, and more.\n"
        "  File size limit: 100 KB per file.\n\n"

        # ── Editing shortcuts ─────────────────────────────────────────────────
        "[bold cyan]Editing[/bold cyan]\n\n"
        "  [yellow]Tab[/yellow]                Auto-complete slash commands\n"
        "  [yellow]↑ / ↓[/yellow]             Scroll through previous messages  [dim](history)[/dim]\n"  # noqa: E501
        "  [yellow]Ctrl+A[/yellow]             Jump to start of line\n"
        "  [yellow]Ctrl+E[/yellow]             Jump to end of line\n"
        "  [yellow]Ctrl+W[/yellow]             Delete previous word\n"
        "  [yellow]Ctrl+U[/yellow]             Clear entire input buffer\n"
        "  [yellow]Ctrl+C[/yellow]             Cancel current input (keeps history)\n"
        "  [yellow]Ctrl+D[/yellow]             Exit the session\n\n"

        # ── Conversation commands ─────────────────────────────────────────────
        "[bold cyan]Conversation commands[/bold cyan]\n\n"
        "  [yellow]/new[/yellow]               Start a fresh conversation  [dim](new ID, clears history)[/dim]\n"  # noqa: E501
        "  [yellow]/id[/yellow]                Show the current conversation ID\n"
        "  [yellow]/state[/yellow]             Show full session state  [dim](ID, namespace, HITL flag)[/dim]\n"  # noqa: E501
        "  [yellow]/save[/yellow]              Save conversation to [dim]kube-q-TIMESTAMP.md[/dim]\n"  # noqa: E501
        "  [yellow]/save <file>[/yellow]        Save conversation to a specific file\n\n"

        # ── Namespace ─────────────────────────────────────────────────────────
        "[bold cyan]Namespace[/bold cyan]\n\n"
        "  [yellow]/ns <name>[/yellow]          Set active namespace — prepended to every query\n"
        "  [yellow]/ns[/yellow]                 Clear active namespace\n\n"

        # ── Session history ───────────────────────────────────────────────────
        "[bold cyan]Session history[/bold cyan]\n\n"
        "  [yellow]/sessions[/yellow]           List recent sessions  "
        "[dim](same as kq --list)[/dim]\n"
        "  [yellow]/forget[/yellow]             Delete current session from local history  "
        "[dim](server data untouched)[/dim]\n\n"

        # ── History & branching ───────────────────────────────────────────────
        "[bold cyan]History & branching[/bold cyan]\n\n"
        "  [yellow]/search <query>[/yellow]     Full-text search across all past sessions\n"
        "  [yellow]/branch[/yellow]             Fork this conversation at the current point\n"
        "  [yellow]/branches[/yellow]           List all forks of (and siblings of) this session\n"
        "  [yellow]/title <text>[/yellow]       Rename the current session\n"
        "  FTS5 boolean syntax supported: [dim]/search pods AND NOT staging[/dim]\n"
        "  [dim]kq --search \"query\"[/dim]    Same as /search, but from the shell\n\n"

        # ── Token usage ───────────────────────────────────────────────────────
        "[bold cyan]Token usage[/bold cyan]\n\n"
        "  [yellow]/tokens[/yellow]             Show token counts and estimated cost "
        "for this session\n"
        "  [yellow]/cost[/yellow]               Alias for [yellow]/tokens[/yellow]\n"
        "  Override cost rates via [dim]KUBE_Q_COST_PER_1K_PROMPT[/dim] and "
        "[dim]KUBE_Q_COST_PER_1K_COMPLETION[/dim] env vars.\n\n"

        # ── HITL (Human-in-the-Loop) ──────────────────────────────────────────
        "[bold cyan]Human-in-the-Loop (HITL)[/bold cyan]\n\n"
        "  When kube-q proposes a [bold]write action[/bold] (deploy, delete, scale, etc.)\n"
        "  it pauses and waits for your approval before proceeding.\n\n"
        "  [yellow]/approve[/yellow]            Approve the pending action — kube-q executes it\n"
        "  [yellow]/deny[/yellow]               Deny the pending action — nothing is applied\n"
        "  The prompt changes to [bold yellow]HITL>[/bold yellow] while an action is pending.\n\n"

        # ── Terminal ──────────────────────────────────────────────────────────
        "[bold cyan]Terminal[/bold cyan]\n\n"
        "  [yellow]/clear[/yellow]              Clear the terminal screen\n"
        "  [yellow]/help[/yellow]               Show this help\n"
        "  [yellow]/quit[/yellow]  [dim]/exit  /q[/dim]   Exit kube-q\n\n"

        # ── CLI flags (reminder) ──────────────────────────────────────────────
        "[bold cyan]Useful launch flags[/bold cyan]\n\n"
        "  [dim]kq --query \"...\"[/dim]           One-shot query, then exit\n"
        "  [dim]kq --url http://host:8000[/dim]     Connect to a specific API server\n"
        "  [dim]kq --api-key <key>[/dim]           Authenticate with an API key  [dim](required when server auth is enabled)[/dim]\n"  # noqa: E501
        "  [dim]kq --ca-cert /path/cert.pem[/dim]   Custom CA certificate for TLS\n"
        "  [dim]kq --output plain[/dim]            Plain text output (no markdown)\n"
        "  [dim]kq --no-stream[/dim]               Wait for full response instead of streaming\n"
        "  [dim]kq --no-banner[/dim]               Suppress logo  [dim](useful for screen recordings)[/dim]\n"  # noqa: E501
        "  [dim]kq --debug[/dim]                   Show raw HTTP request/response log\n"
        "  [dim]kq --version[/dim]                 Print version and exit\n"
        "  [dim]kq --list[/dim]                    List recent sessions and exit\n"
        "  [dim]kq --search \"...[/dim]\"             Full-text search across session "
        "history and exit\n"
        "  [dim]kq --session-id <id>[/dim]         Resume a previous session by ID\n"
        "  [dim]kq --model <name>[/dim]            Override model name sent in requests\n"
        "  [dim]kq --user-name <name>[/dim]        Your display name in the prompt  [dim](default: You)[/dim]\n"  # noqa: E501
        "  [dim]kq --agent-name <name>[/dim]       Assistant name in saved files  [dim](default: kube-q)[/dim]\n"  # noqa: E501
        "  [dim]KUBE_Q_URL=http://...[/dim]             Set API URL via environment variable\n"
        "  [dim]KUBE_Q_API_KEY=...[/dim]                Set API key via environment variable  [dim](avoids 401 errors)[/dim]\n"  # noqa: E501
        "  [dim]KUBE_Q_MODEL=...[/dim]                  Override model name via "
        "environment variable\n"
        "  [dim]KUBE_Q_USER_NAME=...[/dim]              Set your display name via "
        "environment variable\n"
        "  [dim]KUBE_Q_AGENT_NAME=...[/dim]             Set assistant name via "
        "environment variable\n\n"

        # ── Config file ───────────────────────────────────────────────────────
        "[bold cyan]Config (~/.kube-q/.env or ./.env)[/bold cyan]\n\n"
        "  [dim]KUBE_Q_URL, KUBE_Q_API_KEY, KUBE_Q_MODEL[/dim]\n"
        "  [dim]KUBE_Q_TIMEOUT, KUBE_Q_HEALTH_TIMEOUT, KUBE_Q_NAMESPACE_TIMEOUT[/dim]\n"
        "  [dim]KUBE_Q_STARTUP_RETRY_TIMEOUT, KUBE_Q_STARTUP_RETRY_INTERVAL[/dim]\n"
        "  [dim]KUBE_Q_STREAM, KUBE_Q_OUTPUT, KUBE_Q_LOG_LEVEL[/dim]\n"
        "  [dim]KUBE_Q_USER_NAME, KUBE_Q_AGENT_NAME[/dim]\n"
        "  [dim]KUBE_Q_COST_PER_1K_PROMPT, KUBE_Q_COST_PER_1K_COMPLETION[/dim]\n\n"
        "  Logs are written to [dim]~/.kube-q/kube-q.log[/dim]",
        title="[bold cyan]kube-q Help[/bold cyan]",
        border_style="cyan",
        expand=False,
        padding=(1, 2),
    ))
