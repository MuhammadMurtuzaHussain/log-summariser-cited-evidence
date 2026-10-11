import json
import re
from pathlib import Path

import pytest

from citedlog.backends import Reply
from citedlog.dashboard import render_html
from citedlog.logfile import Log
from citedlog.runs import load_runs, make_run
from citedlog.scenario import LOG_NAME, log_text
from citedlog.backends import scripted

WEB = Path(__file__).resolve().parent.parent / "citedlog" / "web"


def page_and_data(log, runs, key=None):
    html = render_html(log, key, runs)
    match = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.DOTALL)
    return html, json.loads(match.group(1))


@pytest.fixture
def demo_runs(log):
    return [make_run(scripted(n), log, demo_name=n) for n in ("faithful", "sloppy")]


def test_page_is_one_self_contained_file(log, answer_key, demo_runs):
    html, _ = page_and_data(log, demo_runs, answer_key)
    assert "{{" not in html and "}}" not in html.split("<style>")[0]
    assert not re.search(r"""(?:src|href)\s*=\s*["']?https?:""", html)
    assert not re.search(r"url\(\s*['\"]?https?:", html)
    assert not re.search(r"<link\b|<img\b|@import|fetch\(|XMLHttpRequest|WebSocket|sendBeacon", html)
    assert html.count("data:font/woff2;base64,") == 4
    assert len(html) < 400_000


def test_embedded_data_holds_every_run_and_all_fifty_lines(log, answer_key, demo_runs):
    _, data = page_and_data(log, demo_runs, answer_key)
    assert [r["id"] for r in data["runs"]] == ["demo-faithful", "demo-sloppy"]
    assert len(data["log"]["lines"]) == 50 and len(data["events"]) == 6
    assert data["default"] == "demo-sloppy"  # the more instructive of the two scripted demos
    sloppy = data["runs"][1]
    assert sloppy["claims"][4]["verdict"]["status"] == "invalid" and sloppy["claims"][6]["over_read"] is True
    assert sloppy["note"].endswith("Not model output.")


def test_the_first_real_run_is_the_default(log, answer_key, demo_runs):
    real = make_run(Reply('{"claims": []}', "llama3.2", "ollama", 3.2, {"temperature": 0.0, "seed": 7}), log)
    _, data = page_and_data(log, [real, *demo_runs], answer_key)
    assert data["default"] == real["id"]


def test_the_reading_is_in_the_html_so_it_reads_without_scripts(log, answer_key, demo_runs):
    html, data = page_and_data(log, demo_runs, answer_key)
    assert data["runs"][1]["hero"] in html.split("<script")[0].replace("&#x27;", "'")
    assert "<noscript>" in html and "Rated" not in html.split("<noscript>")[1].split("</noscript>")[0]


def test_hostile_log_and_model_text_cannot_break_out_of_the_page(tmp_path):
    evil = "</script><img src=x onerror=alert(1)><!-- &amp; " + chr(0x2028) + " end"
    text = log_text().replace("Invalid user admin", f"Invalid user {evil}", 1)
    log = Log(text, LOG_NAME)
    reply = Reply(json.dumps({"claims": [{"kind": "headline", "severity": "info", "text": evil, "lines": [17]}]}),
                  evil, "ollama", 1.0, {})  # fmt: skip
    run = make_run(reply, log)
    html, data = page_and_data(log, [run], None)
    assert "<img src=x" not in html and "</script><img" not in html
    assert html.count("</script>") == 2  # the data block and the code block, nothing else
    assert data["runs"][0]["claims"][0]["text"] == evil  # the data itself is untouched
    assert evil in data["log"]["lines"][16]["msg"]
    js = (WEB / "app.js").read_text()
    assert "innerHTML" not in js and "insertAdjacentHTML" not in js and "document.write" not in js


def test_unreadable_reply_still_renders(log, answer_key):
    run = make_run(Reply("Sorry, no.", "tiny", "ollama", 1.0, {}), log)
    html, data = page_and_data(log, [run], answer_key)
    assert data["runs"][0]["parse_error"] and "could not be read" in data["runs"][0]["hero"]


