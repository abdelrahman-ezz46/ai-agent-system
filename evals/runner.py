"""
Eval runner — measures the agent's task success rate.

For each task: make a fresh temp folder, run setup, point a sandboxed agent at
it (in --auto so it runs unattended), execute the goal, then run the check.
Prints a per-task table and an overall success rate.

Usage:
    python evals/runner.py                      # run all, using config.yaml
    python evals/runner.py --only write_exact,qa_answer
    python evals/runner.py --runs 3             # repeat each (non-deterministic models)
    python evals/runner.py --provider claude --model claude-opus-4-8
"""

import argparse
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass

# Make the project root importable when run as `python evals/runner.py`.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import yaml  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from agent import Agent  # noqa: E402
from memory import Memory  # noqa: E402
from providers import build_provider  # noqa: E402
from safety import Sandbox  # noqa: E402
from skills import load_skills, register_skills  # noqa: E402
from tools import build_registry  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tasks import EVALS  # noqa: E402

console = Console()


class QuietView:
    """A no-op view so eval runs don't spam the terminal with panels."""
    def show_thinking(self, *a): pass
    def show_action(self, *a): pass
    def show_result(self, *a): pass
    def show_answer(self, *a): pass
    def info(self, *a): pass
    def confirm(self, *a): return True   # not used in --auto, but safe


@dataclass
class Ctx:
    workdir: str
    answer: str
    messages: list
    steps: int


def _final_answer(messages: list) -> str:
    for m in reversed(messages):
        if m["role"] == "assistant" and m.get("content") and not m.get("tool_calls"):
            return m["content"]
    return ""


def run_one(ev, provider, verify: bool = True) -> tuple[bool, int, float]:
    """Run a single eval in an isolated sandbox. Returns (passed, steps, seconds)."""
    workdir = tempfile.mkdtemp(prefix="eval_")
    original_cwd = os.getcwd()
    try:
        if ev.setup:
            ev.setup(workdir)

        # Fresh, isolated agent per task (no memory bleed between tasks).
        sandbox = Sandbox([workdir])
        memory = Memory(os.path.join(workdir, "_mem.json"), embedder=None)
        registry = build_registry(sandbox, memory)
        skills = load_skills(os.path.join(ROOT, "skills"), context={"sandbox": sandbox})
        overview = register_skills(registry, skills)
        agent = Agent(provider, registry, sandbox, memory,
                      confirm_dangerous=False, auto=True, view=QuietView(),
                      skills_overview=overview, verify=verify)

        # chdir into the sandbox so the agent's relative paths and shell
        # commands land in the right place ("current folder" == this task's dir).
        os.chdir(workdir)
        start = time.time()
        try:
            agent.run(ev.goal)
        except Exception:
            pass
        elapsed = time.time() - start

        ctx = Ctx(
            workdir=workdir,
            answer=_final_answer(agent.messages),
            messages=agent.messages,
            steps=sum(1 for m in agent.messages
                      if m["role"] == "assistant" and m.get("tool_calls")),
        )
        try:
            passed = bool(ev.check(ctx))
        except Exception:
            passed = False
        return passed, ctx.steps, elapsed
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(workdir, ignore_errors=True)


def main(argv=None):
    p = argparse.ArgumentParser(description="Run the agent eval suite.")
    p.add_argument("--only", help="Comma-separated task names to run.")
    p.add_argument("--runs", type=int, default=1, help="Repeat each task N times.")
    p.add_argument("--provider")
    p.add_argument("--model")
    p.add_argument("--no-verify", action="store_true",
                   help="Disable self-verification (for A/B comparison).")
    args = p.parse_args(argv)

    config = yaml.safe_load(open(os.path.join(ROOT, "config.yaml")))
    if args.provider:
        config["provider"] = args.provider
    if args.model:
        config["model"] = args.model
    provider = build_provider(config)

    evals = EVALS
    if args.only:
        wanted = {n.strip() for n in args.only.split(",")}
        evals = [e for e in EVALS if e.name in wanted]

    console.print(f"[bold]Running {len(evals)} eval(s) × {args.runs} run(s) "
                  f"on {config['provider']}:{config['model']}[/bold]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Task")
    table.add_column("Result")
    table.add_column("Pass rate", justify="right")
    table.add_column("Avg steps", justify="right")
    table.add_column("Avg time", justify="right")

    total_pass = total_runs = 0
    for ev in evals:
        console.print(f"[dim]running {ev.name}…[/dim]")
        passes = steps_sum = 0
        time_sum = 0.0
        for _ in range(args.runs):
            ok, steps, secs = run_one(ev, provider, verify=not args.no_verify)
            passes += int(ok)
            steps_sum += steps
            time_sum += secs
        total_pass += passes
        total_runs += args.runs
        all_pass = passes == args.runs
        mark = "[green]PASS[/green]" if all_pass else (
            "[red]FAIL[/red]" if passes == 0 else "[yellow]FLAKY[/yellow]")
        table.add_row(ev.name, mark, f"{passes}/{args.runs}",
                      f"{steps_sum/args.runs:.1f}", f"{time_sum/args.runs:.1f}s")

    console.print()
    console.print(table)
    rate = 100 * total_pass / total_runs if total_runs else 0
    color = "green" if rate >= 80 else ("yellow" if rate >= 50 else "red")
    console.print(f"\n[bold {color}]Success rate: {total_pass}/{total_runs} "
                  f"({rate:.0f}%)[/bold {color}]")


if __name__ == "__main__":
    main()
