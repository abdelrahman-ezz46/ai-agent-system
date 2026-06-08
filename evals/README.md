# Evals — measuring the agent, not guessing

This folder turns "I think the agent works" into a **measured success rate** you
can track as you change things. It's the difference between *building* an agent
and *engineering* one.

## What's here

| File | Purpose |
|---|---|
| `tasks.py` | The eval suite — each task is a goal + a deterministic success check. |
| `runner.py` | Runs the suite, reports a per-task table and an overall success rate. |
| `compare.py` | A/B harness — runs each task N times with a feature OFF vs ON to measure its true effect. |

## How a task works

Each task:
1. Creates a **fresh temp folder** (isolated sandbox — no state leaks between tasks).
2. Runs an optional **setup** (e.g. drop some files in).
3. Points a sandboxed agent (in `--auto`, unattended) at the **goal**.
4. Runs a **check** against the result — files on disk, or the final answer text.

Pass/fail is objective, so the score is meaningful.

## Running it

```bash
python evals/runner.py                       # all tasks, once each
python evals/runner.py --runs 3              # repeat each task 3× (recommended)
python evals/runner.py --only organize_txt   # a single task
python evals/runner.py --no-verify           # disable self-verification
python evals/runner.py --provider claude --model claude-opus-4-8
```

## Why multiple runs matter

LLM outputs are **stochastic** — a small local model makes different mistakes on
different runs. A single pass is too noisy to trust (we watched the score swing
80% → 90% → 80% with no code change). To measure honestly:

- Run each task several times and report the **mean** pass rate.
- To judge a feature, **A/B it**: same tasks, feature off vs on, N runs each.

```bash
python evals/compare.py --runs 3   # self-verification OFF vs ON
```

That's the methodology this suite is built around — measure through the noise,
don't cherry-pick a lucky run.

## Adding a task

Append an `Eval` to `EVALS` in `tasks.py`:

```python
Eval(
    "my_task",
    "The goal text given to the agent.",
    setup=lambda wd: _w(wd, "input.txt", "data"),     # optional
    check=lambda c: (_r(c.workdir, "out.txt") or "").strip() == "expected",
)
```

The `check` receives a context with `workdir`, `answer`, `messages`, and `steps`.
