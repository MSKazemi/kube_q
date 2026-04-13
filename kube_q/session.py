# Re-export shim — real implementations are in kube_q.cli.repl and kube_q.core.session
from kube_q.cli.repl import run_repl  # noqa: F401
from kube_q.core.session import (  # noqa: F401
    SessionState,
    load_or_create_user_id as _load_or_create_user_id,
    resolve_attachments as _resolve_attachments,
)

# Legacy names exported for any callers that import from kube_q.session
from kube_q.cli.renderer import _print_sessions_table  # noqa: F401
