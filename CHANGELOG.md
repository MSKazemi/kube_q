# Changelog

All notable changes to kube-q will be documented here.

## [Unreleased]

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
