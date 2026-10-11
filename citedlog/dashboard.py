"""Build the dashboard: one HTML file with fonts, styles, script and data inlined."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from .docs import STATUS_TEXT
from .logfile import Log, format_lines
from .runs import assess, load_runs, prompt_version_of
from .scenario import TRUTH_NAME
from .verify import RULES

WEB = Path(__file__).resolve().parent / "web"
FONTS = {
    "{{FONT_SANS_400}}": "ibm-plex-sans-latin-400-normal.woff2",
    "{{FONT_SANS_600}}": "ibm-plex-sans-latin-600-normal.woff2",
    "{{FONT_MONO_400}}": "ibm-plex-mono-latin-400-normal.woff2",
    "{{FONT_MONO_500}}": "ibm-plex-mono-latin-500-normal.woff2",
}
STATUS_LABEL = {
    "verified": "Backed by the log",
    "unchecked": "Nothing to check",
    "unsupported": "Lines do not back it",
    "invalid": "Broken citation",
}
SCRIPT_NOTES = {
    "faithful": "Hand-written briefing that passes every check. It shows what a good result looks like. Not model output.",
    "sloppy": "Hand-written briefing with one example of each failure a small model tends to make. Not model output.",
}


def _safe_json(payload: dict) -> str:
    """JSON that cannot close the script tag it sits in or start an HTML comment."""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    for char, escape in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"), (" ", "\\u2028"), (" ", "\\u2029")):
        text = text.replace(char, escape)
    return text


def _payload(log: Log, truth: dict | None, runs: list[dict]) -> tuple[dict, list[dict]]:
    events = truth["events"] if truth else []
    by_line: dict[int, list[str]] = {}
    for event in events:
        for n in event["lines"]:
            by_line.setdefault(n, []).append(event["id"])

    out_runs, assessed_all = [], []
    for run in runs:
        assessed = assess(run, log, truth)
        assessed_all.append(assessed)
        claims = []
        for claim, verdict in zip(run["claims"], assessed["verdicts"]):
            claims.append(
                {**claim, "verdict": verdict.to_dict(), "over_read": claim["id"] in assessed["score"]["over_read"]}
            )
        note = ""
        if run["source"] == "scripted":
            note = SCRIPT_NOTES.get(run["id"].removeprefix("demo-"), "Hand-written briefing. Not model output.")
        out_runs.append(
            {
                "id": run["id"],
                "label": run["label"],
                "source": run["source"],
                "model": run["model"],
                "created": run["created"],
                "elapsed_s": run.get("elapsed_s"),
                "options": run.get("options") or {},
                "prompt_version": None if run["source"] == "scripted" else prompt_version_of(run, log),
                "parse_error": run.get("parse_error"),
                "note": note,
                "hero": assessed["hero"],
                "score": assessed["score"],
                "claims": claims,
            }
        )

    default = next((r["id"] for r in out_runs if r["source"] != "scripted"), None)
    default = default or next((r["id"] for r in out_runs if r["id"] == "demo-sloppy"), out_runs[0]["id"])
    payload = {
        "log": {
            "name": log.name,
            "lines": [
                {
                    "no": line.no,
                    "head": line.head,
                    "proc": line.proc,
                    "msg": line.message if line.head else line.raw,
                    "events": by_line.get(line.no, []),
                }
                for line in log.lines
            ],
        },
        "events": events,
        "rules": [{"code": r.code, "outcome": r.outcome, "checks": r.checks, "misses": r.misses} for r in RULES],
        "statuses": [{"id": k, "text": t} for k, t in STATUS_TEXT],
        "runs": out_runs,
        "default": default,
    }
    return payload, assessed_all


def _noscript_table(run: dict) -> str:
    rows = []
    for claim, verdict in zip(run["claims"], run["verdicts"]):
        why = " ".join(r["message"].replace("`", "") for r in verdict["reasons"])
        rows.append(
            "<tr>"
            f"<td>{html.escape(claim['id'])}</td><td>{html.escape(claim['kind'])}</td>"
            f"<td>{html.escape(STATUS_LABEL[verdict['status']])}</td>"
            f"<td>{html.escape(claim['text'].replace('`', ''))}</td>"
            f"<td>{html.escape(format_lines(verdict['cited'] + verdict['out_of_range']))}</td>"
            f"<td>{html.escape(why)}</td></tr>"
        )
    head = "<thead><tr><th>Claim</th><th>Kind</th><th>Result</th><th>Text</th><th>Lines</th><th>Why</th></tr></thead>"
    return f"<table>{head}<tbody>{''.join(rows)}</tbody></table>"


def render_html(log: Log, truth: dict | None, runs: list[dict]) -> str:
    payload, _ = _payload(log, truth, runs)
    default = next(r for r in payload["runs"] if r["id"] == payload["default"])
    css = (WEB / "app.css").read_text(encoding="utf-8")
    for marker, name in FONTS.items():
        data = base64.b64encode((WEB / "fonts" / name).read_bytes()).decode("ascii")
        css = css.replace(marker, data)
    page = (WEB / "index.template.html").read_text(encoding="utf-8")
    # Order matters: the data goes in last so nothing inside it is ever treated as a marker.
    page = page.replace("{{CSS}}", css)
    page = page.replace("{{JS}}", (WEB / "app.js").read_text(encoding="utf-8"))
    page = page.replace("{{HERO}}", html.escape(default["hero"]))
    page = page.replace(
        "{{NOSCRIPT_TABLE}}",
        _noscript_table({"claims": default["claims"], "verdicts": [c["verdict"] for c in default["claims"]]}),
    )
    page = page.replace("{{DATA}}", _safe_json(payload))
    return page


def build_dashboard(runs_dir: str | Path, log_path: str | Path, out_path: str | Path) -> tuple[Path, list[str]]:
    log = Log.from_file(log_path)
    truth_path = Path(log_path).with_suffix(".truth.json")
    truth = json.loads(truth_path.read_text(encoding="utf-8")) if truth_path.exists() else None
    runs, skipped = load_runs(runs_dir, log)
    if not runs:
        raise SystemExit(
            f"No runs in {runs_dir}. Run `python -m citedlog demo` for the scripted examples, "
            "or `python -m citedlog summarise` with Ollama running."
        )
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(log, truth, runs), encoding="utf-8")
    return out, skipped


__all__ = ["build_dashboard", "render_html", "TRUTH_NAME"]
