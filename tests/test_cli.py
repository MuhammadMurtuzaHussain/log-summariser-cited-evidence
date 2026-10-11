import json

import pytest

from citedlog.cli import main
from citedlog.scenario import LOG_NAME, TRUTH_NAME, log_text, truth


@pytest.fixture
def workdir(tmp_path):
    (tmp_path / LOG_NAME).write_text(log_text())
    (tmp_path / TRUTH_NAME).write_text(json.dumps(truth()))
    return tmp_path


def test_generate_writes_log_and_answer_key(tmp_path, capsys):
    assert main(["generate", "--data", str(tmp_path)]) == 0
    assert (tmp_path / LOG_NAME).read_text() == log_text()
    assert json.loads((tmp_path / TRUTH_NAME).read_text()) == truth()


def test_summarise_with_a_script_saves_a_run_and_prints_the_verdicts(workdir, capsys):
    code = main(["summarise", "--script", "sloppy", "--log", str(workdir / LOG_NAME), "--runs", str(workdir / "runs")])
    out = capsys.readouterr().out
    assert code == 0
    assert (workdir / "runs" / "demo-sloppy.json").exists()
    assert "UNSUPPORTED" in out and "INVALID" in out and "Cites L57; the log runs from L1 to L50." in out
    assert "Rated suspicious, but every line it cites is routine activity." in out


def test_min_grounding_is_a_gate(workdir, capsys):
    args = ["--log", str(workdir / LOG_NAME), "--runs", str(workdir / "runs"), "--min-grounding", "0.9"]
    assert main(["summarise", "--script", "faithful", *args]) == 0
    assert main(["summarise", "--script", "sloppy", *args]) == 1
    assert "Gate failed: 36%" in capsys.readouterr().err


def test_verify_rechecks_a_saved_run_and_writes_markdown(workdir, capsys):
    main(["summarise", "--script", "faithful", "--log", str(workdir / LOG_NAME), "--runs", str(workdir / "runs")])
    md = workdir / "briefing.md"
    code = main(["verify", str(workdir / "runs" / "demo-faithful.json"), "--log", str(workdir / LOG_NAME), "--markdown", str(md)])
    assert code == 0
    text = md.read_text()
    assert text.startswith("# Auth log briefing: auth_50.log")
    assert "✓ **C2** (malicious)" in text and "[L18, L20, L22-L28]" in text


def test_verify_refuses_a_run_made_against_a_different_log(workdir, tmp_path_factory, capsys):
    main(["summarise", "--script", "faithful", "--log", str(workdir / LOG_NAME), "--runs", str(workdir / "runs")])
    other = tmp_path_factory.mktemp("other") / "auth_50.log"
    other.write_text("Oct  7 06:58:12 web01 sshd[1]: hello\n")
    code = main(["verify", str(workdir / "runs" / "demo-faithful.json"), "--log", str(other)])
    assert code == 2 and "different log" in capsys.readouterr().err


def test_summarise_against_a_fake_ollama_end_to_end(workdir, fake_ollama, capsys):
    from citedlog.demo_scripts import FAITHFUL

    body = {"message": {"role": "assistant", "content": json.dumps({"claims": FAITHFUL})}}
    with fake_ollama(body=body) as server:
        code = main([
            "summarise", "--model", "llama3.2", "--host", server.url,
            "--log", str(workdir / LOG_NAME), "--runs", str(workdir / "runs"),
        ])  # fmt: skip
    assert code == 0
    (path,) = (workdir / "runs").glob("*llama3.2.json")
    run = json.loads(path.read_text())
    assert run["source"] == "ollama" and run["model"] == "llama3.2" and run["parse_error"] is None
    assert run["options"]["temperature"] == 0.0 and run["log"]["lines"] == 50
    assert "All 8 claims are backed by the lines they cite" in capsys.readouterr().out


