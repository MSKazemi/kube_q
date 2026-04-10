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
|---|---|
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
|---|---|
| `Enter` | Send message |
| `Alt+Enter` or `Esc` → `Enter` | Insert newline (multi-line input) |
| `Tab` | Auto-complete slash commands |

---

## File attachments

Embed a file's contents directly in your message using `@`:

```
what is wrong with this deployment? @deployment.yaml
compare these two configs: @old.yaml @new.yaml
```

Supports: `yaml`, `json`, `py`, `sh`, `go`, `tf`, `toml`, `js`, `ts`, `rs`, `java`, `xml`, `html`, `md`, `txt`, `log`, and more. Limit: 100 KB per file.

---

## CLI options

```
kq [--url URL] [--query TEXT] [--no-stream] [--user-id ID]
   [--api-key KEY] [--ca-cert PATH] [--output {rich,plain}]
   [--no-banner]
```

| Flag | Default | Description |
|---|---|---|
| `--url` | `http://localhost:8000` | kube-q API base URL (env: `KUBE_Q_URL`) |
| `--query` / `-q` | — | Run a single query and exit |
| `--no-stream` | off | Wait for full response instead of streaming |
| `--user-id` | auto | Persistent user ID (saved to `~/.kube_q_id`) |
| `--api-key` | — | Bearer token (env: `KUBE_Q_API_KEY`) |
| `--ca-cert` | — | Custom CA certificate bundle for TLS |
| `--output` | `rich` | `rich` for markdown rendering, `plain` for raw text |
| `--no-banner` | off | Suppress logo (useful for screen recordings) |

---

## Human-in-the-Loop (HITL)

When the AI backend requests approval before executing a potentially destructive action, `kube-q` pauses and shows an approval prompt:

```
╭─ Action requires approval ─╮
│ Type /approve to proceed   │
│ or /deny to cancel.        │
╰────────────────────────────╯
HITL> /approve
```

---

## License

MIT
