"""
Unit tests for kube_q/transport.py.

Covers: _describe_error, _build_payload, _request_headers, _iter_sse,
        check_health, non_stream_query (success, HTTP error, JSON error,
        missing keys, HITL flag, HITL emoji fallback, transport retry).
"""

import json
from unittest.mock import patch

import httpx
import respx

from kube_q.transport import (
    _build_payload,
    _describe_error,
    _iter_sse,
    _request_headers,
    check_health,
    non_stream_query,
)

# ── _describe_error ────────────────────────────────────────────────────────────


def test_describe_error_connect_dns() -> None:
    exc = httpx.ConnectError("getaddrinfo failed for 'bad-host'")
    assert "DNS resolution failed" in _describe_error("http://bad-host", exc)


def test_describe_error_connect_refused() -> None:
    exc = httpx.ConnectError("Connection refused")
    result = _describe_error("http://localhost:9999", exc)
    assert "Connection refused" in result


def test_describe_error_timeout() -> None:
    exc = httpx.ReadTimeout("timed out")
    assert "timed out" in _describe_error("http://localhost", exc).lower()


def test_describe_error_proxy() -> None:
    exc = httpx.ProxyError("bad proxy")
    assert "Proxy error" in _describe_error("http://localhost", exc)


def test_describe_error_network() -> None:
    exc = httpx.NetworkError("network failure")
    assert "Network error" in _describe_error("http://localhost", exc)


def test_describe_error_unknown() -> None:
    exc = ValueError("something weird")
    assert "Unexpected error" in _describe_error("http://localhost", exc)


# ── _build_payload ─────────────────────────────────────────────────────────────


def test_build_payload_no_action_id() -> None:
    messages = [{"role": "user", "content": "hello"}]
    payload = _build_payload(messages, "conv-1", "user-1", True, None)
    assert payload["messages"] is messages
    assert payload["stream"] is True
    assert payload["conversation_id"] == "conv-1"
    assert payload["user_id"] == "user-1"
    assert "action_id" not in payload


def test_build_payload_with_action_id() -> None:
    payload = _build_payload([], "conv-1", "user-1", False, "act-42")
    assert payload["stream"] is False
    assert payload["action_id"] == "act-42"


# ── _request_headers ──────────────────────────────────────────────────────────


def test_request_headers_minimal() -> None:
    h = _request_headers("u1", "c1", None)
    assert h["X-User-ID"] == "u1"
    assert h["X-Session-ID"] == "c1"
    assert "Authorization" not in h
    assert "Accept" not in h


def test_request_headers_with_api_key() -> None:
    h = _request_headers("u1", "c1", "secret-key")
    assert h["Authorization"] == "Bearer secret-key"


def test_request_headers_with_accept() -> None:
    h = _request_headers("u1", "c1", None, accept="text/event-stream")
    assert h["Accept"] == "text/event-stream"


# ── _iter_sse ─────────────────────────────────────────────────────────────────


class _FakeResponse:
    """Minimal httpx.Response stand-in that yields fixed text chunks."""

    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks

    def iter_text(self) -> list[str]:
        return self._chunks


