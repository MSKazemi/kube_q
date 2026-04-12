# Changelog

All notable changes to kube-q will be documented here.

## [Unreleased]

### Added — v2.3 Session Search & Branching
- **`kq --search <query>` / `/search <query>`**: FTS5 full-text search across all session history with highlighted match snippets; supports FTS5 boolean syntax (`pods AND NOT staging`); old databases are backfilled during schema migration
- **`/branch`**: fork the current conversation at the current message count into a new independent session — orignal is preserved; `/branches` lists all forks; `/title <text>` renames a session
- **SQLite schema v3**: `messages_fts` FTS5 virtual table with insert/delete triggers, `parent_session_id` and `branch_point` columns on `sessions`; branches are ordinary sessions so search finds them automatically

### Added — v2.2 Token & Cost Tracking
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
