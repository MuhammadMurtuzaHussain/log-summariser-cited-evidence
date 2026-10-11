# What the verifier checks

Generated from `citedlog/verify.py` by `python -m citedlog docs`. Do not edit by hand.

The verifier answers one question for each claim: *do the lines it cites contain what it says?* It uses string matching only, never a second model, so the same claim always gets the same verdict.

## Outcomes

| Outcome | Meaning |
|---|---|
| `verified` | Every line exists and every address, name, time and count in the claim is in the cited lines. |
| `unchecked` | Every line exists, but the claim states nothing the checker can test, so the citation proves little. |
| `unsupported` | The lines exist, but something the claim states is not in them. |
| `invalid` | The citation itself is broken: missing, malformed, or pointing past the end of the log. |

## Rules

| Rule | Outcome if it fails | What it checks | What it cannot catch |
|---|---|---|---|
| `NO_CITATION` | `invalid` | The claim lists at least one line number. | Nothing: an empty citation is always a failure. |
| `BAD_CITATION` | `invalid` | Every entry in `lines` is a whole number, not text, a range string or a decimal. | A range written in the claim text (for example 'lines 17-28') is ignored; only `lines` counts. |
| `LINE_OUT_OF_RANGE` | `invalid` | Every cited line number exists in the log (1 to the last line). | A line that exists but is the wrong one. The next four rules look at that. |
| `ENTITY_NOT_IN_CITED_LINES` | `unsupported` | Every IPv4 address, username known from the log, and `backticked` or 'named' term in the claim appears in at least one cited line. | A username the log never mentions and the claim does not put in backticks or after 'named'. |
| `TIME_NOT_IN_CITED_LINES` | `unsupported` | Every clock time in the claim (13:43 or 13:43:11) appears in at least one cited line. | Durations and ordering ('within 30 seconds', 'before the login'). |
| `COUNT_MISMATCH` | `unsupported` | 'N failed password attempts' (also failed logins, authentication failures) equals the number of cited 'Failed password' lines. When the claim names an address or a user that those lines are from or against, only the lines that match count. 'At least N' and 'more than N' are compared as such. | Counts of other things, such as distinct usernames or sessions. When a claim names several users, failures against any of them count, so a user named only for what happened next can widen the count. |
| `ABSENCE_CONTRADICTED` | `unsupported` | A claim that something never succeeded ('no successful login from X') is checked against the whole log, because absence cannot be shown by citing lines. | Absence claims that name no address or user. |
| `TOO_BROAD` | `unsupported` | The claim cites no more than 60% of the log. Citing nearly everything would otherwise satisfy every rule above. | Padding below that share. It is reported as a note (PADDING), not a failure. |

## Notes that do not change the outcome

- `PADDING`: cited lines that contain none of the names, addresses or times in the claim. Shown on the claim so an analyst can see which citations are along for the ride.
- Over-read: a claim rated `suspicious` or `malicious` whose cited lines are all routine activity (needs the answer key, `*.truth.json`). The claim can be fully backed by its lines and still be a poor reading.

## What a pass does not mean

A verified claim has real evidence behind its details. It is not proof that the claim reads the evidence correctly. 'This is a brute-force attack' cites the right lines whether or not the log supports that conclusion, and the verifier cannot tell the difference. Judgement stays with the analyst; the verifier makes the evidence quick to open.

Threshold used by `TOO_BROAD`: more than 60% of the log.
