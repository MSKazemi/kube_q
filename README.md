# kube-q

**Chat with your Kubernetes cluster from the terminal.**

`kube-q` is an interactive CLI (`kq`) that connects to an AI-powered backend and lets you query, debug, and manage your cluster in plain English — with streaming responses, human-in-the-loop approval flows, and rich terminal rendering.

---

## Features

- **Interactive REPL** — persistent conversation history, slash commands, Tab completion
- **Streaming responses** — tokens render in real-time via Server-Sent Events
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
```

---

## In-REPL commands

| Command | Description |
| --- | --- |
| `/new` | Start a new conversation |
| `/id` | Show current conversation ID |
| `/state` | Show full session state |
| `/ns <name>` | Set active namespace (`/ns` with no arg clears it) |
| `/save [file]` | Save conversation to a Markdown file |
| `/approve` | Approve a pending HITL action |
| `/deny` | Deny a pending HITL action |
| `/clear` | Clear the terminal screen |
| `/help` | Show full help |
| `/quit` | Exit |

**Keyboard shortcuts:**

| Key | Action |
| --- | --- |
| `Enter` | Send message |
| `Alt+Enter` or `Esc` → `Enter` | Insert newline (multi-line input) |
| `Tab` | Auto-complete slash commands |

---

## File attachments

Embed a file's contents directly in your message using `@`:

```text
what is wrong with this deployment? @deployment.yaml
compare these two configs: @old.yaml @new.yaml
```

Supports: `yaml`, `json`, `py`, `sh`, `go`, `tf`, `toml`, `js`, `ts`, `rs`, `java`, `xml`, `html`, `md`, `txt`, `log`, and more. Limit: 100 KB per file.

---

## CLI options

```text
kq [--url URL] [--query TEXT] [--no-stream] [--user-id ID]
   [--api-key KEY] [--ca-cert PATH] [--output {rich,plain}]
   [--no-banner] [--user-name NAME] [--agent-name NAME]
```

| Flag | Default | Description |
| --- | --- | --- |
| `--url` | `http://localhost:8000` | kube-q API base URL (env: `KUBE_Q_URL`) |
| `--query` / `-q` | — | Run a single query and exit |
| `--no-stream` | off | Wait for full response instead of streaming |
| `--user-id` | auto | Persistent user ID (saved to `~/.kube_q_id`) |
| `--api-key` | — | Bearer token for auth-enabled servers (env: `KUBE_Q_API_KEY`) |
| `--ca-cert` | — | Custom CA certificate bundle for TLS |
| `--output` | `rich` | `rich` for markdown rendering, `plain` for raw text |
| `--no-banner` | off | Suppress logo (useful for screen recordings) |
| `--user-name` | `You` | Your display name in the prompt (env: `KUBE_Q_USER_NAME`) |
| `--agent-name` | `kube-q` | Assistant name in saved conversations (env: `KUBE_Q_AGENT_NAME`) |

---

## Configuration

kube-q loads configuration from `.env` files and environment variables. There is no separate config file — everything is done with `KUBE_Q_*` variables.

Priority order (highest wins):

```text
CLI flag  >  shell env var  >  ./.env  >  ~/.kube-q/.env  >  default
```

### .env files

kube-q automatically loads `.env` files — no extra tooling required:

| Location | Priority | Use case |
| --- | --- | --- |
| `~/.kube-q/.env` | lower | Persistent user-level defaults |
| `./.env` (current directory) | higher | Project-local or per-cluster overrides |

Shell-exported variables always win over `.env` files.

**Supported variables:**

```bash
KUBE_Q_URL=http://localhost:8000
KUBE_Q_API_KEY=your-key-here
KUBE_Q_TIMEOUT=120
KUBE_Q_HEALTH_TIMEOUT=5
KUBE_Q_NAMESPACE_TIMEOUT=3
KUBE_Q_STARTUP_RETRY_TIMEOUT=300
KUBE_Q_STARTUP_RETRY_INTERVAL=5
KUBE_Q_STREAM=true
KUBE_Q_OUTPUT=rich
KUBE_Q_LOG_LEVEL=INFO
KUBE_Q_USER_NAME=You
KUBE_Q_AGENT_NAME=kube-q
```

**Example — per-cluster `.env`:**

```bash
# .env in your cluster's working directory
KUBE_Q_URL=https://kube-q.prod.example.com
KUBE_Q_API_KEY=prod-secret-key
KUBE_Q_USER_NAME=alice
```

Then just run `kq` from that directory and it picks up the settings automatically.

### Best practice by install method

| Method | Recommended approach |
| --- | --- |
| `pip install kube-q` (end user) | Put settings in `~/.kube-q/.env` — loaded on every `kq` run, nothing to manage per-directory |
| Cloning from source (developer) | Copy `.env.example` → `.env` in the repo root, fill in dev values — already git-ignored |
| Multiple clusters / environments | One `.env` per working directory; `cd` into the right directory before running `kq` |
| CI / scripts | Use shell env vars (`export KUBE_Q_*`) or inject secrets directly — avoid `.env` files in automated environments |

For pip users the simplest setup is:

```bash
# One-time setup
mkdir -p ~/.kube-q
cat >> ~/.kube-q/.env <<'EOF'
KUBE_Q_URL=https://kube-q.example.com
KUBE_Q_API_KEY=your-key-here
EOF
```

After that, just run `kq` from any directory.

---

## Authentication

When the server has API key authentication enabled, requests without a valid key are rejected with HTTP 401. `kube-q` shows a clear message in that case:

```text
Authentication required. Set KUBE_Q_API_KEY or pass --api-key with a valid key.
Ask your admin for an API key.
```

Supply the key via CLI flag, env var, `.env` file, or config file (see [Configuration](#configuration) above). When auth is **disabled** on the server, no key is needed and everything works as before.

---

## Human-in-the-Loop (HITL)

When the AI backend requests approval before executing a potentially destructive action, `kube-q` pauses and shows an approval prompt:

```text
╭─ Action requires approval ─╮
│ Type /approve to proceed   │
│ or /deny to cancel.        │
╰────────────────────────────╯
HITL> /approve
```

---

## License

MIT