def _sse_chunk(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def test_iter_sse_single_event() -> None:
    event = {"choices": [{"delta": {"content": "hello"}}]}
    resp = _FakeResponse([_sse_chunk(event)])
    events = list(_iter_sse(resp))  # type: ignore[arg-type]
    assert len(events) == 1
    assert events[0]["choices"][0]["delta"]["content"] == "hello"


def test_iter_sse_stops_at_done() -> None:
    event = {"choices": [{"delta": {"content": "hi"}}]}
    resp = _FakeResponse([_sse_chunk(event), "data: [DONE]\n\n"])
    events = list(_iter_sse(resp))  # type: ignore[arg-type]
    assert len(events) == 1  # [DONE] not yielded


def test_iter_sse_skips_malformed_json() -> None:
    bad = "data: not-json\n\n"
    good = _sse_chunk({"choices": []})
    resp = _FakeResponse([bad, good])
    events = list(_iter_sse(resp))  # type: ignore[arg-type]
    assert len(events) == 1  # malformed line skipped, good line yielded


def test_iter_sse_multiple_events() -> None:
    chunks = [_sse_chunk({"id": i}) for i in range(3)]
    resp = _FakeResponse(chunks)
    events = list(_iter_sse(resp))  # type: ignore[arg-type]
    assert [e["id"] for e in events] == [0, 1, 2]


def test_iter_sse_split_across_chunks() -> None:
    # The SSE block arrives in two separate read chunks
    full = _sse_chunk({"choices": [{"delta": {"content": "split"}}]})
    mid = len(full) // 2
    resp = _FakeResponse([full[:mid], full[mid:]])
    events = list(_iter_sse(resp))  # type: ignore[arg-type]
    assert len(events) == 1


# ── check_health ──────────────────────────────────────────────────────────────

BASE = "http://localhost:8000"


@respx.mock
def test_check_health_ok() -> None:
    respx.get(f"{BASE}/healthz").mock(return_value=httpx.Response(200))
    ok, reason = check_health(BASE)
    assert ok is True
    assert reason == ""


@respx.mock
def test_check_health_non_200() -> None:
    respx.get(f"{BASE}/healthz").mock(return_value=httpx.Response(503))
    ok, reason = check_health(BASE)
    assert ok is False
    assert "503" in reason


@respx.mock
def test_check_health_with_api_key() -> None:
    route = respx.get(f"{BASE}/healthz").mock(return_value=httpx.Response(200))
    check_health(BASE, api_key="tok")
    assert route.calls[0].request.headers["Authorization"] == "Bearer tok"


@respx.mock
def test_check_health_connect_error() -> None:
    respx.get(f"{BASE}/healthz").mock(side_effect=httpx.ConnectError("refused"))
    ok, reason = check_health(BASE)
    assert ok is False
    assert reason  # non-empty error string


@respx.mock
def test_check_health_timeout() -> None:
    respx.get(f"{BASE}/healthz").mock(side_effect=httpx.ReadTimeout("timeout"))
    ok, reason = check_health(BASE)
    assert ok is False
    assert "timed out" in reason.lower()


# ── non_stream_query ──────────────────────────────────────────────────────────

_MESSAGES = [{"role": "user", "content": "list pods"}]
_CONV_ID = "conv-abc"
_USER_ID = "user-xyz"


def _ok_body(text: str, hitl: bool = False, action_id: str | None = None) -> dict:
    choice: dict = {"message": {"content": text}, "finish_reason": "stop"}
    if hitl:
        choice["hitl_required"] = True
        choice["action_id"] = action_id
    return {"choices": [choice]}


@respx.mock
def test_non_stream_query_success() -> None:
    respx.post(f"{BASE}/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_ok_body("pod list here"))
    )
    text, hitl, action_id = non_stream_query(BASE, _MESSAGES, _CONV_ID, _USER_ID)
    assert text == "pod list here"
    assert hitl is False
    assert action_id is None


@respx.mock
def test_non_stream_query_http_error() -> None:
    respx.post(f"{BASE}/v1/chat/completions").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )
    text, hitl, action_id = non_stream_query(BASE, _MESSAGES, _CONV_ID, _USER_ID)
    assert text == ""
    assert hitl is False


@respx.mock
def test_non_stream_query_invalid_json() -> None:
    respx.post(f"{BASE}/v1/chat/completions").mock(
        return_value=httpx.Response(200, content=b"not-json")
    )
    text, hitl, _ = non_stream_query(BASE, _MESSAGES, _CONV_ID, _USER_ID)
    assert text == ""


@respx.mock
def test_non_stream_query_missing_keys() -> None:
    respx.post(f"{BASE}/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": []})  # empty choices
    )
    text, hitl, _ = non_stream_query(BASE, _MESSAGES, _CONV_ID, _USER_ID)
    assert text == ""


@respx.mock
def test_non_stream_query_hitl_flag() -> None:
    respx.post(f"{BASE}/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json=_ok_body("action pending", hitl=True, action_id="act-7")
        )
    )
    text, hitl, action_id = non_stream_query(BASE, _MESSAGES, _CONV_ID, _USER_ID)
    assert text == "action pending"
    assert hitl is True
    assert action_id == "act-7"


@respx.mock
def test_non_stream_query_hitl_emoji_fallback() -> None:
    respx.post(f"{BASE}/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_ok_body("needs approval 🛑"))
    )
    text, hitl, _ = non_stream_query(BASE, _MESSAGES, _CONV_ID, _USER_ID)
    assert hitl is True


@respx.mock
def test_non_stream_query_retry_then_succeed() -> None:
    """First attempt raises TransportError; second attempt succeeds."""
    respx.post(f"{BASE}/v1/chat/completions").mock(
        side_effect=[
            httpx.ConnectError("refused"),
            httpx.Response(200, json=_ok_body("ok on retry")),
        ]
    )
    with patch("kube_q.transport.time.sleep"):  # don't actually sleep
        text, hitl, _ = non_stream_query(BASE, _MESSAGES, _CONV_ID, _USER_ID)
    assert text == "ok on retry"


@respx.mock
def test_non_stream_query_all_retries_fail() -> None:
    """All attempts raise TransportError → returns empty string."""
    respx.post(f"{BASE}/v1/chat/completions").mock(
        side_effect=httpx.ConnectError("refused")
    )
    with patch("kube_q.transport.time.sleep"):
        text, hitl, _ = non_stream_query(BASE, _MESSAGES, _CONV_ID, _USER_ID)
    assert text == ""
