"""
A/B harness — measures the effect of self-verification through the noise.

LLM outputs are stochastic, so a single run per task is misleading. This runs
every task N times with verification OFF and N times with it ON, then reports
the mean pass rate for each — the honest way to claim "feature X improved
success from A% to B%".

Usage:
    python evals/compare.py --runs 3
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import yaml  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from providers import build_provider  # noqa: E402
from runner import run_one  # noqa: E402
from tasks import EVALS  # noqa: E402

console = Console()


def main(argv=None):
    p = argparse.ArgumentParser(description="A/B the self-verification feature.")
    p.add_argument("--runs", type=int, default=3, help="Runs per task per condition.")
    p.add_argument("--provider")
    p.add_argument("--model")
    args = p.parse_args(argv)

    config = yaml.safe_load(open(os.path.join(ROOT, "config.yaml")))
    if args.provider:
        config["provider"] = args.provider
    if args.model:
        config["model"] = args.model
    provider = build_provider(config)

    console.print(f"[bold]A/B: self-verification OFF vs ON · {args.runs} runs/task · "
                  f"{config['provider']}:{config['model']}[/bold]")
    console.print(f"[dim]{len(EVALS)} tasks × {args.runs} runs × 2 conditions = "
                  f"{len(EVALS) * args.runs * 2} agent runs[/dim]\n")

    passes = {}  # (task, verify) -> count
    for verify in (False, True):
        label = "ON " if verify else "OFF"
        for ev in EVALS:
            got = 0
            for _ in range(args.runs):
                ok, _, _ = run_one(ev, provider, verify=verify)
                got += int(ok)
            passes[(ev.name, verify)] = got
            console.print(f"[dim]verify {label}  {ev.name:<20} {got}/{args.runs}[/dim]")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Task")
    table.add_column("verify OFF", justify="right")
    table.add_column("verify ON", justify="right")
    table.add_column("Δ", justify="right")

    off_total = on_total = 0
    for ev in EVALS:
        off = passes[(ev.name, False)]
        on = passes[(ev.name, True)]
        off_total += off
        on_total += on
        delta = on - off
        d = f"[green]+{delta}[/green]" if delta > 0 else (
            f"[red]{delta}[/red]" if delta < 0 else "·")
        table.add_row(ev.name, f"{off}/{args.runs}", f"{on}/{args.runs}", d)

    n = len(EVALS) * args.runs
    console.print()
    console.print(table)
    off_pct = 100 * off_total / n
    on_pct = 100 * on_total / n
    console.print(f"\n[bold]Self-verification OFF: {off_total}/{n} ({off_pct:.0f}%)"
                  f"  →  ON: {on_total}/{n} ({on_pct:.0f}%)"
                  f"   [{'+' if on_pct >= off_pct else ''}{on_pct - off_pct:.0f} pts][/bold]")


if __name__ == "__main__":
    main()
