import json
import re

import pytest

from citedlog.briefing import parse_briefing
from citedlog.logfile import IPV4, Log
from citedlog.prompt import (
    DEFAULT_PROMPT,
    PROMPTS,
    SYSTEM,
    SYSTEM_V1,
    SYSTEM_V2,
    prompt_sha256,
    prompt_version_for,
    system_prompt,
)
from citedlog.verify import verify_run


def test_version_one_is_the_prompt_the_first_live_run_used(log):
    assert SYSTEM is SYSTEM_V1 and DEFAULT_PROMPT == "v1"
    # Recorded in runs/20261009-142852-llama3.2.json.
    assert prompt_sha256(log) == "dbb8ec7a496b0401e714d55518fd758be01042aa76a640754bab757b590bb984"


def test_the_versions_differ_and_can_be_told_apart_from_a_hash(log):
    assert set(PROMPTS) == {"v1", "v2"} and SYSTEM_V1 != SYSTEM_V2
    assert prompt_sha256(log, "v1") != prompt_sha256(log, "v2")
    for version in PROMPTS:
        assert prompt_version_for(prompt_sha256(log, version), log) == version
    assert prompt_version_for("0" * 64, log) is None


def test_an_unknown_version_names_the_choices():
    with pytest.raises(ValueError, match="v1, v2"):
        system_prompt("v3")


def test_version_two_keeps_every_rule_of_version_one_and_adds_specifics():
    body = SYSTEM_V1.removesuffix("\n\nReply with the JSON object only.")
    assert SYSTEM_V2.startswith(body)
    assert "9. Be specific." in SYSTEM_V2 and "10. One claim per event." in SYSTEM_V2
    assert "backticks" in SYSTEM_V2 and SYSTEM_V2.rstrip().endswith("with the JSON object only.")


def _example(padding=0):
    """The worked example in version 2: its three log lines and the briefing it shows.

    The example log is only three lines, so any real citation of it is "too broad". `padding` adds
    routine lines after them, the way a real log would surround the events.
    """
    block = SYSTEM_V2.split("Example, from a different log, for the format only:\n", 1)[1]
    numbered, _, rest = block.partition("\n\n")
    lines = [re.sub(r"^\[\d+\] ", "", line) for line in numbered.splitlines()]
    lines += [f"Mar  3 03:{n:02d}:00 gw01 CRON[9{n:02d}]: pam_unix(cron:session): session opened for user root" for n in range(padding)]
    claims, error = parse_briefing(rest.split("\n\nNow reply", 1)[0])
    assert error is None
    return Log("\n".join(lines) + "\n", "example.log"), claims


def test_the_example_is_a_briefing_the_checker_would_pass_in_full():
    example_log, claims = _example(padding=12)
    assert len(example_log) == 15 and [c["kind"] for c in claims] == ["headline", "finding", "finding", "action"]
    assert [v.status for v in verify_run(claims, example_log)] == ["verified"] * 4


def test_the_example_shares_nothing_with_the_scenario_so_copying_it_cannot_score(log):
    example_log, claims = _example()
    assert not (example_log.ips & log.ips)
    assert not (example_log.users & log.users - {"root"})
    prompt_ips = set(IPV4.findall(SYSTEM_V2))
    assert prompt_ips and not (prompt_ips & log.ips)
    assert all("203.0.113" not in c["text"] and "198.51.100" not in c["text"] for c in claims)
    assert json.dumps(claims)  # plain data
