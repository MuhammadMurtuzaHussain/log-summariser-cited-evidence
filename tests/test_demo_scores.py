import re

import pytest

from citedlog.backends import scripted
from citedlog.runs import assess, hero_text, make_run

EXPECTED_SLOPPY = {
    "C1": ("unchecked", []),
    "C2": ("unsupported", ["COUNT_MISMATCH"]),
    "C3": ("verified", []),
    "C4": ("unsupported", ["TIME_NOT_IN_CITED_LINES"]),
    "C5": ("invalid", ["LINE_OUT_OF_RANGE"]),
    "C6": ("unsupported", ["ENTITY_NOT_IN_CITED_LINES"]),
    "C7": ("verified", []),
    "C8": ("unsupported", ["ABSENCE_CONTRADICTED"]),
    "C9": ("unsupported", ["ENTITY_NOT_IN_CITED_LINES"]),
    "C10": ("verified", []),
    "C11": ("verified", []),
    "C12": ("verified", []),
    "C13": ("unchecked", []),
}


def run_of(name, log, answer_key):
    run = make_run(scripted(name), log, demo_name=name)
    return run, assess(run, log, answer_key)


def test_faithful_demo_passes_every_check_and_finds_every_event(log, answer_key):
    run, a = run_of("faithful", log, answer_key)
    assert all(v.status == "verified" for v in a["verdicts"])
    s = a["score"]
    assert (s["facts"], s["grounded"], s["grounding_rate"]) == (8, 8, 1.0)
    assert (s["events_found"], s["events_total"]) == (6, 6)
    assert s["over_read"] == [] and s["actions"] == 3 and s["action_status"]["verified"] == 3


def test_sloppy_demo_trips_exactly_the_rule_each_claim_was_written_for(log, answer_key):
    run, a = run_of("sloppy", log, answer_key)
    got = {c["id"]: (v.status, [r["code"] for r in v.reasons]) for c, v in zip(run["claims"], a["verdicts"])}
    assert got == EXPECTED_SLOPPY


def test_sloppy_demo_scores(log, answer_key):
    _, a = run_of("sloppy", log, answer_key)
    s = a["score"]
    assert s["facts"] == 11
    assert s["by_status"] == {"verified": 4, "unchecked": 1, "unsupported": 5, "invalid": 1}
    assert s["grounding_rate"] == pytest.approx(4 / 11)
    assert s["over_read"] == ["C7"]  # fully backed by its lines, yet routine activity rated suspicious
    found = {e["id"]: e["by"] for e in s["events"]}
    assert found == {"E1": [], "E2": ["C3"], "E3": ["C11"], "E4": [], "E5": [], "E6": []}


def test_an_invented_version_of_an_event_earns_no_coverage(log, answer_key):
    # C6 describes the new account (E5) but names a user that is not in the log.
    _, a = run_of("sloppy", log, answer_key)
    assert next(e for e in a["score"]["events"] if e["id"] == "E5")["found"] is False


def test_actions_are_checked_but_kept_out_of_the_headline_rate(log, answer_key):
    _, a = run_of("sloppy", log, answer_key)
    assert a["score"]["actions"] == 2 and a["score"]["action_status"]["verified"] == 1
    assert a["score"]["facts"] == 11


def test_scoring_without_an_answer_key_still_works(log):
    run = make_run(scripted("faithful"), log, demo_name="faithful")
    s = assess(run, log, None)["score"]
    assert s["events_total"] == 0 and s["over_read"] == [] and s["grounded"] == 8


@pytest.mark.parametrize("name", ["faithful", "sloppy"])
def test_the_reading_only_states_numbers_that_are_in_the_score(log, answer_key, name):
    run, a = run_of(name, log, answer_key)
    s, hero = a["score"], a["hero"]
    numbers = [int(n) for n in re.findall(r"\b\d+\b", hero)]
    allowed = {s["facts"], s["events_total"], s["events_found"], len(s["over_read"]), *s["by_status"].values()}
    assert set(numbers) <= allowed, (hero, numbers, allowed)
    if name == "sloppy":
        for status, phrase in [
            ("verified", "backed by the lines they cite"),
            ("unsupported", "real lines that do not back them"),
            ("invalid", "broken citation"),
            ("unchecked", "nothing the checker can test"),
        ]:
            assert phrase in hero
            assert re.search(rf"\b{s['by_status'][status]} [^.,]*{phrase}", hero), (status, hero)


def test_the_reading_for_an_unreadable_reply_says_so(log):
    run = {"label": "tiny-model", "parse_error": "The reply is not valid JSON."}
    assert "nothing to check" in hero_text(run, {})


def _found(claims, log, answer_key):
    from citedlog.verify import score_run, verify_run

    verdicts = verify_run(claims, log)
    score = score_run(claims, verdicts, log, answer_key)
    return {e["id"]: e["by"] for e in score["events"] if e["by"]}, verdicts


def _claim(n, text, lines):
    return {"id": f"C{n}", "kind": "finding", "severity": "malicious", "text": text, "lines": lines}


def test_a_claim_about_the_new_account_does_not_earn_credit_for_the_later_return(log, answer_key):
    # The first live run did this: it said `support` was created and cited L42, L44 and L45 too.
    claim = _claim(1, "New user `support` created with root privileges", [35, 36, 37, 42, 44, 45])
    found, verdicts = _found([claim], log, answer_key)
    assert verdicts[0].status == "verified" and found == {"E5": ["C1"]}


def test_reading_etc_shadow_as_support_is_what_earns_the_return_event(log, answer_key):
    claim = _claim(1, "`support` read `/etc/shadow` with sudo at 14:02:49.", [44])
    found, verdicts = _found([claim], log, answer_key)
    assert verdicts[0].status == "verified" and found.get("E6") == ["C1"]


def test_a_claim_naming_shadow_but_citing_other_lines_does_not_find_the_return(log, answer_key):
    claim = _claim(1, "`support` read `/etc/shadow`.", [35, 36])
    found, _ = _found([claim], log, answer_key)
    assert "E6" not in found


def test_the_reading_agrees_in_number_with_what_it_counts():
    base = {"label": "m", "parse_error": None}
    one = {"facts": 3, "by_status": {"verified": 1, "unchecked": 2, "unsupported": 0, "invalid": 0}, "events_total": 0}
    many = {"facts": 3, "by_status": {"verified": 2, "unchecked": 1, "unsupported": 0, "invalid": 0}, "events_total": 0}
    assert hero_text(base, one) == "m made 3 claims. 1 is backed by the lines it cites and 2 name nothing the checker can test."
    assert hero_text(base, many) == "m made 3 claims. 2 are backed by the lines they cite and 1 names nothing the checker can test."
