# kube-q

**Chat with your Kubernetes cluster from the terminal.**

`kube-q` is an interactive CLI (`kq`) that connects to an AI-powered backend and lets you query, debug, and manage your cluster in plain English — with streaming responses, persistent session history, full-text search, conversation branching, token cost tracking, human-in-the-loop approval flows, and rich terminal rendering.

---

## Features

- **Interactive REPL** — persistent conversation history, slash commands, Tab completion
- **Streaming responses** — tokens render in real-time via Server-Sent Events
- **Session persistence** — every conversation is saved to a local SQLite database; resume any past session with `--session-id`
- **Full-text search** — `kq --search "pod crash"` or `/search` inside the REPL; FTS5-powered with highlighted match snippets and boolean syntax
- **Conversation branching** — `/branch` forks the current conversation at any point; the original is untouched; `/branches` lists all forks
- **Token & cost tracking** — every response shows tokens used; `/tokens` shows session totals and estimated dollar cost; rates configurable per model
- **Human-in-the-Loop (HITL)** — review and approve or deny destructive actions before they run
- **Namespace context** — set an active namespace with `/ns <name>`; it's injected into every message automatically
- **File attachments** — embed YAML, JSON, logs, and more with `@filename` anywhere in a message
- **Conversation save** — dump the full session to a Markdown file with `/save`
- **Single-query mode** — pipe-friendly with `kq --query "…"` and `--output plain`
- **TLS & auth** — `--api-key` / `KUBE_Q_API_KEY` env var, custom CA cert via `--ca-cert`
- **Rich output** — syntax-highlighted code blocks, elapsed response time, typo suggestions for slash commands

---

## Installation

```bash
pip install kube-q
```

Or install from source:

```bash
git clone https://github.com/your-org/kube-q
cd kube-q
pip install -e .
```

Requires Python 3.12+.

---

## Quick start

```bash
# Start the interactive REPL (connects to localhost:8000 by default)
kq

# Point at a remote API
kq --url https://kube-q.example.com

# Single query and exit
kq --query "show me all pods in the default namespace"

# Pipe-friendly plain text output
kq --query "list failing deployments" --output plain

# List recent sessions
kq --list

# Search across all past conversations
kq --search "pod crash"

# Resume a previous session
kq --session-id <id>
```

---

## In-REPL commands

### Conversation

| Command | Description |
| --- | --- |
| `/new` | Start a new conversation (clears history, generates new ID) |
| `/id` | Show the current conversation ID |
| `/state` | Show full session state — ID, user, messages, tokens, namespace, HITL flag |
| `/save [file]` | Save conversation to a Markdown file |
| `/clear` | Clear the terminal screen |
| `/help` | Show full in-REPL help |
| `/quit` / `/exit` / `/q` | Exit kube-q |

### Namespace

| Command | Description |
| --- | --- |
| `/ns <name>` | Set active namespace — prepended to every query automatically |
| `/ns` | Clear the active namespace |

### Session history

| Command | Description |
| --- | --- |
| `/sessions` | List recent sessions (same as `kq --list`) |
| `/forget` | Delete the current session from local history (server data untouched) |

### History & branching

| Command | Description |
| --- | --- |
| `/search <query>` | Full-text search across all past sessions with highlighted snippets |
| `/branch` | Fork this conversation at the current point into a new independent session |
| `/branches` | List all forks of (and siblings of) this session |
| `/title <text>` | Rename the current session |

FTS5 boolean syntax is supported: `/search pods AND NOT staging`

### Token usage

| Command | Description |
| --- | --- |
| `/tokens` | Show token counts and estimated cost for this session |
| `/cost` | Alias for `/tokens` |

### Human-in-the-Loop

| Command | Description |
| --- | --- |
| `/approve` | Approve a pending HITL action — the AI executes it |
| `/deny` | Deny a pending HITL action — nothing is applied |

**Keyboard shortcuts:**

| Key | Action |
| --- | --- |
| `Enter` | Send message |
| `Alt+Enter` or `Esc` → `Enter` | Insert newline (multi-line input) |
| `Tab` | Auto-complete slash commands |
| `↑` / `↓` | Scroll through input history |
| `Ctrl+C` | Cancel current input |
| `Ctrl+D` | Exit the session |

---

## File attachments

Embed a file's contents directly in your message using `@`:

```text
what is wrong with this deployment? @deployment.yaml
compare these two configs: @old.yaml @new.yaml
what is wrong here? @pod.yaml @service.yaml
```

Supports: `yaml`, `json`, `py`, `sh`, `go`, `tf`, `toml`, `js`, `ts`, `rs`, `java`, `xml`, `html`, `md`, `txt`, `log`, and more. Limit: 100 KB per file. Quote paths with spaces: `@"my file.yaml"`.

---

## CLI reference

```text
kq [options]
```

### Flags

| Flag | Default | Description |
| --- | --- | --- |
| `--url URL` | `http://localhost:8000` | kube-q API base URL (env: `KUBE_Q_URL`) |
| `--query` / `-q TEXT` | — | Run a single query and exit |
| `--no-stream` | off | Disable streaming — wait for full response |
| `--session-id ID` | — | Resume a previous session by ID |
| `--list` | — | List recent sessions and exit |
| `--search QUERY` | — | Full-text search across session history and exit |
| `--user-id ID` | auto | Persistent user ID (saved to `~/.kube-q/user-id`) |
| `--api-key KEY` | — | Bearer token for auth-enabled servers (env: `KUBE_Q_API_KEY`) |
| `--ca-cert PATH` | — | Custom CA certificate bundle for TLS |
| `--output {rich,plain}` | `rich` | `rich` for markdown rendering, `plain` for raw text |
| `--model NAME` | `kubeintellect-v2` | Model name sent in requests (env: `KUBE_Q_MODEL`) |
| `--user-name NAME` | `You` | Your display name in the prompt (env: `KUBE_Q_USER_NAME`) |
| `--agent-name NAME` | `kube-q` | Assistant name in saved conversations (env: `KUBE_Q_AGENT_NAME`) |
| `--no-banner` | off | Suppress logo (useful for screen recordings) |
| `--debug` | off | Log raw HTTP requests/responses to stderr and `~/.kube-q/kube-q.log` |
| `--version` | — | Print version and exit |

