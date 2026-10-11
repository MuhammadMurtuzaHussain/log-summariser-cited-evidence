import re

from citedlog.logfile import Log
from citedlog.scenario import ENTRIES, EVENTS, LOG_NAME, log_text, truth


def test_log_has_exactly_fifty_lines_and_all_parse():
    log = Log(log_text(), LOG_NAME)
    assert len(ENTRIES) == len(log) == 50
    assert all(line.head and line.proc for line in log.lines)
    assert all(line.head + " " + line.proc + line.message == line.raw for line in log.lines)


def test_log_is_in_time_order():
    times = [line.time for line in Log(log_text(), LOG_NAME).lines]
    assert times == sorted(times)


def test_every_line_is_routine_or_belongs_to_one_event():
    key = truth()
    seen = set(key["routine_lines"])
    for event in key["events"]:
        assert not seen & set(event["lines"]), "a line belongs to two events"
        seen |= set(event["lines"])
    assert seen == set(range(1, 51))


def test_key_lines_are_part_of_their_event():
    for event in truth()["events"]:
        assert event["key_lines"] and set(event["key_lines"]) <= set(event["lines"])
    assert [e["id"] for e in truth()["events"]] == list(EVENTS)


def test_the_story_is_what_the_demo_briefings_assume():
    log = Log(log_text(), LOG_NAME)
    failed = lambda ip: [  # noqa: E731
        line.no for line in log.lines if line.message.startswith("Failed password") and ip in line.raw
    ]
    assert len(failed("203.0.113.45")) == 9  # 7 in the burst, 2 against deploy
    assert len(failed("198.51.100.23")) == 2
    accepted = [line.no for line in log.lines if line.message.startswith("Accepted") and "203.0.113.45" in line.raw]
    assert accepted == [31, 42]
    assert not [line for line in log.lines if line.message.startswith("Accepted") and "198.51.100.23" in line.raw]
    assert re.search(r"name=support", log.line(35).raw)
    assert "/etc/shadow" in log.line(44).raw
