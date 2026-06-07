---
name: git-helper
description: Safe, careful git workflows — status, diffs, branches, and commits.
---

# Git helper

Use this skill when the user asks you to work with git (check status, review
changes, make a branch, or commit). You operate git through the `run_shell`
tool.

## Principles

- **Look before you act.** Always run `git status` and `git diff` (read-only)
  before staging or committing, so you understand what will change.
- **Never push or force-anything unless explicitly asked.** `git push`,
  `git reset --hard`, and similar are destructive — they'll trigger a
  confirmation prompt, and you should explain what they do first.
- **Branch off main for changes** rather than committing straight to it, unless
  the user says otherwise: `git checkout -b <short-descriptive-name>`.

## Typical flow

1. `git status` and `git diff` — understand the current state.
2. If making changes: create a branch.
3. Stage intentionally: `git add <specific files>` (avoid `git add .` unless asked).
4. Commit with a clear message: `git commit -m "..."`.
5. Summarize what you did and what you did NOT do (e.g. "I did not push").
