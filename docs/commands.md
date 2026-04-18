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

## Kubernetes context

| Command | Description |
|---|---|
| `/context <name>` | Set active kubectl context — prepended to every query as `[context: kube_context=X]` |
| `/context` | Clear the active context |

Context names Tab-complete from your kubeconfig (`kubectl config get-contexts`). If `kubectl` isn't installed, kube-q falls back to a minimal YAML scan of `~/.kube/config` or `$KUBECONFIG`.

Set it at launch with `--context <name>` or `KUBE_Q_CONTEXT=<name>`.

---

## Profiles & plugins

| Command | Description |
|---|---|
| `/profile` | List profiles in `~/.kube-q/profiles/` and show which one is active |
| `/profile <name>` | Print the restart command for the named profile (profile switching requires a restart) |
| `/plugins` | List slash commands registered by plugins in `~/.kube-q/plugins/` |

Profiles are `.env` fragments that bundle backend + keys + kubectl context per environment — see [Configuration](configuration.md#profiles-per-cluster) for details. Plugins are Python files that register extra slash commands — see [Configuration](configuration.md#plugins).

---

## Session history

| Command | Description |
|---|---|
| `/sessions` | Open an interactive picker of the 20 most recent sessions — use **↑/↓** to navigate, **Enter** to resume in place (stored transcript is re-rendered **and the session's kube context is restored**), **Esc** to cancel |
| `/resume` | Alias for `/sessions` |
| `/history` | Replay messages in the **current** session on demand (all by default) |
| `/history <N>` | Show the last **N** messages |
| `/history <X-Y>` | Show messages **X** through **Y** (1-indexed, inclusive) |
| `/history #<N>` | Show just message **#N** |
| `/forget` | Delete the current session from local history (server-side data untouched) |

Each replayed message is prefixed with `[#N]` so you can reference it — e.g. `/history #4` jumps straight to message 4.

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
