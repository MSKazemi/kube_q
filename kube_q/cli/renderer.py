"""
renderer.py — Display utilities: Rich console, ANSI helpers, logo, markdown rendering,
and side-channel event renderers for the CLI.
"""

import datetime
import sys

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text


def error_timestamp() -> str:
    """Return a dim Rich-markup prefix like '[dim][14:07:33][/dim] ' for error lines."""
    return f"[dim][{datetime.datetime.now().strftime('%H:%M:%S')}][/dim] "

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

_DEFAULT_LOGO_ART = (
    "\033[1;36m    __ __      __         ____      __       ____          __ \033[0m\n"
    "\033[1;36m   / //_/_  __/ /_  ___  /  _/___  / /____  / / /__  _____/ /_\033[0m\n"
    "\033[1;36m  / ,< / / / / __ \\/ _ \\ / // __ \\/ __/ _ \\/ / / _ \\/ ___/ __/\033[0m\n"
    "\033[1;36m / /| / /_/ / /_/ /  __// // / / / /_/  __/ / /  __/ /__/ /_  \033[0m\n"
    "\033[1;36m/_/ |_\\__,_/_.___/\\___/___/_/ /_/\\__/\\___/_/_/\\___/\\___/\\__/  \033[0m"
)
_DEFAULT_TAGLINE = "Your AI co-pilot for Kubernetes."

# Small watermark shown below a custom logo when KUBE_Q_LOGO is set.
_KUBE_Q_WATERMARK = "\033[2m  powered by kube-q\033[0m"

_custom_logo: str | None = None
_custom_tagline: str | None = None


def set_custom_logo(text: str | None) -> None:
    """Set a custom logo block (replaces the ASCII art).  Use \\n for newlines."""
    global _custom_logo
    _custom_logo = text.replace("\\n", "\n") if text else None


def set_custom_tagline(text: str | None) -> None:
    """Set a custom tagline / copyright line."""
    global _custom_tagline
    _custom_tagline = text


def _print_logo(connected: bool = True) -> None:
    if not sys.stdout.isatty():
        return
    print()
    if _custom_logo:
        # Big custom logo + small kube-q watermark
        print(_custom_logo)
        tagline = _custom_tagline or _DEFAULT_TAGLINE
        print(f"\033[2m  {tagline}\033[0m")
        print(_KUBE_Q_WATERMARK)
    else:
        # Default kube-q ASCII art
        colour = "\033[1;36m" if connected else "\033[1;31m"
        art = _DEFAULT_LOGO_ART.replace("\033[1;36m", colour)
        tagline = _custom_tagline or _DEFAULT_TAGLINE
        print(art)
        print(f"\033[2m   {tagline}\033[0m")
    print()


