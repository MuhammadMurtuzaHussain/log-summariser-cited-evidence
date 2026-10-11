"""The live runs, kept as evidence: llama3.2 with prompt v1 and v2 (9 October 2026), qwen2.5:7b with v2 (11 October).

The reply is the model's own. These tests pin what the checker makes of it, so a change to a rule
that would alter the story told in the README has to be made on purpose.
"""

import re
from pathlib import Path

import pytest

from citedlog.briefing import parse_briefing
from citedlog.runs import assess, load_run, prompt_version_of

RUN = Path(__file__).resolve().parent.parent / "runs" / "20261009-142852-llama3.2.json"


@pytest.fixture(scope="module")
def run():
    return load_run(RUN)


@pytest.fixture
def assessed(run, log, answer_key):
    return assess(run, log, answer_key)


def test_it_was_made_against_this_log_and_the_stored_claims_are_the_replys(run, log):
    assert run["log"]["sha256"] == log.sha256
    claims, error = parse_briefing(run["raw_response"])
    assert error is None and claims == run["claims"]
    assert run["source"] == "ollama" and run["model"] == "llama3.2" and run["options"]["temperature"] == 0.0


def test_the_prompt_is_recognised_from_its_hash(run, log):
    assert "prompt_version" not in run  # written before versions existed
    assert prompt_version_of(run, log) == "v1"


def test_only_the_account_claim_is_backed_and_the_rest_name_nothing_testable(run, assessed):
    got = {c["id"]: (c["kind"], v.status) for c, v in zip(run["claims"], assessed["verdicts"])}
    assert got == {
        "C1": ("headline", "unchecked"),
        "C2": ("finding", "unchecked"),
        "C3": ("finding", "verified"),
        "C4": ("action", "unchecked"),
        "C5": ("action", "verified"),
        "C6": ("action", "unchecked"),
        "C7": ("action", "unchecked"),
        "C8": ("action", "unchecked"),
    }


def test_the_briefing_never_names_an_address_a_time_or_a_count(run):
    text = " ".join(c["text"] for c in run["claims"])
    assert not re.search(r"\d+\.\d+\.\d+\.\d+|\d{1,2}:\d{2}|`", text)  # no address, clock time or backtick
    assert not re.search(r"\b(?:\d+|two|three|four|five|six|seven|eight|nine|ten)\b", text, re.IGNORECASE)


def test_one_event_is_found_and_the_return_login_is_not_credited(assessed):
    score = assessed["score"]
    found = {e["id"]: e["by"] for e in score["events"]}
    assert found == {"E1": [], "E2": [], "E3": [], "E4": [], "E5": ["C3"], "E6": []}
    assert (score["facts"], score["grounded"]) == (3, 1) and score["over_read"] == []


def test_the_reading(assessed):
    assert assessed["hero"] == (
        "llama3.2 made 3 claims. 1 is backed by the lines it cites and 2 name nothing the checker can test. "
        "It found 1 of the 6 planted events."
    )


def test_an_accepted_login_cited_for_failed_attempts_is_a_gap_the_checker_does_not_close(run, log, assessed):
    # C2 says "failed" and cites L31, an accepted login. No rule tests what the words describe.
    c2 = next(c for c in run["claims"] if c["id"] == "C2")
    assert "failed" in c2["text"] and 31 in c2["lines"] and "Accepted" in log.line(31).raw
    assert assessed["verdicts"][1].status == "unchecked"


# ---------------------------------------------------------------- the same model with prompt v2

RUN_V2 = RUN.with_name("20261009-151525-llama3.2.json")


@pytest.fixture(scope="module")
def run2():
    return load_run(RUN_V2)


@pytest.fixture
def assessed2(run2, log, answer_key):
    return assess(run2, log, answer_key)


