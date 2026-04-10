"""
cli_transport.py — HTTP communication: SSE streaming, non-streaming query, health check.
"""

import json
import logging
import time

import httpx
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.text import Text

from kube_q.render import console, print_response, _plain_output

# ── Retry config ───────────────────────────────────────────────────────────────
_QUERY_RETRY_DELAYS = (2, 5, 10)  # seconds between attempts (3 total)

# ── Module logger ──────────────────────────────────────────────────────────────
_logger = logging.getLogger(__name__)

# ── Debug mode (set by main via set_debug) ────────────────────────────────────
_debug: bool = False


def set_debug(enabled: bool) -> None:
    """Enable/disable debug HTTP logging (raw request/response to stderr + log file)."""
    global _debug
    _debug = enabled


# ── Error helpers ──────────────────────────────────────────────────────────────

def _describe_error(url: str, exc: Exception) -> str:
    """Return a human-readable reason for a connection failure."""
    if isinstance(exc, httpx.ConnectError):
        msg = str(exc)
        if any(k in msg for k in ("Name or service not known", "nodename nor servname", "getaddrinfo")):
            host = url.split("//")[-1].split("/")[0]
            return f"DNS resolution failed for '{host}'"
        return f"Connection refused — nothing is listening at {url}"
    if isinstance(exc, httpx.TimeoutException):
        return "Request timed out — API did not respond in time"
    if isinstance(exc, httpx.ProxyError):
        return f"Proxy error: {exc}"
    if isinstance(exc, httpx.RemoteProtocolError):
        return f"Server closed the connection unexpectedly: {exc}"
    if isinstance(exc, httpx.NetworkError):
        return f"Network error: {exc}"
    return f"Unexpected error: {exc}"


# ── Debug event hooks ─────────────────────────────────────────────────────────

def _hook_request(request: httpx.Request) -> None:
    safe_headers = {k: v for k, v in request.headers.items() if k.lower() != "authorization"}
    body = request.content.decode("utf-8", errors="replace")
    _logger.debug("→ %s %s  headers=%s", request.method, request.url, safe_headers)
    if body:
        _logger.debug("  body=%s", body[:4000])


def _hook_response(response: httpx.Response) -> None:
    _logger.debug("← %d %s", response.status_code, response.url)


# ── Shared request builders ────────────────────────────────────────────────────

def _make_client(ca_cert: str | None, timeout: float = 120.0) -> httpx.Client:
    hooks: dict = {"request": [_hook_request], "response": [_hook_response]} if _debug else {}
    return httpx.Client(timeout=timeout, verify=ca_cert if ca_cert else True, event_hooks=hooks)


