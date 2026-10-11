"""Command line: generate, summarise, verify, dashboard, docs, demo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import render
from .backends import DEFAULT_MODEL, BackendError, ollama_chat, scripted
from .dashboard import build_dashboard
from .demo_scripts import SCRIPTS
from .docs import verifier_rules_md
from .logfile import Log
from .prompt import DEFAULT_PROMPT, PROMPTS, system_prompt, user_message
from .runs import assess, load_run, make_run, save_run
from .scenario import LOG_NAME, TRUTH_NAME, log_text, truth

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG = ROOT / "data" / LOG_NAME


def _truth_for(log_path: Path) -> dict | None:
    path = log_path.with_suffix(".truth.json")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def cmd_generate(args) -> int:
    out = Path(args.data)
    out.mkdir(parents=True, exist_ok=True)
    (out / LOG_NAME).write_text(log_text(), encoding="utf-8")
    (out / TRUTH_NAME).write_text(json.dumps(truth(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out / LOG_NAME} and {out / TRUTH_NAME}")
    return 0


def cmd_docs(args) -> int:
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(verifier_rules_md(), encoding="utf-8")
    print(f"Wrote {path}")
    return 0


def _report(run: dict, log: Log, truth_data: dict | None, markdown: str | None) -> dict:
    assessed = assess(run, log, truth_data)
    print(render.console(run, assessed, log))
    if markdown:
        Path(markdown).write_text(render.markdown(run, assessed, log), encoding="utf-8")
        print(f"\nWrote {markdown}")
    return assessed


def cmd_summarise(args) -> int:
    log = Log.from_file(args.log)
    truth_data = _truth_for(Path(args.log))
    try:
        if args.script:
            reply = scripted(args.script)
        else:
            print(f"Asking {args.model} to brief on {log.name} ({len(log)} lines). This can take a minute...", flush=True)
            reply = ollama_chat(
                args.model,
                system_prompt(args.prompt),
                user_message(log),
                host=args.host,
                temperature=args.temperature,
                seed=args.seed,
                timeout=args.timeout,
            )
    except BackendError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    run = make_run(reply, log, demo_name=args.script, prompt_version=args.prompt)
    path = save_run(run, args.runs)
    print(f"Saved {path}\n")
    assessed = _report(run, log, truth_data, args.markdown)
    return _gate(assessed, args.min_grounding)


def cmd_verify(args) -> int:
    log = Log.from_file(args.log)
    run = load_run(args.run)
    if run["log"]["sha256"] != log.sha256:
        print(f"error: {args.run} was made against a different log than {args.log}.", file=sys.stderr)
        return 2
    assessed = _report(run, log, _truth_for(Path(args.log)), args.markdown)
    return _gate(assessed, args.min_grounding)


def _gate(assessed: dict, minimum: float) -> int:
    rate = assessed["score"]["grounding_rate"]
    if minimum and (rate is None or rate < minimum):
        shown = "n/a" if rate is None else f"{rate:.0%}"
        print(f"\nGate failed: {shown} of claims are backed by the log; the minimum is {minimum:.0%}.", file=sys.stderr)
        return 1
    return 0


def cmd_dashboard(args) -> int:
    path, notes = build_dashboard(args.runs, args.log, args.out)
    for note in notes:
        print(f"skipped {note}", file=sys.stderr)
    print(f"Wrote {path}")
    return 0


def cmd_demo(args) -> int:
    """Everything that needs no model: data, scripted runs, rules doc, dashboard."""
    cmd_generate(argparse.Namespace(data=str(ROOT / "data")))
    log = Log.from_file(DEFAULT_LOG)
    for name in SCRIPTS:
        save_run(make_run(scripted(name), log, demo_name=name), ROOT / "runs")
    cmd_docs(argparse.Namespace(out=str(ROOT / "docs" / "verifier-rules.md")))
    return cmd_dashboard(
        argparse.Namespace(runs=str(ROOT / "runs"), log=str(DEFAULT_LOG), out=str(ROOT / "site" / "index.html"))
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="citedlog", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("generate", help="write the 50-line log and its answer key")
    p.add_argument("--data", default=str(ROOT / "data"))
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("docs", help="write docs/verifier-rules.md from the code")
    p.add_argument("--out", default=str(ROOT / "docs" / "verifier-rules.md"))
    p.set_defaults(func=cmd_docs)

    p = sub.add_parser("summarise", help="brief on the log with a local model, then verify the briefing")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model name (default: %(default)s)")
    p.add_argument("--host", default=None, help="Ollama URL (default: $OLLAMA_HOST or http://localhost:11434)")
    p.add_argument("--log", default=str(DEFAULT_LOG))
    p.add_argument("--runs", default=str(ROOT / "runs"), help="where to save the run")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--timeout", type=float, default=600.0)
    p.add_argument(
        "--prompt",
        choices=sorted(PROMPTS),
        default=DEFAULT_PROMPT,
        help="instructions sent to the model (default: %(default)s; v2 asks for specifics and shows an example)",
    )
    p.add_argument("--script", choices=sorted(SCRIPTS), help="use a scripted demo instead of a model")
    p.add_argument("--markdown", help="also write the briefing as Markdown to this file")
    p.add_argument("--min-grounding", type=float, default=0.0, help="exit 1 if fewer claims than this share are backed")
    p.set_defaults(func=cmd_summarise)

    p = sub.add_parser("verify", help="re-check a saved run against the log")
    p.add_argument("run")
    p.add_argument("--log", default=str(DEFAULT_LOG))
    p.add_argument("--markdown")
    p.add_argument("--min-grounding", type=float, default=0.0)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("dashboard", help="build the single-file HTML dashboard from every saved run")
    p.add_argument("--runs", default=str(ROOT / "runs"))
    p.add_argument("--log", default=str(DEFAULT_LOG))
    p.add_argument("--out", default=str(ROOT / "site" / "index.html"))
    p.set_defaults(func=cmd_dashboard)

    p = sub.add_parser("demo", help="regenerate data, scripted runs, docs and dashboard (no model needed)")
    p.set_defaults(func=cmd_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
