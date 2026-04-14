# kube-q

**Chat with your Kubernetes cluster from the terminal.**

`kube-q` is an interactive CLI (`kq`) that connects to an AI-powered backend and lets you query, debug, and manage your cluster in plain English — with streaming responses, persistent session history, full-text search, conversation branching, token cost tracking, human-in-the-loop approval flows, and rich terminal rendering.

A browser-based terminal is also available via Docker — the full `kq` REPL runs in any browser with no extra setup.

---

## Features

| | |
|---|---|
| **Interactive REPL** | Persistent conversation history, slash commands, Tab completion |
| **Streaming responses** | Tokens render in real-time via Server-Sent Events |
| **Session persistence** | Every conversation saved to local SQLite; resume with `--session-id` |
| **Full-text search** | `kq --search "pod crash"` with FTS5 boolean syntax and highlighted snippets |
| **Conversation branching** | `/branch` forks at any point; original is untouched |
| **Token & cost tracking** | Per-response token counts; `/tokens` shows session totals and estimated cost |
| **Human-in-the-Loop** | Review and approve or deny destructive actions before they run |
| **File attachments** | Embed YAML, JSON, logs with `@filename` anywhere in a message |
| **Web terminal** | Full `kq` REPL in any browser via Docker (xterm.js + WebSocket + node-pty) |
| **Python SDK** | Use `KubeQClient` directly in scripts and tools |

---

## Quick start

```bash
pip install kube-q
kq
```

Point at your backend:

```bash
kq --url https://kube-q.example.com
```

Single query and exit:

```bash
kq --query "show me all pods in the default namespace"
kq --query "list failing deployments" --output plain
```

List and resume sessions:

```bash
kq --list
kq --session-id <id>
kq --search "pod crash"
```

---

## Next steps

- [Installation](installation.md) — pip, Homebrew, Docker
- [CLI Reference](cli-reference.md) — all flags and options
- [Configuration](configuration.md) — `.env` files and `KUBE_Q_*` variables
- [In-REPL Commands](commands.md) — slash commands and keyboard shortcuts
- [Web UI](web-ui.md) — run kube-q in a browser via Docker
