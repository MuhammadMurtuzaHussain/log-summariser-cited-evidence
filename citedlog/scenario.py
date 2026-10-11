"""The 50-line auth log and its answer key.

The log is written by hand as a short story on one host (`web01`, 7 October):
a quiet morning, a slow probe, a brute-force burst, a successful login, a
privilege escalation, a new backdoor account, and the attacker coming back.

Each entry is tagged with the event it belongs to, and the answer key is
derived from those tags, so the line numbers in `data/auth_50.truth.json` can
never drift from the log. Routine lines are tagged too: a briefing that calls
them suspicious has over-read the log.
"""

from __future__ import annotations

from dataclasses import dataclass

HOST = "web01"
DAY = "Oct  7"
LOG_NAME = "auth_50.log"
TRUTH_NAME = "auth_50.truth.json"


@dataclass(frozen=True)
class Entry:
    time: str
    program: str
    pid: int | None
    message: str
    event: str | None = None  # E1..E6, or None for routine activity
    key: bool = False  # a line a good claim should cite for its event

    @property
    def raw(self) -> str:
        who = f"{self.program}[{self.pid}]" if self.pid else self.program
        return f"{DAY} {self.time} {HOST} {who}: {self.message}"


def _e(time, program, pid, message, event=None, key=False):
    return Entry(time, program, pid, message, event, key)


_KEY_A = "RSA SHA256:Zx3kQ9vN1mQ0b2yH7fT4cL8dRwUe5aGjIoPpVnXs6Yk"
_KEY_B = "RSA SHA256:q7LmT2xW0cVbN8aS5dFgH1jKzXeR4yUiOpAsDfGhJk0"

ENTRIES: list[Entry] = [
    # Routine morning: alice logs in and patches, cron runs, bob mistypes once.
    _e("06:58:12", "sshd", 1180, f"Accepted publickey for alice from 10.0.4.21 port 52114 ssh2: {_KEY_A}"),
    _e("06:58:12", "sshd", 1180, "pam_unix(sshd:session): session opened for user alice(uid=1001) by (uid=0)"),
    _e("07:02:40", "sudo", None, "   alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; COMMAND=/usr/bin/apt update"),
    _e("07:02:40", "sudo", None, "pam_unix(sudo:session): session opened for user root(uid=0) by alice(uid=1001)"),
    _e("07:02:52", "sudo", None, "pam_unix(sudo:session): session closed for user root"),
    _e("07:15:03", "CRON", 1302, "pam_unix(cron:session): session opened for user root(uid=0) by (uid=0)"),
    _e("07:15:03", "CRON", 1302, "pam_unix(cron:session): session closed for user root"),
    _e("07:31:47", "sshd", 1344, "Failed password for bob from 10.0.4.35 port 50221 ssh2"),
    _e("07:31:55", "sshd", 1344, "Accepted password for bob from 10.0.4.35 port 50221 ssh2"),
    _e("07:31:55", "sshd", 1344, "pam_unix(sshd:session): session opened for user bob(uid=1002) by (uid=0)"),
    _e("09:12:30", "sshd", 1180, "pam_unix(sshd:session): session closed for user alice"),
    # E1: a slow probe from a second address that never gets in.
    _e("11:20:05", "sshd", 1921, "Invalid user ubuntu from 198.51.100.23 port 60112", "E1"),
    _e("11:20:07", "sshd", 1921, "Failed password for invalid user ubuntu from 198.51.100.23 port 60112 ssh2", "E1", True),
    _e("11:20:09", "sshd", 1921, "Connection closed by invalid user ubuntu 198.51.100.23 port 60112 [preauth]", "E1"),
    _e("12:47:51", "sshd", 2044, "Invalid user pi from 198.51.100.23 port 60390", "E1"),
    _e("12:47:53", "sshd", 2044, "Failed password for invalid user pi from 198.51.100.23 port 60390 ssh2", "E1", True),
    # E2: brute force from 203.0.113.45 across three invalid names, then root.
    _e("13:41:09", "sshd", 2201, "Invalid user admin from 203.0.113.45 port 41022", "E2"),
    _e("13:41:11", "sshd", 2201, "Failed password for invalid user admin from 203.0.113.45 port 41022 ssh2", "E2", True),
    _e("13:41:14", "sshd", 2203, "Invalid user test from 203.0.113.45 port 41030", "E2"),
    _e("13:41:16", "sshd", 2203, "Failed password for invalid user test from 203.0.113.45 port 41030 ssh2", "E2", True),
    _e("13:41:19", "sshd", 2205, "Invalid user oracle from 203.0.113.45 port 41038", "E2"),
    _e("13:41:21", "sshd", 2205, "Failed password for invalid user oracle from 203.0.113.45 port 41038 ssh2", "E2", True),
    _e("13:41:25", "sshd", 2207, "Failed password for root from 203.0.113.45 port 41046 ssh2", "E2", True),
    _e("13:41:28", "sshd", 2207, "Failed password for root from 203.0.113.45 port 41046 ssh2", "E2", True),
    _e("13:41:31", "sshd", 2207, "Failed password for root from 203.0.113.45 port 41046 ssh2", "E2", True),
    _e("13:41:34", "sshd", 2207, "Failed password for root from 203.0.113.45 port 41046 ssh2", "E2", True),
    _e("13:41:34", "sshd", 2207, "error: maximum authentication attempts exceeded for root from 203.0.113.45 port 41046 ssh2 [preauth]", "E2", True),
    _e("13:41:34", "sshd", 2207, "Disconnecting authenticating user root 203.0.113.45 port 41046: Too many authentication failures [preauth]", "E2", True),
    # E3: the same address guesses the deploy password and gets in.
    _e("13:43:02", "sshd", 2219, "Failed password for deploy from 203.0.113.45 port 41102 ssh2", "E3"),
    _e("13:43:06", "sshd", 2219, "Failed password for deploy from 203.0.113.45 port 41102 ssh2", "E3"),
    _e("13:43:11", "sshd", 2219, "Accepted password for deploy from 203.0.113.45 port 41102 ssh2", "E3", True),
    _e("13:43:11", "sshd", 2219, "pam_unix(sshd:session): session opened for user deploy(uid=1003) by (uid=0)", "E3", True),
    # E4: deploy opens a root shell with sudo.
    _e("13:44:20", "sudo", None, "   deploy : TTY=pts/1 ; PWD=/home/deploy ; USER=root ; COMMAND=/bin/bash", "E4", True),
    _e("13:44:20", "sudo", None, "pam_unix(sudo:session): session opened for user root(uid=0) by deploy(uid=1003)", "E4", True),
    # E5: a new account is created, made a sudoer and given a password.
    _e("13:44:51", "useradd", 2250, "new user: name=support, UID=1004, GID=1004, home=/home/support, shell=/bin/bash", "E5", True),
    _e("13:44:58", "usermod", 2257, "add 'support' to group 'sudo'", "E5", True),
    _e("13:45:06", "passwd", 2260, "pam_unix(passwd:chauthtok): password changed for support", "E5", True),
    _e("13:46:30", "sudo", None, "pam_unix(sudo:session): session closed for user root", "E4"),
    _e("13:46:44", "sshd", 2219, "Received disconnect from 203.0.113.45 port 41102:11: disconnected by user", "E3"),
    _e("13:46:44", "sshd", 2219, "Disconnected from user deploy 203.0.113.45 port 41102", "E3"),
    _e("13:46:44", "sshd", 2219, "pam_unix(sshd:session): session closed for user deploy", "E3"),
    # E6: the attacker returns as the new account and reads the shadow file.
    _e("14:02:17", "sshd", 2301, "Accepted password for support from 203.0.113.45 port 52871 ssh2", "E6", True),
    _e("14:02:17", "sshd", 2301, "pam_unix(sshd:session): session opened for user support(uid=1004) by (uid=0)", "E6", True),
    _e("14:02:49", "sudo", None, "   support : TTY=pts/2 ; PWD=/home/support ; USER=root ; COMMAND=/usr/bin/cat /etc/shadow", "E6", True),
    _e("14:02:49", "sudo", None, "pam_unix(sudo:session): session opened for user root(uid=0) by support(uid=1004)", "E6"),
    # Routine afternoon.
    _e("14:10:03", "CRON", 2377, "pam_unix(cron:session): session opened for user root(uid=0) by (uid=0)"),
    _e("14:10:03", "CRON", 2377, "pam_unix(cron:session): session closed for user root"),
    _e("14:31:12", "sshd", 2402, f"Accepted publickey for alice from 10.0.4.21 port 53340 ssh2: {_KEY_B}"),
    _e("14:31:12", "sshd", 2402, "pam_unix(sshd:session): session opened for user alice(uid=1001) by (uid=0)"),
    _e("14:33:40", "sudo", None, "   alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; COMMAND=/usr/bin/journalctl -u ssh"),
]

