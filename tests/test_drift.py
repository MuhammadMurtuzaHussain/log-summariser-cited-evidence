"""The committed data, runs and docs are generated from the code. If they differ, regenerate them."""

import json
from pathlib import Path

import pytest

from citedlog.backends import scripted
from citedlog.demo_scripts import SCRIPTS
from citedlog.docs import verifier_rules_md
from citedlog.runs import make_run
from citedlog.scenario import LOG_NAME, TRUTH_NAME, log_text, truth

ROOT = Path(__file__).resolve().parent.parent
HINT = " (run `python -m citedlog demo`)"


def test_log_matches_the_scenario():
    assert (ROOT / "data" / LOG_NAME).read_text() == log_text(), "data log has drifted" + HINT


def test_answer_key_matches_the_scenario():
    assert json.loads((ROOT / "data" / TRUTH_NAME).read_text()) == truth(), "answer key has drifted" + HINT


def test_rules_doc_matches_the_code():
    assert (ROOT / "docs" / "verifier-rules.md").read_text() == verifier_rules_md(), "rules doc has drifted" + HINT


@pytest.mark.parametrize("name", list(SCRIPTS))
def test_scripted_runs_match_the_scripts(name, log):
    expected = make_run(scripted(name), log, demo_name=name)
    on_disk = json.loads((ROOT / "runs" / f"demo-{name}.json").read_text())
    assert on_disk == expected, f"demo-{name}.json has drifted" + HINT
