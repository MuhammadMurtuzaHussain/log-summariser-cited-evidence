"""Check that each claim in a briefing is backed by the log lines it cites.

Four outcomes, from best to worst:

  verified     every line exists and every address, name, time and count the claim
               states can be found in the cited lines
  unchecked    every line exists, but the claim states nothing the checker can test
  unsupported  the lines exist, but something the claim states is not in them
  invalid      the citation itself is broken: missing, malformed or out of range

This is evidence checking, not truth checking. A claim can pass and still be a
poor reading of the log (see the limits in `RULES` and the README).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .logfile import CLOCK, IPV4, Log, format_lines

STATUSES = ("verified", "unchecked", "unsupported", "invalid")
FACT_KINDS = ("headline", "finding")
TOO_BROAD_SHARE = 0.6  # citing more than 60% of the log points at nothing in particular


@dataclass(frozen=True)
class Rule:
    code: str
    outcome: str  # which status a failure produces
    checks: str
    misses: str


RULES = [
    Rule(
        "NO_CITATION",
        "invalid",
        "The claim lists at least one line number.",
        "Nothing: an empty citation is always a failure.",
    ),
    Rule(
        "BAD_CITATION",
        "invalid",
        "Every entry in `lines` is a whole number, not text, a range string or a decimal.",
        "A range written in the claim text (for example 'lines 17-28') is ignored; only `lines` counts.",
    ),
    Rule(
        "LINE_OUT_OF_RANGE",
        "invalid",
        "Every cited line number exists in the log (1 to the last line).",
        "A line that exists but is the wrong one. The next four rules look at that.",
    ),
    Rule(
        "ENTITY_NOT_IN_CITED_LINES",
        "unsupported",
        "Every IPv4 address, username known from the log, and `backticked` or 'named' term in the "
        "claim appears in at least one cited line.",
        "A username the log never mentions and the claim does not put in backticks or after 'named'.",
    ),
    Rule(
        "TIME_NOT_IN_CITED_LINES",
        "unsupported",
        "Every clock time in the claim (13:43 or 13:43:11) appears in at least one cited line.",
        "Durations and ordering ('within 30 seconds', 'before the login').",
    ),
    Rule(
        "COUNT_MISMATCH",
        "unsupported",
        "'N failed password attempts' (also failed logins, authentication failures) equals the number "
        "of cited 'Failed password' lines. When the claim names an address or a user that those lines "
        "are from or against, only the lines that match count. 'At least N' and 'more than N' are "
        "compared as such.",
        "Counts of other things, such as distinct usernames or sessions. When a claim names several "
        "users, failures against any of them count, so a user named only for what happened next "
        "can widen the count.",
    ),
    Rule(
        "ABSENCE_CONTRADICTED",
        "unsupported",
        "A claim that something never succeeded ('no successful login from X') is checked against the "
        "whole log, because absence cannot be shown by citing lines.",
        "Absence claims that name no address or user.",
    ),
    Rule(
        "TOO_BROAD",
        "unsupported",
        f"The claim cites no more than {int(TOO_BROAD_SHARE * 100)}% of the log. Citing nearly everything "
        "would otherwise satisfy every rule above.",
        "Padding below that share. It is reported as a note (PADDING), not a failure.",
    ),
]
RULE_OUTCOME = {rule.code: rule.outcome for rule in RULES}

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "twenty": 20,
}  # fmt: skip
_NUM = r"(?P<n>\d+|" + "|".join(_NUMBER_WORDS) + r")"
_COUNT = re.compile(
    r"(?P<rel>at least|more than|over|up to|at most|fewer than)?\s*\b" + _NUM
    + r"\s+(?:(?:consecutive|repeated|separate|further|more|additional)\s+)*"
    r"(?:(?:failed|unsuccessful)\s+(?:(?:password|login|ssh|authentication)\s+)*(?:attempts?|logins?|authentications?|passwords?|tries)"
    r"|(?:(?:password|login|authentication)\s+)?failures?)\b",
    re.IGNORECASE,
)  # fmt: skip
_NEGATION = r"\b(?:no|never|not|without|didn't|did not|fail(?:ed)? to|unable to)\b"
_SUCCESS = (
    r"\b(?:successful(?:ly)?|success|succeed(?:ed)?|accepted|logged in|log in|login|"
    r"authenticat\w+|gained access|got in)\b"
)
_ABSENCE = re.compile(_NEGATION + r"[^.;]{0,40}?" + _SUCCESS, re.IGNORECASE)
_BACKTICKED = re.compile(r"`([^`\n]{1,80})`")
_NAMED = re.compile(r"\b(?:named|called)\s+[`'\"]?([A-Za-z_][\w.-]{2,31})")
_NAMED_STOP = {"the", "this", "that", "them", "there", "its", "their", "and"}


@dataclass
class Token:
    kind: str  # ip | user | time | quoted
    text: str
    found: bool = False
    lines: list[int] = field(default_factory=list)  # cited lines that contain it


@dataclass
class Verdict:
    status: str
    reasons: list[dict] = field(default_factory=list)  # {code, message}
    tokens: list[Token] = field(default_factory=list)
    count: dict | None = None  # {claimed, actual, relation}
    out_of_range: list[int] = field(default_factory=list)
    padding: list[int] = field(default_factory=list)
    contradicting: list[int] = field(default_factory=list)
    cited: list[int] = field(default_factory=list)  # cited lines that exist

    def to_dict(self) -> dict:
        return asdict(self)


def _word(token: str) -> re.Pattern:
    return re.compile(r"(?<![\w.-])" + re.escape(token) + r"(?![\w-])")


def _extract_tokens(text: str, log: Log) -> list[Token]:
    tokens: dict[str, Token] = {}

    def add(kind: str, value: str) -> None:
        tokens.setdefault(value, Token(kind, value))

    for ip in IPV4.findall(text):
        add("ip", ip)
    for user in sorted(log.users):
        if _word(user).search(text):
            add("user", user)
    for clock in CLOCK.findall(text):
        add("time", clock)
    for quoted in _BACKTICKED.findall(text):
        add("quoted", quoted.strip())
    for named in _NAMED.findall(text):
        if named.lower() not in _NAMED_STOP:
            add("quoted", named)
    return list(tokens.values())


def _token_in_line(token: Token, raw: str) -> bool:
    if token.kind == "ip":
        return token.text in IPV4.findall(raw)
    if token.kind == "time":
        clock = "0" + token.text if re.match(r"\d:", token.text) else token.text
        return re.search(r"(?<![\d:])" + re.escape(clock) + r"(?!\d)", raw) is not None
    if token.kind == "user":
        return _word(token.text).search(raw) is not None
    return token.text in raw


def _claimed_count(text: str) -> tuple[int, str] | None:
    match = _COUNT.search(text)
    if not match:
        return None
    raw = match.group("n").lower()
    n = int(raw) if raw.isdigit() else _NUMBER_WORDS[raw]
    rel = (match.group("rel") or "exactly").lower()
    if rel in ("at least",):
        rel = "at least"
    elif rel in ("more than", "over"):
        rel = "more than"
    elif rel in ("up to", "at most"):
        rel = "at most"
    return n, rel


def _count_ok(claimed: int, actual: int, relation: str) -> bool:
    return {
        "exactly": actual == claimed,
        "at least": actual >= claimed,
        "more than": actual > claimed,
        "at most": actual <= claimed,
        "fewer than": actual < claimed,
    }[relation]


_FAILED = re.compile(r"Failed password for (?:invalid user )?(?P<user>\S+) from (?P<ip>\S+)")


def _failures_about(log: Log, failed: list[int], tokens: list["Token"]) -> tuple[list[int], list[str], list[str]]:
    """The failed-password lines a claim is counting: those from the addresses and against the users it names.

    A name only narrows the count if it actually appears in the cited failures, so an address or a user named
    for another reason (the account that logged in afterwards, say) does not empty the count.
    """
    seen = {n: _FAILED.match(log.line(n).message) for n in failed}
    sources = {m["ip"] for m in seen.values() if m}
    targets = {m["user"] for m in seen.values() if m}
    ips = [t.text for t in tokens if t.kind == "ip" and t.text in sources]
    users = [t.text for t in tokens if t.kind == "user" and t.text in targets]
    kept = [
        n for n in failed
        if (m := seen[n]) and (not ips or m["ip"] in ips) and (not users or m["user"] in users)
    ]  # fmt: skip
    return kept, ips, users


def _accepted_lines(log: Log, ips: list[str], users: list[str]) -> list[int]:
    hits = []
    for line in log.lines:
        if not line.message.startswith("Accepted "):
            continue
        if ips and not any(ip in IPV4.findall(line.raw) for ip in ips):
            continue
        if users and not any(_word(u).search(line.message.split(" from ")[0]) for u in users):
            continue
        hits.append(line.no)
    return hits


def verify_claim(claim: dict, log: Log) -> Verdict:
    """Judge one claim against the log. `claim` needs `text` and `lines`."""
    text = str(claim.get("text", ""))
    cited = claim.get("lines")
    reasons: list[dict] = []

    def fail(code: str, message: str) -> None:
        reasons.append({"code": code, "message": message})

    if not isinstance(cited, list) or not cited:
        fail("NO_CITATION", "No line numbers given. Every claim has to cite the lines that back it.")
        return Verdict("invalid", reasons)

    bad = [c for c in cited if not isinstance(c, int) or isinstance(c, bool)]
    if bad:
        shown = ", ".join(repr(b) for b in bad[:3])
        fail("BAD_CITATION", f"`lines` holds {shown}, which is not a log line number.")
        return Verdict("invalid", reasons)

    unique = sorted(set(cited))
    outside = [n for n in unique if not log.has(n)]
    inside = [n for n in unique if log.has(n)]
    if outside:
        shown = ", ".join(f"L{n}" for n in outside)
        fail("LINE_OUT_OF_RANGE", f"Cites {shown}; the log runs from L1 to L{len(log)}.")

    tokens = _extract_tokens(text, log)
    for token in tokens:
        token.lines = [n for n in inside if _token_in_line(token, log.line(n).raw)]
        token.found = bool(token.lines)

    count = None
    claimed = _claimed_count(text)
    if claimed and inside:
        n, relation = claimed
        failed = [k for k in inside if log.line(k).message.startswith("Failed password")]
        kept, count_ips, count_users = _failures_about(log, failed, tokens)
        count = {"claimed": n, "actual": len(kept), "relation": relation}
        if len(kept) < len(failed):  # the claim's own names ruled some failures out; say which
            who = (f" from `{'`, `'.join(count_ips)}`" if count_ips else "") + (
                f" against `{'`, `'.join(count_users)}`" if count_users else ""
            )
            count["scope"] = who

    contradicting: list[int] = []
    if _ABSENCE.search(text):
        ips = [t.text for t in tokens if t.kind == "ip"]
        users = [t.text for t in tokens if t.kind == "user"]
        if ips or users:
            contradicting = _accepted_lines(log, ips, users)

    where = format_lines(inside) if inside else "any line"
    if not outside:
        for token in tokens:
            if token.found:
                continue
            if token.kind == "time":
                fail("TIME_NOT_IN_CITED_LINES", f"The time {token.text} does not appear in {where}.")
            else:
                label = {"ip": "The address", "user": "The user", "quoted": "The term"}[token.kind]
                fail("ENTITY_NOT_IN_CITED_LINES", f"{label} `{token.text}` does not appear in {where}.")
        if count and not _count_ok(count["claimed"], count["actual"], count["relation"]):
            rel = "" if count["relation"] == "exactly" else count["relation"] + " "
            fail(
                "COUNT_MISMATCH",
                f"Says {rel}{count['claimed']} failed attempts; {where} hold "
                f"{count['actual']} 'Failed password' {'line' if count['actual'] == 1 else 'lines'}"
                f"{count.get('scope', '')}.",
            )
        if contradicting:
            many = len(contradicting) > 1
            fail(
                "ABSENCE_CONTRADICTED",
                f"Says nothing succeeded, but the log has {'accepted logins' if many else 'an accepted login'} "
                f"at {format_lines(contradicting)}.",
            )
        if len(inside) > TOO_BROAD_SHARE * len(log):
            fail(
                "TOO_BROAD",
                f"Cites {len(inside)} of {len(log)} lines. A citation that broad does not point at anything.",
            )

    if outside:
        status = "invalid"
    elif reasons:
        status = "unsupported"
    elif not tokens and not count:
        status = "unchecked"
    else:
        status = "verified"

    padding = []
    if inside and any(t.found for t in tokens):
        padding = [n for n in inside if not any(_token_in_line(t, log.line(n).raw) for t in tokens)]

    return Verdict(
        status,
        reasons,
        tokens,
        count,
        out_of_range=outside,
        padding=padding,
        contradicting=contradicting,
        cited=inside,
    )


# ---------------------------------------------------------------- scoring a run


def verify_run(claims: list[dict], log: Log) -> list[Verdict]:
    return [verify_claim(claim, log) for claim in claims]


def score_run(claims: list[dict], verdicts: list[Verdict], log: Log, truth: dict) -> dict:
    """Roll verdicts up into the numbers the dashboard and the console report."""
    by_status = {s: 0 for s in STATUSES}
    facts = [i for i, c in enumerate(claims) if c.get("kind") in FACT_KINDS]
    actions = [i for i, c in enumerate(claims) if c.get("kind") == "action"]
    for i in facts:
        by_status[verdicts[i].status] += 1
    action_status = {s: 0 for s in STATUSES}
    for i in actions:
        action_status[verdicts[i].status] += 1

    routine = set(truth["routine_lines"])
    over_read = [
        claims[i].get("id", f"C{i + 1}")
        for i in facts
        if claims[i].get("severity") in ("suspicious", "malicious")
        and verdicts[i].cited
        and set(verdicts[i].cited) <= routine
    ]

    events = []
    for event in truth["events"]:
        key = set(event["key_lines"])
        found_by = []
        for i in facts:
            if verdicts[i].status != "verified" or not key & set(verdicts[i].cited):
                continue
            text = str(claims[i].get("text", ""))
            if any(term.lower() in text.lower() for term in event["terms"]):
                found_by.append(claims[i].get("id", f"C{i + 1}"))
        events.append({"id": event["id"], "found": bool(found_by), "by": found_by})

    total = len(facts)
    return {
        "facts": total,
        "by_status": by_status,
        "grounded": by_status["verified"],
        "grounding_rate": (by_status["verified"] / total) if total else None,
        "actions": len(actions),
        "action_status": action_status,
        "events": events,
        "events_found": sum(1 for e in events if e["found"]),
        "events_total": len(events),
        "over_read": over_read,
    }
