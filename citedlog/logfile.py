"""Read an auth log and collect the facts a claim can be checked against.

The checker never asks a model what a log line means. It only asks whether the
names, addresses, times and counts in a claim can be found in the lines the
claim cites, so everything here is plain string matching.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?!\d|\.\d)")
CLOCK = re.compile(r"(?<![\d:])\d{1,2}:\d{2}(?::\d{2})?(?!\d|:\d)")

_SYSLOG = re.compile(
    r"^(?P<stamp>\w{3}\s+\d+\s+(?P<time>\d\d:\d\d:\d\d))\s+(?P<host>\S+)\s+"
    r"(?P<program>[^\s:\[]+)(?:\[(?P<pid>\d+)\])?:\s?(?P<message>.*)$"
)

# Where a username can appear in OpenSSH, sudo, PAM and shadow-utils messages.
_USER_PATTERNS = [
    re.compile(r"\bInvalid user (\S+) from"),
    re.compile(r"\bFailed \w+ for (?:invalid user )?(\S+) from"),
    re.compile(r"\bAccepted \w+ for (\S+) from"),
    re.compile(r"\bsession (?:opened|closed) for user (\w[\w.-]*)"),
    re.compile(
        r"\b(?:authenticating user|Disconnected from user|"
        r"Connection closed by (?:invalid |authenticating )?user) (\S+)"
    ),
    re.compile(r"\bmaximum authentication attempts exceeded for (?:invalid user )?(\S+) from"),
    re.compile(r"^\s*(\w[\w.-]*) : TTY="),
    re.compile(r"\bnew user: name=([\w.-]+)"),
    re.compile(r"\badd '([\w.-]+)' to group"),
    re.compile(r"\bpassword changed for (\S+)"),
]


@dataclass(frozen=True)
class LogLine:
    no: int
    raw: str
    stamp: str
    time: str
    host: str
    program: str
    pid: str
    message: str
    head: str = ""  # "Oct  7 13:41:09 web01"
    proc: str = ""  # "sshd[2201]: " (the separator is kept so head + " " + proc + message == raw)


class Log:
    """A log held as numbered lines. Numbering starts at 1, as in `nl` or an editor."""

    def __init__(self, text: str, name: str = "auth.log") -> None:
        self.name = name
        self.text = text if text.endswith("\n") else text + "\n"
        self.sha256 = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        self.lines: list[LogLine] = []
        # Split on newlines only. str.splitlines() would also cut at U+2028, form feeds and
        # similar, so a line number here would stop matching `nl`, `grep -n` and an editor.
        for no, raw in enumerate(self.text[:-1].split("\n"), start=1):
            raw = raw.removesuffix("\r")
            m = _SYSLOG.match(raw)
            if m:
                parts = m.groupdict()
                self.lines.append(
                    LogLine(
                        no=no,
                        raw=raw,
                        stamp=parts["stamp"],
                        time=parts["time"],
                        host=parts["host"],
                        program=parts["program"],
                        pid=parts["pid"] or "",
                        message=parts["message"],
                        head=raw[: m.start("program")].rstrip(),
                        proc=raw[m.start("program") : m.start("message")],
                    )
                )
            else:
                self.lines.append(LogLine(no, raw, "", "", "", "", "", raw))
        self.users = self._collect_users()
        self.ips = {ip for line in self.lines for ip in IPV4.findall(line.raw)}

    @classmethod
    def from_file(cls, path: str | Path) -> Log:
        p = Path(path)
        return cls(p.read_text(encoding="utf-8"), name=p.name)

    def __len__(self) -> int:
        return len(self.lines)

    def line(self, no: int) -> LogLine:
        return self.lines[no - 1]

    def has(self, no: int) -> bool:
        return isinstance(no, int) and not isinstance(no, bool) and 1 <= no <= len(self.lines)

    def numbered(self) -> str:
        """The log as the model sees it: `[17] Oct  7 13:41:09 web01 sshd[2201]: ...`."""
        return "\n".join(f"[{line.no}] {line.raw}" for line in self.lines)

    def _collect_users(self) -> set[str]:
        users: set[str] = set()
        for line in self.lines:
            for pattern in _USER_PATTERNS:
                for match in pattern.finditer(line.message):
                    users.add(match.group(1).rstrip(":;,"))
        return users


def format_lines(numbers: list[int]) -> str:
    """[17, 18, 19, 22] -> 'L17-L19, L22' (ASCII, for the console and reasons)."""
    nums = sorted(set(numbers))
    if not nums:
        return "no lines"
    runs: list[list[int]] = [[nums[0], nums[0]]]
    for n in nums[1:]:
        if n == runs[-1][1] + 1:
            runs[-1][1] = n
        else:
            runs.append([n, n])
    return ", ".join(f"L{a}" if a == b else f"L{a}-L{b}" for a, b in runs)
