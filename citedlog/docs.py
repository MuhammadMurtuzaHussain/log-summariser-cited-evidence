"""Documentation generated from the code, so it cannot drift from it."""

from __future__ import annotations

from .verify import RULES, TOO_BROAD_SHARE

STATUS_TEXT = [
    ("verified", "Every line exists and every address, name, time and count in the claim is in the cited lines."),
    ("unchecked", "Every line exists, but the claim states nothing the checker can test, so the citation proves little."),
    ("unsupported", "The lines exist, but something the claim states is not in them."),
    ("invalid", "The citation itself is broken: missing, malformed, or pointing past the end of the log."),
]


def verifier_rules_md() -> str:
    out = [
        "# What the verifier checks",
        "",
        "Generated from `citedlog/verify.py` by `python -m citedlog docs`. Do not edit by hand.",
        "",
        "The verifier answers one question for each claim: *do the lines it cites contain what it says?* "
        "It uses string matching only, never a second model, so the same claim always gets the same verdict.",
        "",
        "## Outcomes",
        "",
        "| Outcome | Meaning |",
        "|---|---|",
    ]
    out += [f"| `{name}` | {text} |" for name, text in STATUS_TEXT]
    out += [
        "",
        "## Rules",
        "",
        "| Rule | Outcome if it fails | What it checks | What it cannot catch |",
        "|---|---|---|---|",
    ]
    out += [f"| `{r.code}` | `{r.outcome}` | {r.checks} | {r.misses} |" for r in RULES]
    out += [
        "",
        "## Notes that do not change the outcome",
        "",
        "- `PADDING`: cited lines that contain none of the names, addresses or times in the claim. "
        "Shown on the claim so an analyst can see which citations are along for the ride.",
        "- Over-read: a claim rated `suspicious` or `malicious` whose cited lines are all routine activity "
        "(needs the answer key, `*.truth.json`). The claim can be fully backed by its lines and still be a poor reading.",
        "",
        "## What a pass does not mean",
        "",
        "A verified claim has real evidence behind its details. It is not proof that the claim reads the evidence correctly. "
        "'This is a brute-force attack' cites the right lines whether or not the log supports that conclusion, "
        "and the verifier cannot tell the difference. Judgement stays with the analyst; the verifier makes "
        "the evidence quick to open.",
        "",
        f"Threshold used by `TOO_BROAD`: more than {int(TOO_BROAD_SHARE * 100)}% of the log.",
        "",
    ]
    return "\n".join(out)
