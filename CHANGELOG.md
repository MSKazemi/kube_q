# Changelog

All notable changes to kube-q will be documented here.

## [Unreleased]

## [1.4.0] — 2026-04-14

### Added — Web UI (Docker)
- **Browser terminal** — full kube-q REPL accessible in any browser via xterm.js + WebSocket → node-pty → `kq`; no client-side logic duplicated, all commands and streaming stay in the Python process
- **`web/server.mjs`** — production single-port server: Next.js HTTP + PTY WebSocket (`/pty-ws`) on one port; spawns a `kq` process per connection
- **`web/pty-server.mjs`** — dev standalone PTY WebSocket server on port 3001; run alongside `next dev` via `npm run dev`
- **`Dockerfile`** — multi-stage build: Node builder compiles Next.js, runtime stage installs `kube-q` from PyPI + copies built app; env vars injected at runtime (`KUBE_Q_URL`, `KUBE_Q_API_KEY`)
- **iframe / basePath support** — `NEXT_PUBLIC_BASE_PATH` env var relocates the Next.js app to a sub-path; `Content-Security-Policy: frame-ancestors *` and `X-Frame-Options: ALLOWALL` headers allow embedding in any parent page
- **Download conversation button** — toolbar "⬇ Download" button exports the xterm scrollback buffer as a `.md` file directly to the browser
- **Custom branding** — `KUBE_Q_LOGO` sets a custom ASCII banner logo; `KUBE_Q_TAGLINE` sets a custom copyright / tagline line; both configurable via `.env` or environment variable

### Added — Session Search & Branching
- **`kq --search <query>` / `/search <query>`**: FTS5 full-text search across all session history with highlighted match snippets; supports FTS5 boolean syntax (`pods AND NOT staging`); old databases are backfilled during schema migration
- **`/branch`**: fork the current conversation at the current message count into a new independent session — original is preserved; `/branches` lists all forks; `/title <text>` renames a session
- **SQLite schema v3**: `messages_fts` FTS5 virtual table with insert/delete triggers, `parent_session_id` and `branch_point` columns on `sessions`; branches are ordinary sessions so search finds them automatically

### Added — Token & Cost Tracking
- **Token footer**: every response now shows `(1.2s · 460 tokens)` when the server emits a `usage` block in the SSE stream or JSON response; servers that omit `usage` behave exactly as before — no errors, no noise
- **`/tokens` / `/cost`**: new in-REPL commands print a Rich panel with per-session prompt/completion/total counts, request count, and estimated dollar cost; override rates with `KUBE_Q_COST_PER_1K_PROMPT` and `KUBE_Q_COST_PER_1K_COMPLETION` env vars for custom backends
- **`kq --list` tokens column**: session listing now shows total token count per session; SQLite schema auto-migrates transparently from v1 databases (adds `token_log` table and `total_*_tokens` columns via `PRAGMA user_version`)

### Added
- Configurable display names — `--user-name` / `--agent-name` CLI flags, `KUBE_Q_USER_NAME` / `KUBE_Q_AGENT_NAME` env vars, and `user_name` / `agent_name` config file keys; used in the prompt and saved conversation files
- Friendly HTTP 401 error handling — shows a clear actionable message instead of raw JSON when the server has auth enabled and the key is missing or invalid; affects streaming, non-streaming, and health-check paths
- `.env` file support — all settings configurable via `KUBE_Q_*` environment variables; kube-q loads `~/.kube-q/.env` and `./.env` automatically (no extra tooling required)
- Removed YAML config file — `.env` files cover all the same settings with one less format and one less dependency (`pyyaml` removed)
- Renamed config directory to `~/.kube-q/`; history, user-id, and log files all consolidated there

## [1.0.0] — 2026-04-10

### Added
- Interactive REPL with streaming SSE responses
- Human-in-the-Loop (HITL) approve/deny flow
- Persistent conversation history and user ID
- Namespace context switching (`/ns`)
- Conversation save to markdown (`/save`)
- Built-in demo scenarios (deploy, debug, hitl, security, scale)
- Single-query mode (`--query`)
- Health check with retry on startup
- Multi-line copy-paste support via `prompt_toolkit`
- Rich syntax highlighting for YAML/JSON code blocks
- File attachment support via `@filename` in messages
- `--api-key` / `KUBE_Q_API_KEY` authentication
- `--ca-cert` for corporate proxies / self-signed certificates
- `--output plain` flag for pipe-friendly output
- Live token streaming
- Typo suggestions for unknown slash commands