# Title, severity, and the words a claim must use to count as describing the event.
# E6 needs "shadow", not "support": the first live run cited the later login lines in a claim
# that only said the account had been created, and "support" alone credited it with both events.
EVENTS = {
    "E1": {
        "title": "Slow probe from 198.51.100.23 that never gets in",
        "severity": "suspicious",
        "terms": ["198.51.100.23"],
    },
    "E2": {
        "title": "Brute force from 203.0.113.45 against admin, test, oracle and root",
        "severity": "malicious",
        "terms": ["203.0.113.45"],
    },
    "E3": {
        "title": "deploy password guessed and a login accepted",
        "severity": "malicious",
        "terms": ["deploy"],
    },
    "E4": {
        "title": "deploy opens a root shell with sudo",
        "severity": "malicious",
        "terms": ["sudo", "root"],
    },
    "E5": {
        "title": "New account support created, made a sudoer and given a password",
        "severity": "malicious",
        "terms": ["support"],
    },
    "E6": {
        "title": "Attacker returns as support and reads /etc/shadow",
        "severity": "malicious",
        "terms": ["shadow"],
    },
}


def log_text() -> str:
    return "\n".join(entry.raw for entry in ENTRIES) + "\n"


def truth() -> dict:
    """The answer key: which lines belong to which event, derived from the tags."""
    events = []
    for event_id, meta in EVENTS.items():
        lines = [i for i, e in enumerate(ENTRIES, start=1) if e.event == event_id]
        key_lines = [i for i, e in enumerate(ENTRIES, start=1) if e.event == event_id and e.key]
        events.append({"id": event_id, **meta, "lines": lines, "key_lines": key_lines})
    routine = [i for i, e in enumerate(ENTRIES, start=1) if e.event is None]
    return {
        "log": LOG_NAME,
        "line_count": len(ENTRIES),
        "note": (
            "A claim finds an event when it is backed by its citation, cites at least one key "
            "line and uses at least one of the event's terms. Routine lines are ordinary "
            "activity: a claim rated suspicious or malicious that cites only these has over-read the log."
        ),
        "events": events,
        "routine_lines": routine,
    }
