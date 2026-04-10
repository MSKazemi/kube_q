"""
cli_render.py — Display utilities: Rich console, ANSI helpers, logo, markdown rendering.
"""

import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

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

def _fmt_help() -> None:
    console.print(Panel(
        # ── Sending messages ──────────────────────────────────────────────────
        "[bold cyan]Sending messages[/bold cyan]\n\n"
        "  [yellow]Enter[/yellow]              Send your message\n"
        "  [yellow]Alt+Enter[/yellow]          Insert a newline  [dim](hold Alt, press Enter)[/dim]\n"
        "  [yellow]Esc  →  Enter[/yellow]      Insert a newline  [dim](press Esc, release, then Enter — works everywhere)[/dim]\n"
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
        "  [yellow]↑ / ↓[/yellow]             Scroll through previous messages  [dim](history)[/dim]\n"
        "  [yellow]Ctrl+A[/yellow]             Jump to start of line\n"
        "  [yellow]Ctrl+E[/yellow]             Jump to end of line\n"
        "  [yellow]Ctrl+W[/yellow]             Delete previous word\n"
        "  [yellow]Ctrl+U[/yellow]             Clear entire input buffer\n"
        "  [yellow]Ctrl+C[/yellow]             Cancel current input (keeps history)\n"
        "  [yellow]Ctrl+D[/yellow]             Exit the session\n\n"

        # ── Conversation commands ─────────────────────────────────────────────
        "[bold cyan]Conversation commands[/bold cyan]\n\n"
        "  [yellow]/new[/yellow]               Start a fresh conversation  [dim](new ID, clears history)[/dim]\n"
        "  [yellow]/id[/yellow]                Show the current conversation ID\n"
        "  [yellow]/state[/yellow]             Show full session state  [dim](ID, namespace, HITL flag)[/dim]\n"
        "  [yellow]/save[/yellow]              Save conversation to [dim]kube-q-TIMESTAMP.md[/dim]\n"
        "  [yellow]/save <file>[/yellow]        Save conversation to a specific file\n\n"

        # ── Namespace ─────────────────────────────────────────────────────────
        "[bold cyan]Namespace[/bold cyan]\n\n"
        "  [yellow]/ns <name>[/yellow]          Set active namespace — prepended to every query\n"
        "  [yellow]/ns[/yellow]                 Clear active namespace\n\n"

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
        "  [dim]kq --api-key <key>[/dim]           Authenticate with an API key\n"
        "  [dim]kq --ca-cert /path/cert.pem[/dim]   Custom CA certificate for TLS\n"
        "  [dim]kq --output plain[/dim]            Plain text output (no markdown)\n"
        "  [dim]kq --no-stream[/dim]               Wait for full response instead of streaming\n"
        "  [dim]kq --no-banner[/dim]               Suppress logo  [dim](useful for screen recordings)[/dim]\n"
        "  [dim]KUBE_Q_URL=http://...[/dim]             Set API URL via environment variable\n"
        "  [dim]KUBE_Q_API_KEY=...[/dim]                Set API key via environment variable",
        title="[bold cyan]kube-q Help[/bold cyan]",
        border_style="cyan",
        expand=False,
        padding=(1, 2),
    ))
