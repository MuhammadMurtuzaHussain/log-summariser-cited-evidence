import json

from citedlog.briefing import parse_briefing

GOOD = {"claims": [{"kind": "finding", "severity": "malicious", "text": " Root guessed. ", "lines": [1, 2]}]}


def test_plain_json():
    claims, err = parse_briefing(json.dumps(GOOD))
    assert err is None
    assert claims == [{"id": "C1", "kind": "finding", "severity": "malicious", "text": "Root guessed.", "lines": [1, 2]}]


def test_code_fences_and_chatter_are_tolerated():
    fenced = "Sure! Here you go:\n```json\n" + json.dumps(GOOD) + "\n```\nHope that helps."
    assert parse_briefing(fenced)[1] is None
    assert parse_briefing("Here: " + json.dumps(GOOD) + " Done.")[1] is None


def test_a_bare_list_is_accepted():
    claims, err = parse_briefing(json.dumps(GOOD["claims"]))
    assert err is None and len(claims) == 1


def test_wrong_line_numbers_are_kept_exactly_as_given():
    raw = json.dumps({"claims": [{"kind": "finding", "severity": "info", "text": "x", "lines": ["17", 99, None, 3.5]}]})
    assert parse_briefing(raw)[0][0]["lines"] == ["17", 99, None, 3.5]


def test_a_missing_lines_field_stays_missing():
    raw = json.dumps({"claims": [{"kind": "finding", "severity": "info", "text": "x"}]})
    assert parse_briefing(raw)[0][0]["lines"] is None


def test_unknown_kind_and_severity_fall_back_to_the_quietest_reading():
    raw = json.dumps({"claims": [{"kind": "rumour", "severity": "catastrophic", "text": "x", "lines": [1]}]})
    c = parse_briefing(raw)[0][0]
    assert (c["kind"], c["severity"]) == ("finding", "info")


def test_non_dict_items_are_skipped_and_ids_stay_sequential():
    raw = json.dumps({"claims": ["junk", GOOD["claims"][0], 7, GOOD["claims"][0]]})
    assert [c["id"] for c in parse_briefing(raw)[0]] == ["C1", "C2"]


def test_failures_return_an_explanation_and_no_claims():
    for raw in ["", "not json at all", '{"claims": "nope"}', '{"claims": []}', "[1, 2"]:
        claims, err = parse_briefing(raw)
        assert claims == [] and err
