# Configuration

kube-q loads configuration from `.env` files and environment variables. CLI flags override everything.

## Priority order

```
CLI flag  >  shell env var  >  ./.env  >  ~/.kube-q/.env  >  built-in default
```

---

## .env file locations

| Location | Priority | Use case |
|---|---|---|
| `~/.kube-q/.env` | lower | Persistent user-level defaults across all clusters |
| `./.env` (current directory) | higher | Per-project or per-cluster overrides |

Shell-exported variables always win over `.env` files. You can mix both — common settings in `~/.kube-q/.env`, cluster-specific overrides in `./.env`.

---

## All variables

```bash
# ── Connection ────────────────────────────────────────────────────────────────
KUBE_Q_URL=http://localhost:8000        # kube-q API base URL
KUBE_Q_API_KEY=                         # Bearer token (required when server auth is enabled)
KUBE_Q_MODEL=kubeintellect-v2           # Model name sent in requests

# ── Timeouts (seconds) ────────────────────────────────────────────────────────
KUBE_Q_TIMEOUT=120                      # Per-query HTTP timeout
KUBE_Q_HEALTH_TIMEOUT=5                 # Health-check HTTP timeout
KUBE_Q_NAMESPACE_TIMEOUT=3             # Namespace fetch timeout
KUBE_Q_STARTUP_RETRY_TIMEOUT=300       # How long to retry on startup before giving up
KUBE_Q_STARTUP_RETRY_INTERVAL=5        # Seconds between startup retries

# ── Output ────────────────────────────────────────────────────────────────────
KUBE_Q_STREAM=true                      # Enable/disable streaming responses
KUBE_Q_OUTPUT=rich                      # rich | plain
KUBE_Q_LOG_LEVEL=INFO                   # DEBUG | INFO | WARNING | ERROR
KUBE_Q_SKIP_HEALTH_CHECK=false          # Skip startup health-check loop

# ── Display names ─────────────────────────────────────────────────────────────
KUBE_Q_USER_NAME=You                    # Your display name in the prompt
KUBE_Q_AGENT_NAME=kube-q               # Assistant name in saved conversations

# ── Custom branding ───────────────────────────────────────────────────────────
KUBE_Q_LOGO=KubeIntellect               # Custom ASCII banner logo (\\n for newlines)
KUBE_Q_TAGLINE=© 2025 Acme Corp        # Custom tagline / copyright line

# ── Token cost overrides ──────────────────────────────────────────────────────
KUBE_Q_COST_PER_1K_PROMPT=0.003        # Override prompt token cost rate
KUBE_Q_COST_PER_1K_COMPLETION=0.006    # Override completion token cost rate
```

---

## Quick setup

### Minimal (user-level)

```bash
mkdir -p ~/.kube-q
cat > ~/.kube-q/.env <<'EOF'
KUBE_Q_URL=https://kube-q.example.com
KUBE_Q_API_KEY=your-api-key
EOF
```

### Per-cluster override

Create `.env` in your cluster's working directory:

```bash
# .env
KUBE_Q_URL=https://kube-q.prod.example.com
KUBE_Q_API_KEY=prod-key
KUBE_Q_USER_NAME=alice
KUBE_Q_MODEL=kubeintellect-v2
```

Run `kq` from that directory — it picks up the overrides automatically.

### Multiple clusters

```
~/clusters/
  prod/.env        → KUBE_Q_URL=https://kube-q.prod.example.com
  staging/.env     → KUBE_Q_URL=https://kube-q.staging.example.com
  dev/.env         → KUBE_Q_URL=http://localhost:8000
```

---

## Custom branding

Operators can replace the startup banner and tagline:

```bash
# .env
KUBE_Q_LOGO=KubeIntellect\nPowered by AI
KUBE_Q_TAGLINE=© 2025 Acme Corp — Internal Use Only
```

Use `\n` for line breaks in the logo. Set `KUBE_Q_LOGO=` (empty) to suppress the logo entirely.

---

## Files written by kube-q

| Path | Description |
|---|---|
| `~/.kube-q/.env` | User config (you create this) |
| `~/.kube-q/user-id` | Auto-generated persistent user ID (`0600` permissions) |
| `~/.kube-q/history.db` | SQLite session history database |
| `~/.kube-q/kube-q.log` | Rotating log (5 MB × 3 files, written in `--debug` mode) |