def test_v2_is_a_fair_comparison_with_v1(run, run2, log):
    from citedlog.prompt import prompt_sha256

    assert run2["log"]["sha256"] == log.sha256 and run2["parse_error"] is None
    assert (run2["model"], run2["options"]) == (run["model"], run["options"])  # same model, temperature, seed
    assert run2["prompt_version"] == "v2" and run2["label"] == "llama3.2 (prompt v2)"
    assert run2["prompt_sha256"] == prompt_sha256(log, "v2") != run["prompt_sha256"]
    claims, error = parse_briefing(run2["raw_response"])
    assert error is None and claims == run2["claims"]


def test_v2_over_cites_the_headline_and_the_first_finding(run2, assessed2):
    got = {c["id"]: (c["kind"], v.status, [r["code"] for r in v.reasons]) for c, v in zip(run2["claims"], assessed2["verdicts"])}
    assert got == {
        "C1": ("headline", "unsupported", ["TOO_BROAD"]),
        "C2": ("finding", "unsupported", ["TOO_BROAD"]),
        "C3": ("finding", "verified", []),
        "C4": ("action", "verified", []),
        "C5": ("action", "verified", []),
        "C6": ("action", "unchecked", []),
        "C7": ("action", "unchecked", []),
    }
    # One sentence naming three events, cited with 33 of the 50 lines, twice: rule 10 was not followed.
    assert [len(set(c["lines"])) for c in run2["claims"][:2]] == [33, 33]
    assert run2["claims"][0]["text"].split(", with")[1] == run2["claims"][1]["text"].split(", with")[1]


def test_v2_finds_two_events_through_the_one_claim_that_cites_narrowly(assessed2):
    found = {e["id"]: e["by"] for e in assessed2["score"]["events"]}
    assert found == {"E1": [], "E2": [], "E3": [], "E4": [], "E5": ["C3"], "E6": ["C3"]}
    assert assessed2["hero"] == (
        "llama3.2 (prompt v2) made 3 claims. 1 is backed by the lines it cites and 2 cite real lines "
        "that do not back them. It found 2 of the 6 planted events."
    )


def test_v2_names_what_v1_never_did_but_the_grounding_rate_did_not_move(run, run2, assessed, assessed2):
    v1_text = " ".join(c["text"] for c in run["claims"])
    v2_text = " ".join(c["text"] for c in run2["claims"])
    assert "`" not in v1_text and "`support`" in v2_text and "`alice`" in v2_text and "`cat /etc/shadow`" in v2_text
    s1, s2 = assessed["score"], assessed2["score"]
    assert (s1["facts"], s1["grounded"]) == (s2["facts"], s2["grounded"]) == (3, 1)
    assert (s1["events_found"], s2["events_found"]) == (1, 2)
    assert (s1["by_status"]["unchecked"], s2["by_status"]["unchecked"]) == (2, 0)


def test_a_wrong_assertion_in_the_backed_claim_is_a_gap_the_checker_does_not_close(run2, log, assessed2):
    # C3 says `support` was added to sudo "without a password". L37 shows its password being set.
    c3 = next(c for c in run2["claims"] if c["id"] == "C3")
    assert "without a password" in c3["text"] and 37 not in c3["lines"]
    assert "password changed for support" in log.line(37).raw
    assert assessed2["verdicts"][2].status == "verified"


# ---------------------------------------------------------------- a larger model, same prompt and settings as v2

RUN_QWEN = RUN.with_name("20261011-083227-qwen2.5-7b.json")


@pytest.fixture(scope="module")
def run3():
    return load_run(RUN_QWEN)


@pytest.fixture
def assessed3(run3, log, answer_key):
    return assess(run3, log, answer_key)


def test_qwen_is_a_fair_comparison_with_llama_v2(run2, run3, log):
    from citedlog.prompt import prompt_sha256

    assert run3["log"]["sha256"] == log.sha256 and run3["parse_error"] is None
    assert run3["source"] == "ollama" and run3["model"] == "qwen2.5:7b"
    assert run3["prompt_version"] == "v2" and run3["label"] == "qwen2.5:7b (prompt v2)"
    assert run3["prompt_sha256"] == run2["prompt_sha256"] == prompt_sha256(log, "v2")
    assert (run3["options"]["temperature"], run3["options"]["seed"]) == (run2["options"]["temperature"], run2["options"]["seed"])
    claims, error = parse_briefing(run3["raw_response"])
    assert error is None and claims == run3["claims"]


