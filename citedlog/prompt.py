"""The prompt and the JSON shape the model is asked to return."""

from __future__ import annotations

import hashlib

from .logfile import Log

SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["headline", "finding", "action"]},
                    "severity": {"type": "string", "enum": ["info", "suspicious", "malicious"]},
                    "text": {"type": "string"},
                    "lines": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["kind", "severity", "text", "lines"],
            },
        }
    },
    "required": ["claims"],
}

SYSTEM_V1 = """\
You are an assistant to a security analyst. You are given an authentication log. Every line starts with its line number in square brackets, for example [17].

Write the analyst briefing as JSON: {"claims": [...]}. Each claim has four fields: "kind", "severity", "text" and "lines".

Rules:
1. Use only what the log shows. Do not use outside knowledge about the hosts, people or attackers.
2. "lines" lists the line numbers that show the claim is true. Cite every line the claim depends on and no others. Use only line numbers that appear in the log.
3. Do not write line numbers in "text".
4. Put every username, IP address, command and file path in backticks, copied exactly from the log. Write times as they appear in the log.
5. If "text" states a count, it must equal the number of cited lines that show the thing being counted.
6. Do not claim anything the log does not show. If you say something never happened, say it only about the address or user you name.
7. "severity" is "info" for routine activity, "suspicious" for activity that needs a look, and "malicious" for activity the log shows is an attack or a compromise.
8. Order: one claim with "kind": "headline" that summarises the log in a sentence or two; then claims with "kind": "finding", most serious first; then claims with "kind": "action", each a concrete next step that cites the lines which justify it.

Reply with the JSON object only.\
"""


# Version 2 answers the first live run (llama3.2, version 1): the model kept to the JSON shape
# and cited real lines, but wrote claims like "Multiple failed SSH login attempts" that name no
# address, user, time or count, so the checker had nothing to test. Version 2 asks for the
# specifics and shows the format on a different, three-line log. The example uses an address
# and usernames that appear nowhere in the scenario, so a copy of it cannot score.
_V2_RULES = """\

9. Be specific. A finding says who did what: the source address or the username, and the action that the lines show, for example "failed password for `root`" or "added `name` to group `sudo`". A sentence that would be just as true of a different log, such as "multiple failed login attempts", is not a finding.
10. One claim per event. Do not merge separate events, such as a burst of failures, a later successful login and a new account, into one claim. Cite only the lines of that event.

Example, from a different log, for the format only:
[1] Mar  3 02:11:05 gw01 sshd[311]: Failed password for invalid user guest from 192.0.2.8 port 5001 ssh2
[2] Mar  3 02:11:09 gw01 sshd[311]: Failed password for root from 192.0.2.8 port 5002 ssh2
[3] Mar  3 02:11:14 gw01 sshd[314]: Accepted password for ops from 192.0.2.8 port 5003 ssh2

{"claims": [
{"kind": "headline", "severity": "malicious", "text": "`192.0.2.8` failed twice against `guest` and `root`, then logged in as `ops` at 02:11:14.", "lines": [1, 2, 3]},
{"kind": "finding", "severity": "suspicious", "text": "`192.0.2.8` made 2 failed password attempts, against `guest` and `root`.", "lines": [1, 2]},
{"kind": "finding", "severity": "malicious", "text": "`192.0.2.8` logged in as `ops` seconds after those failures.", "lines": [3]},
{"kind": "action", "severity": "info", "text": "Review what `ops` did after the login from `192.0.2.8`.", "lines": [3]}
]}

Now reply for the real log, with the JSON object only.\
"""

SYSTEM_V2 = SYSTEM_V1.removesuffix("\n\nReply with the JSON object only.").rstrip() + _V2_RULES

PROMPTS = {"v1": SYSTEM_V1, "v2": SYSTEM_V2}
DEFAULT_PROMPT = "v1"
SYSTEM = SYSTEM_V1  # the version the first live run used; kept so older imports still work


def user_message(log: Log) -> str:
    return f"Log file: {log.name} ({len(log)} lines)\n\n{log.numbered()}\n\nWrite the briefing now."


def system_prompt(version: str) -> str:
    try:
        return PROMPTS[version]
    except KeyError:
        raise ValueError(f"unknown prompt version {version!r}; choose from {', '.join(PROMPTS)}") from None


def prompt_sha256(log: Log, version: str = "v1") -> str:
    return hashlib.sha256((system_prompt(version) + "\n---\n" + user_message(log)).encode("utf-8")).hexdigest()


def prompt_version_for(sha: str, log: Log) -> str | None:
    """Which prompt version produced a run, judged from the hash the run recorded."""
    return next((v for v in PROMPTS if prompt_sha256(log, v) == sha), None)
