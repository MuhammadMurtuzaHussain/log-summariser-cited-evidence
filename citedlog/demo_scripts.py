"""Two hand-written briefings, used when no model is available.

These are not model output. They exist so the verifier and the dashboard can be
shown without Ollama, and so the tests can pin down exactly which failure each
rule catches. The dashboard labels them "scripted demo" wherever they appear.

`faithful` is a briefing that passes every check. `sloppy` is a briefing with one
example of each failure a small model tends to produce: an uncheckable summary, a
miscount, a wrong time, a line that does not exist, an invented account, a routine
event read as an attack, a false "never succeeded", and an invented address.
"""

from __future__ import annotations


def _c(kind, severity, text, lines):
    return {"kind": kind, "severity": severity, "text": text, "lines": lines}


FAITHFUL = [
    _c(
        "headline", "malicious",
        "An external address, `203.0.113.45`, guessed passwords against `root` and three invalid "
        "names, got into `deploy` at 13:43:11, opened a root shell, created a sudo account called "
        "`support` and later logged in with it.",
        [18, 20, 22, 23, 24, 25, 26, 31, 33, 35, 36, 42],
    ),
    _c(
        "finding", "malicious",
        "`203.0.113.45` made 7 failed password attempts between 13:41:11 and 13:41:34: once each "
        "against the invalid users `admin`, `test` and `oracle`, then four times against `root`, "
        "before `sshd` cut it off for too many failures.",
        [18, 20, 22, 23, 24, 25, 26, 27, 28],
    ),
    _c(
        "finding", "malicious",
        "After 2 failed password attempts as `deploy`, `203.0.113.45` logged in as `deploy` at "
        "13:43:11 with a password.",
        [29, 30, 31, 32],
    ),
    _c(
        "finding", "malicious",
        "`deploy` ran `sudo` with `/bin/bash` as `root` at 13:44:20, giving the attacker a root shell.",
        [33, 34],
    ),
    _c(
        "finding", "malicious",
        "A new account, `support`, was created at 13:44:51, added to the `sudo` group and given a "
        "password at 13:45:06.",
        [35, 36, 37],
    ),
    _c(
        "finding", "malicious",
        "At 14:02:17 `203.0.113.45` logged in as `support` with a password, then used `sudo` to run "
        "`/usr/bin/cat /etc/shadow` at 14:02:49.",
        [42, 43, 44, 45],
    ),
    _c(
        "finding", "suspicious",
        "`198.51.100.23` probed the usernames `ubuntu` and `pi` at 11:20 and 12:47 and never got in; "
        "the log shows no successful login from it.",
        [12, 13, 14, 15, 16],
    ),
    _c(
        "finding", "info",
        "Routine activity: `alice` logged in from `10.0.4.21` with a public key at 06:58, and `bob` "
        "mistyped his password once at 07:31 before logging in from `10.0.4.35`.",
        [1, 2, 8, 9],
    ),
    _c(
        "action", "malicious",
        "Block `203.0.113.45` at the firewall and review every session it opened.",
        [31, 42],
    ),
    _c(
        "action", "malicious",
        "Disable the `support` account, reset the password for `deploy`, and check both for added "
        "SSH keys or scheduled jobs.",
        [31, 35, 36, 37],
    ),
    _c(
        "action", "suspicious",
        "Review which accounts may use `sudo`, starting with `deploy`.",
        [33, 36],
    ),
]

SLOPPY = [
    _c(
        "headline", "malicious",
        "Several brute-force attacks hit the server and at least one account was compromised.",
        [17, 18, 31],
    ),
    _c(
        "finding", "malicious",
        "`203.0.113.45` made 12 failed password attempts against `root`, `admin`, `test` and `oracle`.",
        [18, 20, 22, 23, 24, 25, 26, 27, 28],
    ),
    _c(
        "finding", "malicious",
        "`203.0.113.45` tried the usernames `admin`, `test` and `oracle` and then `root` at 13:41, "
        "all within about half a minute.",
        [17, 18, 19, 20, 21, 22, 23],
    ),
    _c(
        "finding", "malicious",
        "`deploy` logged in from `203.0.113.45` at 13:52:11.",
        [31, 32],
    ),
    _c(
        "finding", "malicious",
        "After getting a root shell, `deploy` installed a persistence mechanism.",
        [33, 34, 57],
    ),
    _c(
        "finding", "malicious",
        "A new account named `backup` was created and added to the sudo group.",
        [35, 36],
    ),
    _c(
        "finding", "suspicious",
        "`bob` entered a wrong password at 07:31, which looks like credential stuffing.",
        [8, 9, 10],
    ),
    _c(
        "finding", "malicious",
        "There were no successful logins from `203.0.113.45`; every attempt failed.",
        list(range(17, 29)),
    ),
    _c(
        "finding", "suspicious",
        "`198.51.100.77` tried the username `ubuntu` at 11:20.",
        [12, 13, 14],
    ),
    _c(
        "finding", "info",
        "`alice` logged in with a public key at 06:58 and ran `apt update` with `sudo`.",
        [1, 2, 3],
    ),
    _c(
        "finding", "malicious",
        "`deploy` logged in from `203.0.113.45` after failed attempts.",
        [31],
    ),
    _c("action", "malicious", "Block `203.0.113.45`.", [31]),
    _c("action", "suspicious", "Rotate credentials and review sudo access.", [33, 34]),
]

SCRIPTS = {
    "faithful": {
        "label": "Faithful demo",
        "note": "Hand-written briefing that passes every check. Not model output.",
        "claims": FAITHFUL,
    },
    "sloppy": {
        "label": "Sloppy demo",
        "note": "Hand-written briefing with one example of each failure a small model tends to make. Not model output.",
        "claims": SLOPPY,
    },
}
