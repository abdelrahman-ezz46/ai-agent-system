"""
Entry point. Wires everything together and runs either a one-shot goal or the
interactive REPL.

    config.yaml ─▶ provider ─┐
                  tools ─────┼─▶ Agent ─▶ run(goal) loop
                  sandbox ───┘

Usage:
    python main.py                         interactive REPL
    python main.py "organize my downloads" run one goal, then exit
    python main.py --auto "..."            autonomous: no confirmation prompts
    python main.py --dry-run "..."         preview dangerous actions, change nothing
    python main.py --provider claude --model claude-opus-4-8 "..."
"""

import argparse
import sys

import yaml

import ui
from agent import Agent
from embeddings import build_embedder
from memory import Memory
from providers import build_provider
from safety import Sandbox
from skills import load_skills, register_skills
from tools import build_registry


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="agent",
        description="A terminal AI agent that operates your computer.",
    )
    # Positional goal words are joined into one string. If none, we start the REPL.
    p.add_argument("goal", nargs="*", help="A goal to run once, then exit.")
    p.add_argument("--auto", action="store_true",
                   help="Autonomous mode: run dangerous actions without asking.")
    p.add_argument("--dry-run", action="store_true",
                   help="Preview only: never execute dangerous actions.")
    p.add_argument("--tui", action="store_true",
                   help="Launch the full-screen Textual UI.")
    p.add_argument("--provider", help="Override the provider from config.yaml.")
    p.add_argument("--model", help="Override the model from config.yaml.")
    return p.parse_args(argv)


def build_agent(config: dict, args: argparse.Namespace):
    """Assemble the agent + the bits the banner needs. Raises on provider error."""
    provider = build_provider(config)

    sandbox = Sandbox(config.get("allowed_paths", []))
    embedder = build_embedder(config)   # None disables semantic recall
    memory = Memory(config.get("memory_file", "agent_memory.json"), embedder=embedder)
    registry = build_registry(sandbox, memory)

    # Load user skills and register their tools + the use_skill tool.
    skills = load_skills(config.get("skills_dir", "skills"), context={"sandbox": sandbox})
    overview = register_skills(registry, skills)

    agent = Agent(
        provider=provider,
        registry=registry,
        sandbox=sandbox,
        memory=memory,
        confirm_dangerous=config.get("confirm_dangerous", True),
        auto=args.auto,
        dry_run=args.dry_run,
        skills_overview=overview,
        verify=config.get("verify", True),
    )
    return agent, sandbox, memory, skills


def current_mode(args: argparse.Namespace) -> str:
    if args.dry_run:
        return "dry-run (no changes)"
    if args.auto:
        return "auto (autonomous)"
    return "interactive"


def main(argv=None):
    args = parse_args(argv)
    config = load_config()

    # CLI overrides win over config.yaml.
    if args.provider:
        config["provider"] = args.provider
    if args.model:
        config["model"] = args.model

    try:
        agent, sandbox, memory, skills = build_agent(config, args)
    except Exception as e:
        ui.blocked(f"Could not set up agent: {e}")
        sys.exit(1)

    # ── Full-screen Textual UI ───────────────────────────────────────────────
    if args.tui:
        from tui import AgentTUI
        subtitle = (f"{config['provider']} · {config['model']} · "
                    f"{memory.count()} memories · {len(skills)} skills · {current_mode(args)}")
        initial = " ".join(args.goal) if args.goal else None
        AgentTUI(agent, subtitle=subtitle, initial_goal=initial).run()
        return

    # ── One-shot mode: a goal was given on the command line ──────────────────
    if args.goal:
        goal = " ".join(args.goal)
        ui.info(f"mode: {current_mode(args)}")
        try:
            agent.run(goal)
        except KeyboardInterrupt:
            ui.info("\n(interrupted)")
            sys.exit(130)
        return

    # ── Interactive REPL ─────────────────────────────────────────────────────
    ui.banner(config["provider"], config["model"], sandbox.describe(),
              memory_count=memory.count(), memory_mode=memory.mode(),
              mode=current_mode(args), skill_count=len(skills))

    while True:
        try:
            goal = ui.ask_goal()
        except (EOFError, KeyboardInterrupt):
            ui.info("\nbye 👋")
            break

        if goal.strip().lower() in ("exit", "quit", "q"):
            ui.info("bye 👋")
            break
        if not goal.strip():
            continue

        try:
            agent.run(goal)
        except KeyboardInterrupt:
            ui.info("\n(interrupted — back to prompt)")
        except Exception as e:
            ui.blocked(f"Something went wrong: {e}")


if __name__ == "__main__":
    main()
