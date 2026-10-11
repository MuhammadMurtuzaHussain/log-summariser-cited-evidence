import pytest

from citedlog.verify import RULE_OUTCOME, RULES, verify_claim

L = "lines"


def codes(verdict):
    return [r["code"] for r in verdict.reasons]


def check(log, text, lines):
    return verify_claim({"text": text, L: lines}, log)


# ---------------------------------------------------------------- citation shape


@pytest.mark.parametrize("lines", [None, [], "17", 17])
def test_missing_citation_is_invalid(log, lines):
    v = check(log, "`203.0.113.45` guessed passwords.", lines)
    assert v.status == "invalid" and codes(v) == ["NO_CITATION"]


@pytest.mark.parametrize("lines", [["17"], [17.0], [True], ["17-28"], [None]])
def test_non_integer_lines_are_invalid(log, lines):
    v = check(log, "`203.0.113.45` guessed passwords.", lines)
    assert v.status == "invalid" and codes(v) == ["BAD_CITATION"]


@pytest.mark.parametrize("bad", [0, 51, -1, 999])
def test_lines_outside_the_log_are_invalid(log, bad):
    v = check(log, "`203.0.113.45` tried `admin`.", [18, bad])
    assert v.status == "invalid" and codes(v) == ["LINE_OUT_OF_RANGE"]
    assert v.out_of_range == [bad] and v.cited == [18]
    assert "L1 to L50" in v.reasons[0]["message"]


def test_a_claim_with_no_text_but_good_lines_is_unchecked(log):
    assert check(log, "", [18]).status == "unchecked"


def test_duplicate_lines_are_counted_once(log):
    v = check(log, "`203.0.113.45` tried `admin`.", [18, 18, 17])
    assert v.cited == [17, 18] and v.status == "verified"


# ---------------------------------------------------------------- tokens


def test_everything_in_the_cited_lines_verifies(log):
    v = check(log, "`203.0.113.45` failed against `admin` at 13:41:11.", [18])
    assert v.status == "verified" and v.reasons == []
    assert {t.kind for t in v.tokens} == {"ip", "user", "time"}
    assert all(t.found for t in v.tokens)


def test_address_not_in_cited_lines(log):
    v = check(log, "`198.51.100.77` tried `ubuntu`.", [12, 13])
    assert v.status == "unsupported" and codes(v) == ["ENTITY_NOT_IN_CITED_LINES"]
    assert "198.51.100.77" in v.reasons[0]["message"]


def test_real_address_on_the_wrong_lines_is_caught(log):
    v = check(log, "203.0.113.45 logged in as deploy.", [1, 2])
    assert v.status == "unsupported"
    assert codes(v) == ["ENTITY_NOT_IN_CITED_LINES"] * 2


def test_known_user_not_in_cited_lines(log):
    assert codes(check(log, "alice logged in.", [8, 9])) == ["ENTITY_NOT_IN_CITED_LINES"]


def test_invented_backticked_name_is_caught(log):
    v = check(log, "A new account `backup` was created.", [35, 36])
    assert codes(v) == ["ENTITY_NOT_IN_CITED_LINES"] and v.tokens[0].kind == "quoted"


def test_invented_name_after_named_is_caught_without_backticks(log):
    assert codes(check(log, "A new account named backup was created.", [35])) == ["ENTITY_NOT_IN_CITED_LINES"]
    assert check(log, "A new account called support was created.", [35]).status == "verified"


def test_commands_in_backticks_must_appear(log):
    assert check(log, "`alice` ran `apt update`.", [3]).status == "verified"
    assert codes(check(log, "`alice` ran `rm -rf /`.", [3])) == ["ENTITY_NOT_IN_CITED_LINES"]


def test_usernames_match_whole_words_only(log):
    # 'test' must not be found inside 'attested', and 'root' not inside 'rooted'.
    assert check(log, "The host was rooted.", [23]).status == "unchecked"


