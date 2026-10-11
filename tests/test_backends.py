import json

import pytest

from citedlog.backends import BackendError, ollama_chat, resolve_host, scripted
from citedlog.prompt import SCHEMA, SYSTEM, user_message

CANNED = {"message": {"role": "assistant", "content": '{"claims": []}'}, "done": True}


def test_request_shape(fake_ollama, log):
    with fake_ollama(body=CANNED) as server:
        reply = ollama_chat("llama3.2", SYSTEM, user_message(log), host=server.url, temperature=0.2, seed=3)
    assert reply.text == '{"claims": []}' and reply.source == "ollama" and reply.model == "llama3.2"
    (request,) = server.requests
    body = request["json"]
    assert request["path"] == "/api/chat"
    assert body["model"] == "llama3.2" and body["stream"] is False
    assert body["format"] == SCHEMA
    assert body["options"] == {"temperature": 0.2, "seed": 3, "num_ctx": 8192}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert body["messages"][0]["content"] == SYSTEM
    user = body["messages"][1]["content"]
    assert "(50 lines)" in user and "[1] Oct  7 06:58:12" in user and "[50] Oct  7 14:33:40" in user
    assert "[0]" not in user and "[51]" not in user


def test_model_not_pulled_says_how_to_fix_it(fake_ollama):
    with fake_ollama(status=404, body={"error": "model 'nope' not found"}) as server:
        with pytest.raises(BackendError, match="ollama pull nope"):
            ollama_chat("nope", "s", "u", host=server.url)


def test_error_payload_is_reported(fake_ollama):
    with fake_ollama(body={"error": "out of memory"}) as server:
        with pytest.raises(BackendError, match="out of memory"):
            ollama_chat("m", "s", "u", host=server.url)


def test_reply_without_content_is_reported(fake_ollama):
    with fake_ollama(body={"done": True}) as server:
        with pytest.raises(BackendError, match="no message content"):
            ollama_chat("m", "s", "u", host=server.url)


def test_server_not_running_says_how_to_start_it():
    with pytest.raises(BackendError, match="Could not reach Ollama.*ollama serve"):
        ollama_chat("m", "s", "u", host="http://127.0.0.1:9", timeout=2)


def test_slow_server_times_out_with_a_clear_message(fake_ollama):
    with fake_ollama(body=CANNED, delay=1.0) as server:
        with pytest.raises(BackendError, match="did not answer"):
            ollama_chat("m", "s", "u", host=server.url, timeout=0.2)


def test_host_resolution(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert resolve_host(None) == "http://localhost:11434"
    assert resolve_host("127.0.0.1:11500/") == "http://127.0.0.1:11500"
    monkeypatch.setenv("OLLAMA_HOST", "box.lan:11434")
    assert resolve_host(None) == "http://box.lan:11434"


def test_scripted_backend_returns_json_the_parser_can_read():
    from citedlog.briefing import parse_briefing

    reply = scripted("sloppy")
    assert reply.source == "scripted" and reply.elapsed_s is None
    claims, err = parse_briefing(reply.text)
    assert err is None and len(claims) == 13
    with pytest.raises(BackendError):
        scripted("nope")


def test_the_prompt_asks_for_what_the_verifier_checks():
    assert "backticks" in SYSTEM and "line numbers" in SYSTEM and "equal the number of cited lines" in SYSTEM
    assert json.dumps(SCHEMA)  # serialisable
    assert SCHEMA["properties"]["claims"]["items"]["required"] == ["kind", "severity", "text", "lines"]
