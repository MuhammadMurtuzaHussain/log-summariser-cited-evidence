"""Turn a model's raw reply into a list of claims, without correcting anything.

Parsing is deliberately forgiving about packaging (code fences, chatter around
the JSON) and deliberately silent about content: a wrong line number stays
wrong, so the verifier sees exactly what the model said.
"""

from __future__ import annotations

import json
import re

KINDS = ("headline", "finding", "action")
SEVERITIES = ("info", "suspicious", "malicious")


def _loads(text: str):
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


def parse_briefing(raw: str) -> tuple[list[dict], str | None]:
    """Return (claims, parse_error). On failure the claims list is empty."""
    try:
        data = _loads(raw)
    except (json.JSONDecodeError, ValueError) as err:
        return [], f"The reply is not valid JSON ({err.__class__.__name__}: {err})."
    items = data.get("claims") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return [], 'The JSON has no "claims" list.'

    claims = []
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind") if item.get("kind") in KINDS else "finding"
        severity = item.get("severity") if item.get("severity") in SEVERITIES else "info"
        claims.append(
            {
                "id": f"C{len(claims) + 1}",
                "kind": kind,
                "severity": severity,
                "text": str(item.get("text", "")).strip(),
                "lines": item.get("lines"),
            }
        )
    if not claims:
        return [], "The JSON holds no claims."
    return claims, None
