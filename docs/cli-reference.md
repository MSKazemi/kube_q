# CLI Reference

```
kq [options]
```

---

## Flags

| Flag | Default | Description |
|---|---|---|
| `--url URL` | `http://localhost:8000` | kube-q API base URL (env: `KUBE_Q_URL`) |
| `--query TEXT` / `-q TEXT` | — | Run a single query and exit (non-interactive) |
| `--no-stream` | off | Disable streaming — wait for full response |
| `--session-id ID` | — | Resume a previous session by ID (loads history from local store) |
| `--list` | — | List recent sessions and exit |
| `--search QUERY` | — | Full-text search across session history and exit |
| `--user-id ID` | auto | Persistent user ID (saved to `~/.kube-q/user-id`) |
| `--api-key KEY` | — | Bearer token for auth-enabled servers (env: `KUBE_Q_API_KEY`) |
| `--ca-cert PATH` | — | Custom CA certificate bundle for TLS verification |
| `--output {rich,plain}` | `rich` | `rich` for markdown rendering; `plain` for pipe-friendly raw text |
| `--model NAME` | `kubeintellect-v2` | Model name sent in requests (env: `KUBE_Q_MODEL`) |
| `--user-name NAME` | `You` | Your display name in the prompt (env: `KUBE_Q_USER_NAME`) |
| `--agent-name NAME` | `kube-q` | Assistant name in saved conversations (env: `KUBE_Q_AGENT_NAME`) |
| `--no-banner` / `--quiet` | off | Suppress logo and header (useful for screen recordings) |
| `--no-health-check` | off | Skip startup health-check retry loop (env: `KUBE_Q_SKIP_HEALTH_CHECK`) |
| `--debug` / `--verbose` | off | Log raw HTTP requests/responses to stderr and `~/.kube-q/kube-q.log` |
| `--version` | — | Print version and exit |

---

## Examples

### Interactive REPL

```bash
# Connect to local backend (default)
kq

# Connect to remote backend
kq --url https://kube-q.example.com

# With API key
kq --url https://kube-q.example.com --api-key my-secret-key

# Custom display names
kq --user-name Alice --agent-name KubeBot

# Skip the startup health check (faster start when server is known-good)
kq --no-health-check
```

### Single-query mode

```bash
# Print response and exit
kq --query "show all pods in the default namespace"

# Pipe-friendly plain text
kq --query "list failing deployments" --output plain

# Combine with jq or other tools
kq --query "show pod names" --output plain | grep "crash"
```

### Session management

```bash
# List the 20 most recent sessions
kq --list

# Resume a session by ID (shown in --list output)
kq --session-id abc123

# Search across all past sessions
kq --search "deployment rollback"
kq --search "pods AND crash AND NOT staging"
```

### Debugging

```bash
# Log raw HTTP traffic to stderr + ~/.kube-q/kube-q.log
kq --debug

# Custom CA cert (corporate proxies, self-signed certs)
kq --url https://internal.example.com --ca-cert /etc/ssl/my-ca.pem
```

---

## Environment variables

All flags can be set via environment variables. See [Configuration](configuration.md) for the full list.

```bash
export KUBE_Q_URL=https://kube-q.example.com
export KUBE_Q_API_KEY=my-key
kq
```
