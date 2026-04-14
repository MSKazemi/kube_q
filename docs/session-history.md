# Session History

kube-q saves every conversation to a local SQLite database at `~/.kube-q/history.db`. Nothing is sent to or stored on the server — this is a local-only mirror. The database never affects your cluster.

---

## Listing sessions

```bash
kq --list
```

Shows the 20 most recent sessions with ID, title, message count, token total, and last-used time. Inside the REPL, `/sessions` does the same.

---

## Resuming a session

```bash
kq --session-id <id>
```

Loads the full message history for that session and continues the conversation from where you left off. The session ID is shown in `kq --list` output.

---

## Full-text search

```bash
kq --search "deployment rollback"
kq --search "pods AND crash"
kq --search "oom killed OR crash loop"
```

Powered by SQLite FTS5. Results show session title, matched message excerpt with highlighted terms, and the session ID. Supports FTS5 boolean syntax:

| Syntax | Meaning |
|---|---|
| `pods crash` | both words anywhere |
| `pods AND crash` | both words (explicit) |
| `pods OR crash` | either word |
| `pods NOT staging` | pods but not staging |
| `"crash loop"` | exact phrase |

Inside the REPL: `/search <query>` works the same way.

---

## Conversation branching

```
/branch
```

Forks the current conversation at the current message count into a new independent session. The original session is never modified — you get a clean fork you can take in a different direction.

```
/branches        — list all forks of (and siblings of) this session
/title <text>    — rename the current session
```

Branches show up in `kq --list` as regular sessions. Search finds them automatically.

---

## Deleting a session

```
/forget
```

Deletes the current session from local history. Server-side state (if any) is not affected.

---

## Database details

| Property | Value |
|---|---|
| Path | `~/.kube-q/history.db` |
| Format | SQLite 3, WAL mode |
| Schema version | v3 (auto-migrates from v1 and v2) |
| What's stored | Session metadata, messages, token counts, FTS index |
| What's NOT stored | Cluster credentials, API keys, server state |

Schema migrations run automatically at startup — old databases from v1.0.0 are upgraded transparently.