def test_qwen_backs_one_claim_and_the_other_three_each_fail_a_different_rule(run3, assessed3):
    got = {c["id"]: (c["kind"], v.status, [r["code"] for r in v.reasons]) for c, v in zip(run3["claims"], assessed3["verdicts"])}
    assert got == {
        "C1": ("headline", "unsupported", ["TOO_BROAD"]),
        "C2": ("finding", "unsupported", ["COUNT_MISMATCH"]),
        "C3": ("finding", "unsupported", ["ENTITY_NOT_IN_CITED_LINES"]),
        "C4": ("finding", "verified", []),
        "C5": ("action", "verified", []),
        "C6": ("action", "verified", []),
    }
    assert len(set(run3["claims"][0]["lines"])) == 37


def test_qwen_names_the_attacker_and_the_accounts_which_llama_never_did(run2, run3):
    llama = " ".join(c["text"] for c in run2["claims"])
    qwen = " ".join(c["text"] for c in run3["claims"])
    assert "203.0.113.45" not in llama and "`deploy`" not in llama
    assert "`203.0.113.45`" in qwen and "`deploy`" in qwen and "`support`" in qwen and "`/etc/shadow`" in qwen


def test_qwen_finds_one_event_and_grounds_fewer_claims_than_llama_because_it_says_more(assessed, assessed2, assessed3):
    found = {e["id"]: e["by"] for e in assessed3["score"]["events"]}
    assert found == {"E1": [], "E2": [], "E3": [], "E4": [], "E5": [], "E6": ["C4"]}
    assert (assessed3["score"]["facts"], assessed3["score"]["grounded"]) == (4, 1)
    assert assessed3["score"]["over_read"] == []
    # Same one backed claim as llama v1 and v2, out of more claims that can be tested.
    assert assessed3["score"]["grounding_rate"] < assessed["score"]["grounding_rate"] == assessed2["score"]["grounding_rate"]
    assert assessed3["score"]["by_status"]["unchecked"] == 0


def test_qwen_reading(assessed3):
    assert assessed3["hero"] == (
        "qwen2.5:7b (prompt v2) made 4 claims. 1 is backed by the lines it cites and 3 cite real lines "
        "that do not back them. It found 1 of the 6 planted events."
    )


def test_qwen_miscounts_the_failed_attempts_on_any_reading(run3, log, assessed3):
    # C2 says 5 against `root`. L23-L34 hold 4 against root and 2 against deploy, and the claim names both
    # accounts, so the checker's number is 6. Counted against root alone it is 4. The verdict is right either way.
    c2 = next(c for c in run3["claims"] if c["id"] == "C2")
    verdict = assessed3["verdicts"][1]
    assert "5 failed password attempts" in c2["text"] and "`root`" in c2["text"] and "`deploy`" in c2["text"]
    assert verdict.count == {"claimed": 5, "actual": 6, "relation": "exactly"}
    against_root = [n for n in c2["lines"] if log.line(n).message.startswith("Failed password for root ")]
    assert len(against_root) == 4


def test_qwen_attribution_is_plausible_but_not_shown_by_the_lines_it_cites(run3, log, assessed3):
    # C3 says `deploy` created `support`. L33-L34 show deploy opening a root shell 31 seconds earlier,
    # which makes the claim reasonable, but the model cited only L35-L37, so the checker is right to refuse it.
    c3 = next(c for c in run3["claims"] if c["id"] == "C3")
    assert c3["lines"] == [35, 36, 37] and "by `deploy`" in c3["text"]
    assert all("deploy" not in log.line(n).raw for n in c3["lines"])
    assert "COMMAND=/bin/bash" in log.line(33).raw and "by deploy" in log.line(34).raw
