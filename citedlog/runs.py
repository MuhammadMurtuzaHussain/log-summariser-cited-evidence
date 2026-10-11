"""A run is one model reply, kept exactly as received, plus how it was produced.

Run files hold what the model said. They do not hold the verdicts: those are
worked out again every time from the run and the log, so an improved verifier
can re-judge old runs without calling the model again.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .backends import Reply
from .briefing import parse_briefing
from .demo_scripts import SCRIPTS
from .logfile import Log
from .prompt import DEFAULT_PROMPT, prompt_sha256, prompt_version_for
from .verify import score_run, verify_run

RUN_SCHEMA = 1
DEMO_CREATED = "2026-10-09T00:00:00+00:00"  # fixed so the committed demo runs never drift


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", text.lower()).strip("-")


def make_run(reply: Reply, log: Log, *, demo_name: str | None = None, prompt_version: str = DEFAULT_PROMPT) -> dict:
    claims, parse_error = parse_briefing(reply.text)
    if reply.source == "scripted":
        run_id = f"demo-{demo_name}"
        label = SCRIPTS[demo_name]["label"]
        created = DEMO_CREATED
    else:
        created = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        stamp = created[:19].replace("-", "").replace(":", "").replace("T", "-")
        run_id = f"{stamp}-{_slug(reply.model)}"
        # The default prompt keeps the bare model name; any other prompt is named in the label,
        # so two runs of one model stay distinguishable on the tabs.
        label = reply.model if prompt_version == DEFAULT_PROMPT else f"{reply.model} (prompt {prompt_version})"
    run = {
        "schema": RUN_SCHEMA,
        "id": run_id,
        "label": label,
        "source": reply.source,
        "model": reply.model,
        "created": created,
        "elapsed_s": reply.elapsed_s,
        "options": reply.options,
        "log": {"name": log.name, "sha256": log.sha256, "lines": len(log)},
        "prompt_sha256": prompt_sha256(log, "v1" if reply.source == "scripted" else prompt_version),
        "parse_error": parse_error,
        "claims": claims,
        "raw_response": reply.text,
    }
    if reply.source != "scripted":
        run["prompt_version"] = prompt_version
    return run


def prompt_version_of(run: dict, log: Log) -> str | None:
    """The prompt version of a run: as recorded, else worked out from its prompt hash."""
    return run.get("prompt_version") or prompt_version_for(run.get("prompt_sha256", ""), log)


def save_run(run: dict, directory: str | Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{run['id']}.json"
    path.write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_run(path: str | Path) -> dict:
    run = json.loads(Path(path).read_text(encoding="utf-8"))
    if run.get("schema") != RUN_SCHEMA:
        raise ValueError(f"{path}: unsupported run schema {run.get('schema')!r}")
    return run


def load_runs(directory: str | Path, log: Log) -> tuple[list[dict], list[str]]:
    """All runs made against this exact log, newest model runs first, scripted demos last."""
    runs, skipped = [], []
    for path in sorted(Path(directory).glob("*.json")):
        try:
            run = load_run(path)
        except (ValueError, json.JSONDecodeError) as err:
            skipped.append(f"{path.name}: {err}")
            continue
        if run["log"]["sha256"] != log.sha256:
            skipped.append(f"{path.name}: made against a different log, so its line numbers mean nothing here")
            continue
        runs.append(run)
    real = sorted((r for r in runs if r["source"] != "scripted"), key=lambda r: r["created"], reverse=True)
    demos = sorted((r for r in runs if r["source"] == "scripted"), key=lambda r: r["id"])
    return real + demos, skipped


# ------------------------------------------------------------------ assessment


def assess(run: dict, log: Log, truth: dict | None) -> dict:
    """Verdicts, scores and the one-paragraph reading for a run."""
    verdicts = verify_run(run["claims"], log)
    score = score_run(run["claims"], verdicts, log, truth or {"events": [], "routine_lines": []})
    return {"verdicts": verdicts, "score": score, "hero": hero_text(run, score)}


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _join(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def hero_text(run: dict, score: dict) -> str:
    """The reading of a run, built only from its numbers."""
    name = run["label"]
    if run.get("parse_error"):
        return f"{name} returned a reply that could not be read as a briefing, so there is nothing to check."
    n = score["facts"]
    if n == 0:
        return f"{name} made no claims about the log."
    s = score["by_status"]
    if s["verified"] == n:
        first = f"All {n} claims are backed by the lines they cite."
    else:
        parts = [
            f"{s['verified']} is backed by the lines it cites"
            if s["verified"] == 1
            else f"{s['verified']} are backed by the lines they cite"
        ]
        if s["unsupported"]:
            parts.append(
                f"{s['unsupported']} cite{'s' if s['unsupported'] == 1 else ''} real lines that do not back them"
            )
        if s["invalid"]:
            parts.append(f"{s['invalid']} {'has' if s['invalid'] == 1 else 'have'} a broken citation")
        if s["unchecked"]:
            parts.append(
                f"{s['unchecked']} name{'s' if s['unchecked'] == 1 else ''} nothing the checker can test"
            )
        first = f"{name} made {n} claims. {_join(parts)}."
    if score["events_total"] == 0:
        return first
    found, total = score["events_found"], score["events_total"]
    events = f"all {total}" if found == total else f"{found} of the {total}"
    second = f" It found {events} planted events"
    if score["over_read"]:
        k = len(score["over_read"])
        second += f" and read routine activity as an attack in {_count(k, 'claim', 'claims')}"
    return first + second + "."