def test_runs_made_against_another_log_are_left_out(tmp_path, log, demo_runs):
    from citedlog.runs import save_run

    other = Log("Oct  7 06:58:12 web01 sshd[1]: hello\n", LOG_NAME)
    stale = make_run(scripted("faithful"), other, demo_name="faithful")
    save_run(stale, tmp_path)
    runs, skipped = load_runs(tmp_path, log)
    assert runs == [] and "different log" in skipped[0]


# ---------------------------------------------------------------- colour


def _channel(c):
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_):
    r, g, b = (int(hex_[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def ratio(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def tokens(block):
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", block))


@pytest.fixture(scope="module")
def themes():
    css = (WEB / "app.css").read_text()
    light = tokens(re.search(r"^:root\{(.*?)\n\}", css, re.DOTALL | re.MULTILINE).group(1))
    dark = tokens(re.search(r':root\[data-theme="dark"\]\{(.*?)\n\}', css, re.DOTALL).group(1))
    media = tokens(re.search(r"@media \(prefers-color-scheme:dark\)\{(.*?)\n\}\n", css, re.DOTALL).group(1))
    return {"light": light, "dark": {**light, **dark}, "media": {**light, **media}}


def test_the_os_dark_scope_and_the_toggle_dark_scope_agree(themes):
    assert themes["media"] == themes["dark"]


TEXT_ON = ["surface", "page", "wash", "hover", "ok-wash", "none-wash", "warn-wash", "bad-wash"]


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_text_meets_4_5_to_1_on_every_surface_it_sits_on(themes, theme):
    t = themes[theme]
    for ink in ("ink", "ink-2"):
        for bg in TEXT_ON:
            assert ratio(t[ink], t[bg]) >= 4.5, (theme, ink, bg, ratio(t[ink], t[bg]))
    assert ratio(t["ink"], t["token"]) >= 4.5  # a highlighted word inside a cited line
    assert ratio(t["link"], t["surface"]) >= 4.5  # the claim links under the log


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_status_glyphs_meet_3_to_1_on_their_fills(themes, theme):
    t = themes[theme]
    for name in ("ok", "none", "warn", "bad"):
        assert ratio(t[f"on-{name}"], t[name]) >= 3.0, (theme, name, ratio(t[f"on-{name}"], t[name]))


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_status_marks_are_distinct_from_each_other_and_visible_on_the_page(themes, theme):
    t = themes[theme]
    marks = [t[n] for n in ("ok", "none", "warn", "bad")]
    assert len(set(marks)) == 4
    # Colour is never the only channel (each state has its own glyph and label), so the bar is the
    # lighter one for non-text marks: 1.7:1 here; amber/orange sit below 3:1 on light by design.
    assert all(ratio(m, t["surface"]) >= 1.7 for m in marks)


def test_every_status_has_a_glyph_a_label_and_a_class_in_the_script():
    js = (WEB / "app.js").read_text()
    for status, cls in [("verified", "s-ok"), ("unchecked", "s-none"), ("unsupported", "s-warn"), ("invalid", "s-bad")]:
        assert re.search(rf"{status}: \{{ label: \"[^\"]+\", cls: \"{cls}\" \}}", js)
        assert f"{status}: \"M" in js
        assert f".{cls}{{" in (WEB / "app.css").read_text()


def test_each_model_run_says_which_prompt_made_it(log, answer_key, demo_runs):
    v2 = make_run(Reply('{"claims": []}', "llama3.2", "ollama", 3.2, {"temperature": 0.0, "seed": 7}), log, prompt_version="v2")
    old = make_run(Reply('{"claims": []}', "llama3.2", "ollama", 3.2, {"temperature": 0.0, "seed": 7}), log)
    del old["prompt_version"]  # a run saved before versions existed is recognised from its hash
    _, data = page_and_data(log, [v2, old, *demo_runs], answer_key)
    assert [r["prompt_version"] for r in data["runs"]] == ["v2", "v1", None, None]
    assert 'Prompt " + run.prompt_version' in (WEB / "app.js").read_text()
