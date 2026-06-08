"""
Eval tasks — each is a goal plus a deterministic success check.

The whole point of evals: instead of *believing* the agent works, we *measure*
it. Each task sets up a fresh sandbox folder, gives the agent a goal, then checks
the resulting state (files on disk, or the final answer text). Pass/fail is
objective, so we can track a success rate and watch it move as we improve things.

A check receives a context object with:
    ctx.workdir   the folder the agent operated in
    ctx.answer    the agent's final answer text
    ctx.messages  the full conversation
    ctx.steps     how many tool-using turns it took
"""

import os
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Eval:
    name: str
    goal: str
    check: Callable          # check(ctx) -> bool
    setup: Optional[Callable] = None   # setup(workdir) -> None, runs before the agent


# ── tiny helpers for setup/checks ────────────────────────────────────────────
def _w(workdir: str, name: str, content: str) -> None:
    with open(os.path.join(workdir, name), "w") as f:
        f.write(content)


def _r(workdir: str, name: str):
    path = os.path.join(workdir, name)
    return open(path).read() if os.path.isfile(path) else None


def _exists(workdir: str, name: str) -> bool:
    return os.path.exists(os.path.join(workdir, name))


# ── the suite ────────────────────────────────────────────────────────────────
EVALS = [
    Eval(
        "write_exact",
        "Create a file called hello.txt containing exactly: hello world",
        check=lambda c: (_r(c.workdir, "hello.txt") or "").strip() == "hello world",
    ),
    Eval(
        "count_txt",
        "Count how many .txt files are in the current folder and write just "
        "that number (digits only) to count.md",
        setup=lambda wd: [_w(wd, n, "x") for n in ("a.txt", "b.txt", "c.txt", "d.md")],
        check=lambda c: (_r(c.workdir, "count.md") or "").strip() == "3",
    ),
    Eval(
        "uppercase",
        "Read input.txt, convert its contents to UPPERCASE, and write the result "
        "to output.txt",
        setup=lambda wd: _w(wd, "input.txt", "hello there\nsecond line"),
        check=lambda c: (_r(c.workdir, "output.txt") or "").strip() == "HELLO THERE\nSECOND LINE",
    ),
    Eval(
        "organize_txt",
        "Move all .txt files into a new folder called texts. Leave other files "
        "where they are.",
        setup=lambda wd: [_w(wd, n, "x") for n in ("a.txt", "b.txt", "photo.jpg")],
        check=lambda c: (_exists(c.workdir, "texts/a.txt") and _exists(c.workdir, "texts/b.txt")
                         and _exists(c.workdir, "photo.jpg") and not _exists(c.workdir, "a.txt")),
    ),
    Eval(
        "delete_file",
        "Delete the file junk.log but keep everything else.",
        setup=lambda wd: [_w(wd, "junk.log", "x"), _w(wd, "keep.txt", "y")],
        check=lambda c: (not _exists(c.workdir, "junk.log")) and _exists(c.workdir, "keep.txt"),
    ),
    Eval(
        "append_line",
        "Append a new line with the text line2 to the file log.txt (keep the "
        "existing content).",
        setup=lambda wd: _w(wd, "log.txt", "line1\n"),
        check=lambda c: all(s in (_r(c.workdir, "log.txt") or "") for s in ("line1", "line2")),
    ),
    Eval(
        "word_count",
        "How many words are in essay.txt? Write just the number (digits only) "
        "to wc.md",
        setup=lambda wd: _w(wd, "essay.txt", "the quick brown fox jumps over the lazy dog"),
        check=lambda c: (_r(c.workdir, "wc.md") or "").strip() == "9",
    ),
    Eval(
        "qa_answer",
        "Read facts.txt and tell me what the capital is.",
        setup=lambda wd: _w(wd, "facts.txt", "The capital of this country is Paris."),
        check=lambda c: "paris" in (c.answer or "").lower(),
    ),
    Eval(
        "find_then_read",
        "There is exactly one file ending in .secret in this folder. Read it and "
        "write its contents to revealed.txt",
        setup=lambda wd: _w(wd, "treasure.secret", "the code is 4271"),
        check=lambda c: "4271" in (_r(c.workdir, "revealed.txt") or ""),
    ),
    Eval(
        "two_step_transform",
        "Read numbers.txt (one number per line), add them all up, and write only "
        "the total to sum.txt",
        setup=lambda wd: _w(wd, "numbers.txt", "10\n20\n30\n40"),
        check=lambda c: (_r(c.workdir, "sum.txt") or "").strip() == "100",
    ),
]
