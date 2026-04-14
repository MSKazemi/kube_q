# In-REPL Commands

All commands start with `/`. Tab-completion is available — press `Tab` after typing `/` to see suggestions. Typo suggestions are shown for close matches (e.g. `/hlep` → "did you mean /help?").

---

## Conversation

| Command | Description |
|---|---|
| `/new` | Start a new conversation — clears history, generates a new session ID |
| `/id` | Show the current conversation ID |
| `/state` | Show full session state: ID, user, message count, tokens, namespace, HITL flag |
| `/save [file]` | Save conversation to a Markdown file (defaults to a timestamped filename) |
| `/clear` | Clear the terminal screen |
| `/help` | Show full in-REPL help |
| `/quit` / `/exit` / `/q` | Exit kube-q |

---

## Namespace

| Command | Description |
|---|---|
| `/ns <name>` | Set active namespace — prepended to every query automatically |
| `/ns` | Clear the active namespace |

The active namespace is shown in the prompt and injected into messages automatically, so you don't have to type it each time.

---

## Session history

| Command | Description |
|---|---|
| `/sessions` | List the 20 most recent sessions (same as `kq --list`) |
| `/forget` | Delete the current session from local history (server-side data untouched) |

---

## Search & branching

| Command | Description |
|---|---|
| `/search <query>` | Full-text search across all past sessions with highlighted snippets |
| `/branch` | Fork this conversation at the current point into a new independent session |
| `/branches` | List all forks (and siblings) of this session |
| `/title <text>` | Rename the current session |

FTS5 boolean syntax is supported in `/search`:

```
/search pods AND NOT staging
/search "oom killed" OR "crash loop"
/search deployment AND rollback
```

---

## Token usage

| Command | Description |
|---|---|
| `/tokens` | Show token counts and estimated cost for this session |
| `/cost` | Alias for `/tokens` |

See [Token Tracking](token-tracking.md) for details.

---

## Human-in-the-Loop

| Command | Description |
|---|---|
| `/approve` | Approve a pending action — the AI executes it |
| `/deny` | Deny a pending action — nothing is applied |

The prompt changes to `HITL>` while an action is pending. See [Human-in-the-Loop](hitl.md) for details.

---

## Keyboard shortcuts

| Key | Action |
|---|---|
| `Enter` | Send message |
| `Alt+Enter` or `Esc` → `Enter` | Insert newline (multi-line input) |
| `Tab` | Auto-complete slash commands |
| `↑` / `↓` | Scroll through input history |
| `Ctrl+C` | Cancel current input |
| `Ctrl+D` | Exit the session |
