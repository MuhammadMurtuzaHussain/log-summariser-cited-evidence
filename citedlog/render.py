"""Console and Markdown views of a verified briefing."""

from __future__ import annotations

import os
import sys

from .logfile import format_lines

LABEL = {
    "verified": "VERIFIED",
    "unchecked": "UNCHECKED",
    "unsupported": "UNSUPPORTED",
    "invalid": "INVALID",
}
_COLOUR = {"verified": "32", "unchecked": "90", "unsupported": "33", "invalid": "31"}
OVER_READ = "Rated {severity}, but every line it cites is routine activity."
GLYPH_MD = {"verified": "✓", "unchecked": "–", "unsupported": "!", "invalid": "✕"}


def _use_colour() -> bool:
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _paint(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _use_colour() else text


def console(run: dict, assessed: dict, log) -> str:
    claims, verdicts, score = run["claims"], assessed["verdicts"], assessed["score"]
    out = []
    took = f", {run['elapsed_s']:.1f} s" if run.get("elapsed_s") else ""
    out.append(f"{run['label']}{took} · {log.name} ({len(log)} lines)")
    out.append("")
    if run.get("parse_error"):
        out.append(f"  Could not read the reply: {run['parse_error']}")
        out.append("")
    for claim, verdict in zip(claims, verdicts):
        status = _paint(f"{LABEL[verdict.status]:<11}", _COLOUR[verdict.status])
        cited = format_lines(verdict.cited + verdict.out_of_range) if (verdict.cited or verdict.out_of_range) else "no lines"
        out.append(f"  {claim['id']:<4}{claim['kind']:<9} {claim['severity']:<10} {status} {cited}")
        out.append(f"        {claim['text']}")
        for reason in verdict.reasons:
            out.append(f"        ! {reason['message']}")
        if claim["id"] in score["over_read"]:
            out.append(f"        ~ {OVER_READ.format(severity=claim['severity'])}")
        out.append("")
    out.append(assessed["hero"])
    return "\n".join(out)


def markdown(run: dict, assessed: dict, log) -> str:
    """The briefing as an analyst would paste it: citations inline, check marks beside them."""
    claims, verdicts, score = run["claims"], assessed["verdicts"], assessed["score"]
    out = [f"# Auth log briefing: {log.name}", ""]
    out.append(
        f"Written by {run['label']}. Every claim carries the log lines it rests on and "
        "whether the checker found its names, times and counts in those lines."
    )
    out.append("")
    out.append(f"> {assessed['hero']}")
    out.append("")
    sections = [("Headline", "headline"), ("Findings", "finding"), ("Recommended actions", "action")]
    for title, kind in sections:
        rows = [(c, v) for c, v in zip(claims, verdicts) if c["kind"] == kind]
        if not rows:
            continue
        out.append(f"## {title}")
        out.append("")
        for claim, verdict in rows:
            cited = format_lines(verdict.cited + verdict.out_of_range)
            out.append(
                f"- {GLYPH_MD[verdict.status]} **{claim['id']}** ({claim['severity']}) {claim['text']} "
                f"[{cited}]"
            )
            for reason in verdict.reasons:
                out.append(f"  - {reason['message']}")
            if claim["id"] in score["over_read"]:
                out.append(f"  - {OVER_READ.format(severity=claim['severity'])}")
        out.append("")
    out.append("Key: ✓ backed by the cited lines · – nothing the checker can test · ! cited lines do not back it · ✕ broken citation")
    return "\n".join(out) + "\n"