def test_a_model_that_returns_prose_is_recorded_not_crashed_on(workdir, fake_ollama, capsys):
    body = {"message": {"content": "I'm sorry, I can't help with that."}}
    with fake_ollama(body=body) as server:
        code = main([
            "summarise", "--model", "tiny", "--host", server.url,
            "--log", str(workdir / LOG_NAME), "--runs", str(workdir / "runs"), "--min-grounding", "0.5",
        ])  # fmt: skip
    out = capsys.readouterr()
    assert code == 1 and "Could not read the reply" in out.out
    (path,) = (workdir / "runs").glob("*tiny.json")
    assert json.loads(path.read_text())["parse_error"]


def test_ollama_not_running_exits_2_with_instructions(workdir, capsys):
    code = main(["summarise", "--host", "http://127.0.0.1:9", "--timeout", "2",
                 "--log", str(workdir / LOG_NAME), "--runs", str(workdir / "runs")])  # fmt: skip
    err = capsys.readouterr().err
    assert code == 2 and "ollama serve" in err and not (workdir / "runs").exists()


def test_a_log_without_an_answer_key_can_still_be_briefed_and_verified(tmp_path, capsys):
    log = tmp_path / "mine.log"
    log.write_text(log_text())
    code = main(["summarise", "--script", "faithful", "--log", str(log), "--runs", str(tmp_path / "runs")])
    out = capsys.readouterr().out
    assert code == 0 and "planted events" not in out


def _faithful_body():
    from citedlog.demo_scripts import FAITHFUL

    return {"message": {"role": "assistant", "content": json.dumps({"claims": FAITHFUL})}}


def test_the_prompt_version_reaches_the_model_and_the_run_file(workdir, fake_ollama):
    from citedlog.prompt import PROMPTS

    with fake_ollama(body=_faithful_body()) as server:
        main(["summarise", "--model", "llama3.2", "--host", server.url, "--prompt", "v2",
              "--log", str(workdir / LOG_NAME), "--runs", str(workdir / "runs")])  # fmt: skip
    assert server.requests[0]["json"]["messages"][0]["content"] == PROMPTS["v2"]
    (path,) = (workdir / "runs").glob("*llama3.2.json")
    run = json.loads(path.read_text())
    assert run["prompt_version"] == "v2" and run["label"] == "llama3.2 (prompt v2)"


def test_the_default_prompt_is_version_one_and_keeps_the_plain_model_name(workdir, fake_ollama):
    from citedlog.prompt import PROMPTS, prompt_sha256

    with fake_ollama(body=_faithful_body()) as server:
        main(["summarise", "--model", "llama3.2", "--host", server.url,
              "--log", str(workdir / LOG_NAME), "--runs", str(workdir / "runs")])  # fmt: skip
    assert server.requests[0]["json"]["messages"][0]["content"] == PROMPTS["v1"]
    (path,) = (workdir / "runs").glob("*llama3.2.json")
    run = json.loads(path.read_text())
    from citedlog.logfile import Log

    assert run["prompt_version"] == "v1" and run["label"] == "llama3.2"
    assert run["prompt_sha256"] == prompt_sha256(Log.from_file(workdir / LOG_NAME), "v1")


def test_two_prompts_on_one_model_make_two_distinguishable_runs(workdir, fake_ollama):
    import time

    with fake_ollama(body=_faithful_body()) as server:
        for version in ("v1", "v2"):
            main(["summarise", "--model", "llama3.2", "--host", server.url, "--prompt", version,
                  "--log", str(workdir / LOG_NAME), "--runs", str(workdir / "runs")])  # fmt: skip
            time.sleep(1.1)  # run ids carry the second they were made
    labels = sorted(json.loads(p.read_text())["label"] for p in (workdir / "runs").glob("*.json"))
    assert labels == ["llama3.2", "llama3.2 (prompt v2)"]


def test_an_unknown_prompt_version_is_refused_before_any_request(workdir, capsys):
    with pytest.raises(SystemExit) as stop:
        main(["summarise", "--prompt", "v9", "--log", str(workdir / LOG_NAME), "--runs", str(workdir / "runs")])
    assert stop.value.code == 2 and "invalid choice: 'v9'" in capsys.readouterr().err