---

## Session history

kube-q saves every conversation to a local SQLite database at `~/.kube-q/history.db`. Nothing is sent to or read from the server — this is a local-only mirror.

```bash
# See recent sessions
kq --list

# Resume from where you left off
kq --session-id <id>

# Search across everything you've ever discussed
kq --search "deployment rollback"
kq --search "pods AND crash"
```

Inside the REPL, `/sessions`, `/forget`, `/search`, `/branch`, `/branches`, and `/title` give you full control over history.

**Branching** forks a conversation at the current message count. The original session is never modified — you get a new independent session you can take in a different direction. Branches show up in `kq --list` as regular sessions.

---

## Token & cost tracking

After every response kube-q shows the token count in the footer:

```
kube-q  (1.2s · 460 tokens)
```

Use `/tokens` or `/cost` for a session summary:

```
┌─ Token Usage ─────────────────────────┐
│ This session:                         │
│   Prompt:     1,240 tokens            │
│   Completion: 3,890 tokens            │
│   Total:      5,130 tokens            │
│   Requests:   8                       │
│   Est. cost:  $0.0312                 │
│                                       │
│ Last response:                        │
│   120 in → 340 out ($0.0024)          │
└───────────────────────────────────────┘
```

Cost estimates are labeled "Est." — not exact. Built-in rates for `kubeintellect-v2`, `gpt-4o`, `gpt-4o-mini`, and `claude-sonnet-4-6`. Override for custom backends:

```bash
KUBE_Q_COST_PER_1K_PROMPT=0.002
KUBE_Q_COST_PER_1K_COMPLETION=0.008
```

If the server doesn't emit a `usage` block, the footer omits the token count — no errors, no noise.

---

## Configuration

kube-q loads configuration from `.env` files and environment variables. Priority order (highest wins):

```
CLI flag  >  shell env var  >  ./.env  >  ~/.kube-q/.env  >  default
```

### .env files

| Location | Priority | Use case |
| --- | --- | --- |
| `~/.kube-q/.env` | lower | Persistent user-level defaults |
| `./.env` (current directory) | higher | Project-local or per-cluster overrides |

Shell-exported variables always win over `.env` files.

### All supported variables

```bash
KUBE_Q_URL=http://localhost:8000
KUBE_Q_API_KEY=your-key-here
KUBE_Q_MODEL=kubeintellect-v2
KUBE_Q_TIMEOUT=120
KUBE_Q_HEALTH_TIMEOUT=5
KUBE_Q_NAMESPACE_TIMEOUT=3
KUBE_Q_STARTUP_RETRY_TIMEOUT=300
KUBE_Q_STARTUP_RETRY_INTERVAL=5
KUBE_Q_STREAM=true
KUBE_Q_OUTPUT=rich                  # rich | plain
KUBE_Q_LOG_LEVEL=INFO               # DEBUG | INFO | WARNING | ERROR
KUBE_Q_USER_NAME=You
KUBE_Q_AGENT_NAME=kube-q
KUBE_Q_COST_PER_1K_PROMPT=0.003    # override cost rate for /tokens
KUBE_Q_COST_PER_1K_COMPLETION=0.006
```

### Example — per-cluster setup

```bash
# .env in your cluster's working directory
KUBE_Q_URL=https://kube-q.prod.example.com
KUBE_Q_API_KEY=prod-secret-key
KUBE_Q_USER_NAME=alice
```

Run `kq` from that directory and it picks up the settings automatically.

### Quick one-time setup (pip users)

```bash
mkdir -p ~/.kube-q
cat >> ~/.kube-q/.env <<'EOF'
KUBE_Q_URL=https://kube-q.example.com
KUBE_Q_API_KEY=your-key-here
EOF
```

---

## Authentication

When the server has API key authentication enabled, requests without a valid key are rejected with HTTP 401. kube-q shows a clear message:

```
Authentication required. Set KUBE_Q_API_KEY or pass --api-key with a valid key.
Ask your administrator for an API key.
```

When auth is disabled on the server, no key is needed.

---

## Human-in-the-Loop (HITL)

When the AI backend requests approval before executing a potentially destructive action, kube-q pauses:

```
╭─ Action requires approval ──────────────────╮
│ Action requires approval.                   │
│ Type /approve to proceed or /deny to cancel.│
╰─────────────────────────────────────────────╯
HITL> /approve
```

The prompt changes to `HITL>` while an action is pending. Type `/approve` to execute it or `/deny` to cancel.

---

## Data & privacy

- Session history is stored **locally only** at `~/.kube-q/history.db` (SQLite). Nothing is sent to the kube-q server.
- Conversations may contain sensitive cluster data. Use `/save` with care — saved files go wherever you point them.
- The user ID (`~/.kube-q/user-id`) is stored with `0600` permissions.
- Logs are written to `~/.kube-q/kube-q.log` (rotating, 5 MB × 3 files).

---

## License

MIT