def _request_headers(
    user_id: str,
    conversation_id: str,
    api_key: str | None,
    *,
    accept: str | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {"X-User-ID": user_id, "X-Session-ID": conversation_id}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if accept:
        headers["Accept"] = accept
    return headers


def _build_payload(
    messages: list[dict],
    conversation_id: str,
    user_id: str,
    stream: bool,
    pending_action_id: str | None,
) -> dict:
    payload: dict = {
        "model": "gpt-3.5-turbo",
        "messages": messages,
        "stream": stream,
        "conversation_id": conversation_id,
        "user_id": user_id,
    }
    if pending_action_id:
        payload["action_id"] = pending_action_id
    return payload


# ── SSE helpers ────────────────────────────────────────────────────────────────

def _iter_sse(response: httpx.Response):
    """Yield parsed SSE data objects. Handles multi-line data and [DONE] sentinel."""
    buffer = ""
    for raw_chunk in response.iter_text():
        buffer += raw_chunk
        while "\n\n" in buffer:
            block, buffer = buffer.split("\n\n", 1)
            for line in block.splitlines():
                if line.startswith("data:"):
                    payload = line[len("data:"):].strip()
                    if payload == "[DONE]":
                        return
                    try:
                        yield json.loads(payload)
                    except json.JSONDecodeError:
                        pass


def _stream_once(
    url: str,
    payload: dict,
    headers: dict,
    client: httpx.Client,
) -> tuple[str, bool, str | None]:
    """One streaming attempt. Raises httpx.TransportError on connection failure."""
    full_text = ""
    hitl_pending = False
    action_id: str | None = None
    t0 = time.monotonic()

    with Live(
        Spinner("dots", text=Text(" kube-q is thinking…", style="cyan")),
        console=console,
        refresh_per_second=12,
        transient=True,
    ) as live:
        with client.stream("POST", f"{url}/v1/chat/completions",
                           json=payload, headers=headers) as resp:
            if resp.status_code != 200:
                body = resp.read().decode()
                live.stop()
                console.print(f"[red][HTTP {resp.status_code}] {body}[/red]")
                return "", False, None

            first_token = True
            for event in _iter_sse(resp):
                choices = event.get("choices", [])
                if not choices:
                    continue
                choice = choices[0]
                content = choice.get("delta", {}).get("content", "")
                finish = choice.get("finish_reason")
                if content:
                    if first_token:
                        # Spinner disappears; switch to persistent live rendering
                        live.transient = False
                        first_token = False
                    full_text += content
                    live.update(Markdown(full_text) if not _plain_output else Text(full_text))
                if finish == "stop":
                    if choice.get("hitl_required"):
                        hitl_pending = True
                        action_id = choice.get("action_id")
                    elif "🛑" in full_text:
                        hitl_pending = True
                        console.print(
                            "[dim]Warning: HITL triggered via emoji fallback "
                            "— server should be upgraded to send hitl_required.[/dim]"
                        )

    elapsed = time.monotonic() - t0
    if full_text:
        # Content already rendered live above; print elapsed footer
        console.print(f"[bold cyan]kube-q[/bold cyan]  [dim]({elapsed:.1f}s)[/dim]")
        console.print()
    return full_text, hitl_pending, action_id


# ── Public query functions ─────────────────────────────────────────────────────

def stream_query(
    url: str,
    messages: list[dict],
    conversation_id: str,
    user_id: str,
    pending_action_id: str | None = None,
    *,
    api_key: str | None = None,
    ca_cert: str | None = None,
    timeout: float = 120.0,
) -> tuple[str, bool, str | None]:
    """Send a streaming chat request. Returns (full_text, hitl_pending, action_id)."""
    payload = _build_payload(messages, conversation_id, user_id, True, pending_action_id)
    headers = _request_headers(user_id, conversation_id, api_key, accept="text/event-stream")
    _logger.info("stream_query conversation=%s user=%s url=%s", conversation_id, user_id, url)

    with _make_client(ca_cert, timeout=timeout) as client:
        for attempt in range(len(_QUERY_RETRY_DELAYS) + 1):
            if attempt > 0:
                delay = _QUERY_RETRY_DELAYS[attempt - 1]
                console.print(
                    f"[dim]  Retrying in {delay}s… "
                    f"(attempt {attempt}/{len(_QUERY_RETRY_DELAYS)})[/dim]"
                )
                time.sleep(delay)
            try:
                return _stream_once(url, payload, headers, client)
            except httpx.TransportError as exc:
                reason = _describe_error(url, exc)
                if attempt == 0:
                    console.print(f"\n[red]Disconnected:[/red] {reason}")
                else:
                    console.print(f"[dim]    → {reason}[/dim]")

    console.print(
        "[red]  All retries failed.[/red] "
        "[dim]Check your connection and API URL, then try again.[/dim]"
    )
    return "", False, None


def non_stream_query(
    url: str,
    messages: list[dict],
    conversation_id: str,
    user_id: str,
    pending_action_id: str | None = None,
    *,
    api_key: str | None = None,
    ca_cert: str | None = None,
    timeout: float = 120.0,
) -> tuple[str, bool, str | None]:
    """Send a non-streaming chat request. Returns (response_text, hitl_pending, action_id)."""
    payload = _build_payload(messages, conversation_id, user_id, False, pending_action_id)
    headers = _request_headers(user_id, conversation_id, api_key)
    _logger.info("non_stream_query conversation=%s user=%s url=%s", conversation_id, user_id, url)

    with _make_client(ca_cert, timeout=timeout) as client:
        for attempt in range(len(_QUERY_RETRY_DELAYS) + 1):
            if attempt > 0:
                delay = _QUERY_RETRY_DELAYS[attempt - 1]
                console.print(
                    f"[dim]  Retrying in {delay}s… "
                    f"(attempt {attempt}/{len(_QUERY_RETRY_DELAYS)})[/dim]"
                )
                time.sleep(delay)
            try:
                t0 = time.monotonic()
                resp = client.post(
                    f"{url}/v1/chat/completions", json=payload, headers=headers
                )
                elapsed = time.monotonic() - t0

                if resp.status_code != 200:
                    console.print(f"[red][HTTP {resp.status_code}] {resp.text}[/red]")
                    return "", False, None

                try:
                    data = resp.json()
                    _logger.debug("non_stream response body=%s", resp.text[:4000])
                except json.JSONDecodeError as e:
                    console.print(f"[red]Invalid JSON from server: {e}[/red]")
                    _logger.error("non_stream invalid JSON: %s — body=%s", e, resp.text[:500])
                    return "", False, None

                try:
                    choice_data = data["choices"][0]
                    text = choice_data["message"]["content"]
                except (KeyError, IndexError) as e:
                    console.print(
                        f"[red]Unexpected response structure (missing {e}): {data}[/red]"
                    )
                    return "", False, None

                hitl_pending = choice_data.get("hitl_required", False)
                action_id = choice_data.get("action_id") if hitl_pending else None

                if not hitl_pending and "🛑" in text:
                    hitl_pending = True
                    console.print(
                        "[dim]Warning: HITL triggered via emoji fallback "
                        "— server should be upgraded to send hitl_required.[/dim]"
                    )

                console.print(
                    f"[bold cyan]kube-q:[/bold cyan]  [dim]({elapsed:.1f}s)[/dim]"
                )
                print_response(text)
                return text, hitl_pending, action_id

            except httpx.TransportError as exc:
                reason = _describe_error(url, exc)
                if attempt == 0:
                    console.print(f"\n[red]Disconnected:[/red] {reason}")
                else:
                    console.print(f"[dim]    → {reason}[/dim]")

    console.print(
        "[red]  All retries failed.[/red] "
        "[dim]Check your connection and API URL, then try again.[/dim]"
    )
    return "", False, None


# ── Health check ──────────────────────────────────────────────────────────────

def check_health(
    url: str,
    *,
    api_key: str | None = None,
    ca_cert: str | None = None,
    timeout: float = 5.0,
) -> tuple[bool, str]:
    """Check API reachability. Returns (ok, reason)."""
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    _logger.debug("check_health url=%s", url)
    try:
        with _make_client(ca_cert, timeout=timeout) as client:
            r = client.get(f"{url}/healthz", headers=headers)
        if r.status_code == 200:
            return True, ""
        return False, f"HTTP {r.status_code} from {url}/healthz"
    except httpx.ConnectError as e:
        msg = str(e)
        if any(k in msg for k in ("Name or service not known", "nodename nor servname", "getaddrinfo")):
            host = url.split("//")[-1].split("/")[0]
            return False, f"DNS resolution failed for '{host}' — check the hostname or /etc/hosts"
        return False, f"Connection refused — nothing is listening at {url}"
    except httpx.TimeoutException:
        return False, f"Connection timed out — {url} did not respond within 5 s"
    except Exception as e:
        return False, f"Unexpected error: {e}"