def test_time_must_appear(log):
    v = check(log, "`deploy` logged in at 13:52:11.", [31])
    assert codes(v) == ["TIME_NOT_IN_CITED_LINES"]


@pytest.mark.parametrize("stated", ["13:43", "13:43:11", "at 13:43."])
def test_times_match_by_prefix_or_exactly(log, stated):
    assert check(log, f"`deploy` logged in {stated}", [31]).status == "verified"


def test_single_digit_hours_match_padded_log_times(log):
    assert check(log, "`alice` logged in at 6:58.", [1]).status == "verified"


def test_a_claim_with_nothing_to_test_is_unchecked(log):
    v = check(log, "Several brute-force attacks hit the server.", [17, 18])
    assert v.status == "unchecked" and v.reasons == []


# ---------------------------------------------------------------- counts


COUNT_LINES = [18, 20, 22, 23, 24, 25, 26, 27, 28]  # seven 'Failed password' lines


@pytest.mark.parametrize(
    "text, ok",
    [
        ("7 failed password attempts from `203.0.113.45`", True),
        ("seven failed password attempts from `203.0.113.45`", True),
        ("12 failed password attempts from `203.0.113.45`", False),
        ("at least 5 failed attempts from `203.0.113.45`", True),
        ("at least 9 failed attempts from `203.0.113.45`", False),
        ("more than 7 failed logins from `203.0.113.45`", False),
        ("over 6 failed logins from `203.0.113.45`", True),
        ("up to 7 failed attempts from `203.0.113.45`", True),
        ("3 authentication failures from `203.0.113.45`", False),
    ],
)
def test_counts_are_compared_with_failed_password_lines(log, text, ok):
    v = check(log, text, COUNT_LINES)
    assert (v.status == "verified") is ok
    assert v.count["actual"] == 7
    assert (codes(v) == []) is ok and (ok or codes(v) == ["COUNT_MISMATCH"])


def test_count_of_something_else_is_not_checked(log):
    assert check(log, "three invalid usernames from `203.0.113.45`", COUNT_LINES).count is None


def test_count_with_nothing_else_can_still_verify(log):
    assert check(log, "2 failed password attempts.", [29, 30]).status == "verified"


# A claim that names an address or an account is counting that address or account,
# not every failure in the span it cites. L23-L34 hold four failures against root
# and two against deploy, all from the same address.

SPAN = list(range(23, 35))


@pytest.mark.parametrize(
    "text, ok, actual",
    [
        ("4 failed password attempts against `root`.", True, 4),
        ("2 failed password attempts against `deploy`.", True, 2),
        ("`203.0.113.45` made 4 failed attempts against `root`.", True, 4),
        ("`203.0.113.45` made 6 failed attempts.", True, 6),
        ("6 failed password attempts against `root`.", False, 4),
        ("`203.0.113.45` made 5 failed attempts against `root`.", False, 4),
        ("`203.0.113.45` made 4 failed attempts against `deploy`.", False, 2),
    ],
)
def test_count_follows_the_users_the_claim_names(log, text, ok, actual):
    v = check(log, text, SPAN)
    assert v.count["actual"] == actual
    assert (v.status == "verified") is ok
    assert ("COUNT_MISMATCH" in codes(v)) is (not ok)


def test_a_narrowed_count_says_what_it_counted(log):
    v = check(log, "6 failed password attempts against `root`.", SPAN)
    message = next(r["message"] for r in v.reasons if r["code"] == "COUNT_MISMATCH")
    assert "Says 6 failed attempts" in message
    assert "hold 4 'Failed password' lines against `root`" in message


def test_a_count_with_no_name_in_it_still_counts_every_failure(log):
    v = check(log, "Six failed password attempts.", SPAN)
    assert v.count["actual"] == 6 and v.status == "verified"
    assert "scope" not in v.count


