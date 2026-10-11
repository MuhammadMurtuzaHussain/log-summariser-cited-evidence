"""Where the briefing text comes from: a local Ollama model, or a scripted demo.

Only the Python standard library is used. The Ollama call is a single request to
`/api/chat` with a JSON schema in `format`, so the server constrains the reply
to the claim structure. Nothing leaves the machine unless `--host` points elsewhere.
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .demo_scripts import SCRIPTS
from .prompt import SCHEMA

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"


class BackendError(RuntimeError):
    """Something the user can fix: Ollama is not running, or the model is not pulled."""


@dataclass
class Reply:
    text: str
    model: str
    source: str  # "ollama" or "scripted"
    elapsed_s: float | None = None
    options: dict = field(default_factory=dict)


def resolve_host(host: str | None) -> str:
    host = host or os.environ.get("OLLAMA_HOST") or DEFAULT_HOST
    if not host.startswith(("http://", "https://")):
        host = "http://" + host
    return host.rstrip("/")


def ollama_chat(
    model: str,
    system: str,
    user: str,
    *,
    host: str | None = None,
    temperature: float = 0.0,
    seed: int = 7,
    num_ctx: int = 8192,
    timeout: float = 600.0,
) -> Reply:
    base = resolve_host(host)
    options = {"temperature": temperature, "seed": seed, "num_ctx": num_ctx}
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": SCHEMA,
            "options": options,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        base + "/api/chat", data=body, headers={"Content-Type": "application/json"}
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as err:
        detail = ""
        try:
            detail = json.loads(err.read().decode("utf-8")).get("error", "")
        except (ValueError, UnicodeDecodeError):
            pass
        if err.code == 404:
            raise BackendError(
                f"Ollama does not have the model '{model}'. Run: ollama pull {model}"
                + (f" ({detail})" if detail else "")
            ) from err
        raise BackendError(f"Ollama returned HTTP {err.code}. {detail}".strip()) from err
    except (urllib.error.URLError, ConnectionError) as err:
        if isinstance(getattr(err, "reason", None), (socket.timeout, TimeoutError)):
            raise BackendError(f"Ollama did not answer within {timeout:.0f} s.") from err
        raise BackendError(
            f"Could not reach Ollama at {base}. Start the Ollama app (or run `ollama serve`), "
            f"then `ollama pull {model}`."
        ) from err
    except (socket.timeout, TimeoutError) as err:
        raise BackendError(f"Ollama did not answer within {timeout:.0f} s.") from err

    if isinstance(payload, dict) and payload.get("error"):
        raise BackendError(f"Ollama said: {payload['error']}")
    try:
        text = payload["message"]["content"]
    except (KeyError, TypeError) as err:
        raise BackendError("Ollama's reply had no message content.") from err
    return Reply(text, model, "ollama", round(time.monotonic() - started, 1), options)


def scripted(name: str) -> Reply:
    if name not in SCRIPTS:
        raise BackendError(f"No scripted demo called '{name}'. Choose from: {', '.join(SCRIPTS)}")
    text = json.dumps({"claims": SCRIPTS[name]["claims"]}, indent=2)
    return Reply(text, f"scripted:{name}", "scripted", None, {})
