from citedlog.logfile import CLOCK, IPV4, Log, format_lines


def test_users_and_ips_are_read_from_the_log(log):
    assert log.users == {"alice", "bob", "root", "admin", "test", "oracle", "deploy", "support", "ubuntu", "pi"}
    assert log.ips == {"10.0.4.21", "10.0.4.35", "198.51.100.23", "203.0.113.45"}


def test_numbering_starts_at_one_and_has_rejects_bad_numbers(log):
    assert log.line(1).no == 1 and log.line(50).no == 50
    assert log.has(1) and log.has(50)
    assert not log.has(0) and not log.has(51) and not log.has(-3)
    assert not log.has(True) and not log.has(7.0) and not log.has("7")


def test_numbered_view_is_what_the_model_sees(log):
    first = log.numbered().splitlines()[0]
    assert first.startswith("[1] Oct  7 06:58:12 web01 sshd[1180]: Accepted publickey")


def test_ip_pattern_ignores_versions_and_trailing_full_stops():
    assert IPV4.findall("from 203.0.113.45.") == ["203.0.113.45"]
    assert IPV4.findall("version 1.2.3.4.5") == []
    assert IPV4.findall("a 10.0.4.21, b 10.0.4.35") == ["10.0.4.21", "10.0.4.35"]


def test_clock_pattern():
    assert CLOCK.findall("at 13:43:11 and 14:02, not 123:456") == ["13:43:11", "14:02"]
    assert CLOCK.findall("13:41: the attacker") == ["13:41"]


def test_format_lines():
    assert format_lines([17, 18, 19, 22]) == "L17-L19, L22"
    assert format_lines([5]) == "L5"
    assert format_lines([3, 1, 2, 2]) == "L1-L3"
    assert format_lines([]) == "no lines"


def test_sha256_changes_with_content():
    assert Log("a\n").sha256 != Log("b\n").sha256
    assert Log("a").sha256 == Log("a\n").sha256


def test_lines_split_on_newlines_only():
    # U+2028 and form feeds are not line ends in a log file; `grep -n` and editors agree.
    log = Log("a" + chr(0x2028) + "b\nc\x0cd\r\ne\n")
    assert len(log) == 3
    assert [line.raw for line in log.lines] == ["a" + chr(0x2028) + "b", "c\x0cd", "e"]