def test_a_count_narrows_by_address_alone(log):
    # L13 and L16 are failures from another address; only L18 is from the named one.
    assert check(log, "`203.0.113.45` made 1 failed password attempt.", [13, 18]).status == "verified"
    v = check(log, "`203.0.113.45` made 3 failed password attempts.", [13, 18])
    assert codes(v) == ["COUNT_MISMATCH"] and v.count["actual"] == 1
    assert "from `203.0.113.45`" in v.reasons[0]["message"]


def test_a_user_who_was_never_a_target_does_not_narrow_the_count(log):
    # alice is in the log but nobody failed a password against her in L23-L34.
    # Her name is not in those lines, so the claim fails on that, not on the count.
    v = check(log, "6 failed password attempts, none against `alice`.", SPAN)
    assert codes(v) == ["ENTITY_NOT_IN_CITED_LINES"]
    assert v.count["actual"] == 6


# ---------------------------------------------------------------- absence


def test_never_succeeded_is_checked_against_the_whole_log(log):
    v = check(log, "There were no successful logins from `203.0.113.45`.", list(range(17, 29)))
    assert v.status == "unsupported" and codes(v) == ["ABSENCE_CONTRADICTED"]
    assert v.contradicting == [31, 42]


def test_never_succeeded_passes_when_it_is_true(log):
    v = check(log, "`198.51.100.23` never got in; no successful login from it.", [12, 13, 14, 15, 16])
    assert v.status == "verified" and v.contradicting == []


def test_absence_by_user_is_checked(log):
    assert codes(check(log, "`deploy` never logged in.", [29, 30])) == ["ABSENCE_CONTRADICTED"]
    assert check(log, "`root` never logged in from `203.0.113.45`.", [23, 24]).status == "verified"


def test_absence_without_an_address_or_user_is_not_checked(log):
    assert check(log, "No successful login happened.", [23]).status == "unchecked"


# ---------------------------------------------------------------- breadth and padding


def test_citing_most_of_the_log_is_too_broad(log):
    broad = check(log, "`203.0.113.45` attacked the host.", list(range(1, 32)))  # 31 of 50
    assert codes(broad) == ["TOO_BROAD"]
    edge = check(log, "`203.0.113.45` attacked the host.", list(range(1, 31)))  # 30 of 50
    assert "TOO_BROAD" not in codes(edge)


def test_padding_is_reported_but_does_not_fail(log):
    v = check(log, "`203.0.113.45` guessed the `admin` password.", [1, 2, 18])
    assert v.status == "verified" and v.padding == [1, 2]


def test_no_padding_note_when_nothing_matched_at_all(log):
    assert check(log, "A new account named backup was created.", [35]).padding == []


def test_out_of_range_claims_still_report_what_they_matched(log):
    v = check(log, "`203.0.113.45` tried `admin`.", [18, 99])
    assert v.status == "invalid" and [t.found for t in v.tokens] == [True, True]


# ---------------------------------------------------------------- the rule list


def test_every_rule_outcome_is_a_failure_status():
    assert {r.outcome for r in RULES} <= {"invalid", "unsupported"}
    assert set(RULE_OUTCOME) == {r.code for r in RULES}
    assert len(RULE_OUTCOME) == len(RULES)


def test_every_failure_code_the_checker_can_emit_is_documented(log):
    emitted = set()
    cases = [
        ("x", None), ("x", ["a"]), ("`203.0.113.45`", [99]), ("`198.51.100.77`", [12]),
        ("at 13:52:11", [31]), ("9 failed attempts", [29]), ("no successful login from `203.0.113.45`", [18]),
        ("`203.0.113.45`", list(range(1, 40))),
    ]  # fmt: skip
    for text, lines in cases:
        emitted |= set(codes(verify_claim({"text": text, L: lines}, log)))
    assert emitted == set(RULE_OUTCOME)


def test_verifier_is_deterministic(log):
    claim = {"text": "`203.0.113.45` made 9 failed attempts at 13:41:11.", L: [18, 20]}
    assert verify_claim(claim, log).to_dict() == verify_claim(claim, log).to_dict()