def _print_not_connected_panel(url: str, reason: str) -> None:
    """Show an actionable panel when the backend is unreachable."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    console.print(Panel(
        f"[red bold]✗ Cannot reach:[/red bold] {url}\n"
        f"[dim]  Time:   {ts}[/dim]\n"
        f"[dim]  Reason: {reason}[/dim]\n\n"
        "[bold]To configure the backend URL:[/bold]\n"
        "  [yellow]kq --url http://host:8000[/yellow]"
        "                    One-time launch flag\n"
        "  [yellow]export KUBE_Q_URL=http://host:8000[/yellow]"
        "             Current shell session\n"
        "  [yellow]/url http://host:8000[/yellow]"
        "                         Change without restarting\n"
        "  [yellow]echo 'KUBE_Q_URL=http://...' >> ~/.kube-q/.env[/yellow]"
        "   Persist permanently\n\n"
        "[dim]These commands work offline: "
        "/help  /sessions  /save  /state  /tokens  /search  /branch[/dim]",
        title="[red]Backend not reachable[/red]",
        border_style="red",
    ))


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


# ── Side-channel event renderers ──────────────────────────────────────────────

def render_status(event: dict, live: Live, first_token: bool) -> None:
    """Render a ``status`` side-channel event.

    While the spinner is still visible (no tokens yet), replace the spinner
    text with the new status message.  After the first token has arrived the
    spinner is gone, so fall back to printing a dim ephemeral line above the
    live markdown area.
    """
    msg = event.get("message") or event.get("phase") or ""
    if not msg:
        return
    if first_token:
        live.update(Spinner("dots", text=Text.assemble((" ", ""), (msg, "dim cyan"))))
    else:
        console.print(f"[dim]⚙ {msg}[/dim]")


def render_tool_call(event: dict) -> None:
    """Render a ``tool_call`` side-channel event above the live area."""
    tool = event.get("tool", "")
    msg = event.get("message", "")
    if tool and msg:
        console.print(f"[dim cyan]⚙ {tool}[/dim cyan][dim] → {msg}[/dim]")
    elif tool:
        console.print(f"[dim cyan]⚙ {tool}[/dim cyan]")
    elif msg:
        console.print(f"[dim]⚙ {msg}[/dim]")


def render_error_event(event: dict) -> None:
    """Render an ``error`` side-channel event."""
    console.print(
        f"{error_timestamp()}[red]✗ {event.get('message', str(event))}[/red]"
    )


# ── Help panel ────────────────────────────────────────────────────────────────

def format_search_results(results: list[dict]) -> None:
    """Print a Rich table of FTS5 search results."""
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
    """Print a Rich table of branched sessions."""
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


def _print_sessions_table(sessions: list[dict]) -> None:
    """Render a Rich table of sessions."""
    from rich.table import Table

    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return

    table = Table(
        "Session ID", "Title", "Messages", "Tokens", "Namespace", "Context", "Updated",
        title="[bold cyan]Recent Sessions[/bold cyan]",
        border_style="dim cyan",
        show_lines=False,
    )
    for s in sessions:
        title = s["title"] or "[dim](untitled)[/dim]"
        ns = s["namespace"] or "[dim]—[/dim]"
        ctx = s.get("kube_context") or "[dim]—[/dim]"
        updated = s["updated_at"][:19].replace("T", " ") if s["updated_at"] else "—"
        total_tok = s.get("total_tokens", 0)
        tok_str = f"{total_tok:,}" if total_tok else "[dim]—[/dim]"
        table.add_row(
            s["session_id"][:36],
            title,
            str(s["message_count"]),
            tok_str,
            ns,
            ctx,
            updated,
        )
    console.print(table)


def _print_token_panel(
    session_id: str,
    override_prompt: float | None = None,
    override_completion: float | None = None,
) -> None:
    """Print a Rich panel showing token usage and estimated cost for a session."""
    from kube_q.cli.store import get_last_usage, get_session_tokens
    from kube_q.core import costs

    tok = get_session_tokens(session_id)
    last = get_last_usage(session_id)

    model = last.get("model") if last else None
    session_cost = costs.estimate_cost(
        model,
        tok["total_prompt_tokens"],
        tok["total_completion_tokens"],
        override_prompt,
        override_completion,
    )

    body = (
        f"  [bold]This session:[/bold]\n"
        f"    Prompt:     {tok['total_prompt_tokens']:,} tokens\n"
        f"    Completion: {tok['total_completion_tokens']:,} tokens\n"
        f"    Total:      {tok['total_tokens']:,} tokens\n"
        f"    Requests:   {tok['request_count']}\n"
        f"    Est. cost:  {costs.format_cost(session_cost)}"
    )

    if last:
        lp = last["prompt_tokens"]
        lc = last["completion_tokens"]
        last_cost = costs.estimate_cost(
            last.get("model"), lp, lc, override_prompt, override_completion
        )
        body += (
            f"\n\n  [bold]Last response:[/bold]\n"
            f"    {costs.format_tokens(lp, lc)} ({costs.format_cost(last_cost)})"
        )

    console.print(Panel(
        body,
        title="[bold cyan]Token Usage[/bold cyan]",
        border_style="dim cyan",
        expand=False,
        padding=(0, 1),
    ))


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
        "  [yellow]Tab[/yellow]                Auto-complete slash commands  [dim](suggestions also pop up as you type)[/dim]\n"  # noqa: E501
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
        "  [yellow]/save <file>[/yellow]        Save conversation to a specific file  [dim](Tab completes paths)[/dim]\n\n"  # noqa: E501

        # ── Namespace ─────────────────────────────────────────────────────────
        "[bold cyan]Namespace[/bold cyan]\n\n"
        "  [yellow]/ns <name>[/yellow]          Set active namespace — prepended to every query\n"
        "  [yellow]/ns[/yellow]                 Clear active namespace\n"
        "  [dim]Tab-completes namespaces from the cluster (cached after first use).[/dim]\n\n"

        # ── Kubernetes context ────────────────────────────────────────────────
        "[bold cyan]Kubernetes context[/bold cyan]\n\n"
        "  [yellow]/context <name>[/yellow]     Set active kubectl context — prepended to every query\n"  # noqa: E501
        "  [yellow]/context[/yellow]            Clear active context\n"
        "  [dim]Tab-completes from your kubeconfig (kubectl config get-contexts).[/dim]\n\n"

        # ── Profiles & plugins ────────────────────────────────────────────────
        "[bold cyan]Profiles & plugins[/bold cyan]\n\n"
        "  [yellow]/profile[/yellow]                 List available profiles in ~/.kube-q/profiles/\n"  # noqa: E501
        "  [yellow]/profile new <name>[/yellow]      Create a new profile .env from template\n"
        "  [yellow]/profile show <name>[/yellow]     Print a profile's contents\n"
        "  [yellow]/profile delete <name>[/yellow]   Delete a profile file\n"
        "  [yellow]/profile <name>[/yellow]          Show restart command to activate a profile  [dim](switching requires restart)[/dim]\n"  # noqa: E501
        "  [yellow]/plugins[/yellow]                 List loaded plugins from ~/.kube-q/plugins/\n"
        "  [dim]Profiles are .env fragments per cluster; plugins register extra slash commands.[/dim]\n\n"  # noqa: E501

        # ── Config ────────────────────────────────────────────────────────────
        "[bold cyan]Config[/bold cyan]\n\n"
        "  [yellow]/config[/yellow]                  Print effective config with each value's source\n"  # noqa: E501
        "  [yellow]/config set KEY=VAL[/yellow]      Persist a value to ~/.kube-q/.env  [dim](validated)[/dim]\n"  # noqa: E501
        "  [yellow]/config reset KEY[/yellow]        Remove a single key from ~/.kube-q/.env\n"
        "  [yellow]/config reset[/yellow]            Delete ~/.kube-q/.env entirely\n"
        "  [dim]KEY accepts the env var (KUBE_Q_URL) or its alias (url).[/dim]\n\n"

        # ── Session history ───────────────────────────────────────────────────
        "[bold cyan]Session history[/bold cyan]\n\n"
        "  [yellow]/sessions[/yellow]           Pick a past session to resume  "
        "[dim](↑/↓ navigate, Enter resume, Esc cancel; kube context restored)[/dim]\n"
        "  [yellow]/resume[/yellow]             Alias for [yellow]/sessions[/yellow]\n"
        "  [yellow]/list[/yellow]               Print recent sessions as a table  "
        "[dim](no picker — same data as[/dim] [yellow]kq --list[/yellow][dim])[/dim]\n"
        "  [yellow]/history[/yellow]            Replay messages in the current session  "
        "[dim](no args = all)[/dim]\n"
        "  [yellow]/history <N>[/yellow]        Show the last [bold]N[/bold] messages\n"
        "  [yellow]/history <X-Y>[/yellow]      Show messages [bold]X[/bold] through [bold]Y[/bold]"
        "  [dim](1-indexed, inclusive)[/dim]\n"
        "  [yellow]/history #<N>[/yellow]       Show just message [bold]#N[/bold]\n"
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
        "  [yellow]/url[/yellow] [dim][new-url][/dim]        Show or change the backend URL  [dim](saves to ~/.kube-q/.env)[/dim]\n"  # noqa: E501
        "  [yellow]/version[/yellow]            Print the installed kube-q version\n"
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
        "  [dim]kq --no-health-check[/dim]          Skip startup health check  [dim](useful for web/scripted use)[/dim]\n"  # noqa: E501
        "  [dim]kq --debug[/dim]                   Show raw HTTP request/response log\n"
        "  [dim]kq --version[/dim]                 Print version and exit\n"
        "  [dim]kq --list[/dim]                    List recent sessions and exit\n"
        "  [dim]kq --search \"...[/dim]\"             Full-text search across session "
        "history and exit\n"
        "  [dim]kq --session-id <id>[/dim]         Resume a previous session by ID  [dim](replays stored transcript on launch)[/dim]\n"  # noqa: E501
        "  [dim]kq --model <name>[/dim]            Override model name sent in requests\n"
        "  [dim]kq --user-name <name>[/dim]        Your display name in the prompt  [dim](default: You)[/dim]\n"  # noqa: E501
        "  [dim]kq --agent-name <name>[/dim]       Assistant name in saved files  [dim](default: kube-q)[/dim]\n"  # noqa: E501
        "  [dim]kq --backend kube-q|openai|azure[/dim]  Pick the LLM backend  [dim](default: kube-q)[/dim]\n"  # noqa: E501
        "  [dim]kq --openai-api-key <key>[/dim]      Use direct OpenAI backend\n"
        "  [dim]kq --openai-endpoint <url>[/dim]     Override the OpenAI endpoint\n"
        "  [dim]kq --azure-openai-api-key <key>[/dim]\n"
        "  [dim]kq --azure-openai-endpoint <url>[/dim]\n"
        "  [dim]kq --azure-openai-deployment <name>[/dim]  Azure OpenAI backend config\n"
        "  [dim]kq --profile <name>[/dim]           Load ~/.kube-q/profiles/<name>.env before start\n"  # noqa: E501
        "  [dim]kq --context <name>[/dim]           Set active kubectl context at startup\n"
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
        "  [dim]KUBE_Q_COST_PER_1K_PROMPT, KUBE_Q_COST_PER_1K_COMPLETION[/dim]\n"
        "  [dim]KUBE_Q_BACKEND, KUBE_Q_OPENAI_API_KEY, KUBE_Q_OPENAI_ENDPOINT, KUBE_Q_OPENAI_MODEL[/dim]\n"  # noqa: E501
        "  [dim]KUBE_Q_AZURE_OPENAI_API_KEY, KUBE_Q_AZURE_OPENAI_ENDPOINT,[/dim]\n"
        "  [dim]  KUBE_Q_AZURE_OPENAI_DEPLOYMENT, KUBE_Q_AZURE_OPENAI_API_VERSION[/dim]\n"
        "  [dim]KUBE_Q_CONTEXT, KUBE_Q_PROFILE[/dim]\n\n"
        "  [yellow]kq config show[/yellow]            List every key with its value and source\n"
        "  [yellow]kq config set KEY=VAL[/yellow]     Persist a value to ~/.kube-q/.env\n"
        "  [yellow]kq config reset [KEY][/yellow]    Remove a key (or wipe the file)\n"
        "  [yellow]kq config profile list[/yellow]   List named profiles in ~/.kube-q/profiles/\n"
        "  [yellow]kq config profile new NAME[/yellow]  Create a new profile .env from template\n"
        "  [yellow]kq config profile show NAME[/yellow] / [yellow]delete NAME[/yellow]\n\n"
        "  Logs are written to [dim]~/.kube-q/kube-q.log[/dim]",
        title="[bold cyan]kube-q Help[/bold cyan]",
        border_style="cyan",
        expand=False,
        padding=(1, 2),
    ))
