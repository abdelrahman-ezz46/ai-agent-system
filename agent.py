"""
THE LOOP — the heart of the whole project.

This is the think -> act -> observe cycle that makes the system "agentic"
rather than "a script that calls an LLM once." Read this file top to bottom and
you understand the entire idea.
"""

from memory import Memory
from providers.base import Provider
from safety import Sandbox, is_readonly_command
from tools import Registry
import ui

SYSTEM_PROMPT = """You are a helpful agent operating the user's computer through tools.

Work step by step:
- Inspect before you act. Run read-only commands (ls, cat, grep) to understand
  the situation before making any changes.
- Use one tool at a time and react to its output.
- When the task is done, stop calling tools and give a short, clear summary.

You have LONG-TERM MEMORY that persists across sessions. Everything you remember
about this user is ALREADY listed under "What you remember" below — read it and
answer from it directly. Trust it; only use the `recall` tool to search for
something that is NOT already shown there.

When you learn something durable and useful for next time, call `remember` with
one concise, SELF-CONTAINED sentence — write the fact so it makes sense on its
own later (e.g. "The user's name is Adam", not just "prefers concise answers").
Save preferences, system/project details, and lessons — not one-off task steps.

You may have SKILLS — reusable playbooks for specific tasks. Available skills are
listed under "Available skills" below (name: description). When a task matches a
skill, call `use_skill(name)` to load its full instructions FIRST, then follow
them. If no skill fits, just proceed normally.

You can only operate inside the user's allowed folders: {sandbox}.
Be careful and concise."""

# A hard cap so a confused model can't loop forever burning tokens / commands.
MAX_STEPS = 12


class Agent:
    def __init__(self, provider: Provider, registry: Registry,
                 sandbox: Sandbox, memory: Memory, confirm_dangerous: bool,
                 auto: bool = False, dry_run: bool = False,
                 skills_overview: str = "", view=None):
        self.provider = provider
        self.registry = registry
        self.sandbox = sandbox
        self.memory = memory
        self.confirm_dangerous = confirm_dangerous
        self.skills_overview = skills_overview
        # Where narration goes. Defaults to the rich terminal UI; the
        # Textual TUI injects its own view object with the same methods.
        self.view = view if view is not None else ui
        # Execution modes:
        #   auto    -> autonomous: run dangerous actions without asking
        #   dry_run -> preview only: never execute dangerous actions
        # dry_run wins if both are set (safest).
        self.auto = auto
        self.dry_run = dry_run
        # Short-term: the conversation for the current process run.
        self.messages: list[dict] = []

    def _compose_system(self, goal: str) -> str:
        """Build the system prompt fresh, injecting the most RELEVANT memories.

        This is the 'retrieval' step (RAG): instead of dumping everything, we
        ask the memory store for the facts most relevant to the current goal,
        so the agent starts each session already knowing what matters here.
        """
        base = SYSTEM_PROMPT.format(sandbox=self.sandbox.describe())
        if self.skills_overview:
            base += f"\n\n# Available skills:\n{self.skills_overview}"
        memories = self.memory.context_for(goal)
        if memories:
            return f"{base}\n\n# What you remember about this user:\n{memories}"
        return f"{base}\n\n(You have no saved memories yet.)"

    def run(self, goal: str):
        """Drive one goal to completion."""
        self.messages.append({"role": "user", "content": goal})
        # Recompute each run so newly-remembered facts take effect immediately,
        # and so retrieval is tailored to this specific goal.
        system = self._compose_system(goal)

        for _ in range(MAX_STEPS):
            # ── THINK ───────────────────────────────────────────────────────
            reply = self.provider.chat(
                messages=self.messages,
                tools=self.registry.schemas(),
                system=system,
            )
            self.view.show_thinking(reply.text)

            # Record the assistant turn (text + any tool calls) in memory.
            self.messages.append({
                "role": "assistant",
                "content": reply.text,
                "tool_calls": reply.tool_calls,
            })

            # ── DONE? ───────────────────────────────────────────────────────
            if not reply.wants_tools:
                self.view.show_answer(reply.text)
                return

            # ── ACT + OBSERVE (for each requested tool) ─────────────────────
            for call in reply.tool_calls:
                output = self._execute(call)
                self.view.show_result(output)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": output,
                })

        self.view.info("Reached the step limit — stopping to stay safe.")

    def _execute(self, call) -> str:
        """Run one tool call through the safety gate, then the registry."""
        self.view.show_action(call.name, call.arguments)

        # Each tool decides whether THIS call is dangerous (run_shell flags only
        # destructive commands; write_file always flags). The mode then decides
        # what to do about it.
        tool = self.registry.get(call.name)
        dangerous = bool(tool and tool.is_dangerous_call(call.arguments))

        # Dry-run hardening: a model can mutate files via shell tricks (touch,
        # tee, `cat >`) that the destructive-pattern check misses. In preview
        # mode, treat ANY shell command that isn't provably read-only as
        # dangerous, so "no changes" really means no changes.
        if self.dry_run and call.name == "run_shell":
            if not is_readonly_command(call.arguments.get("command", "")):
                dangerous = True

        if dangerous:
            desc = self._confirm_text(call)

            if self.dry_run:
                # Preview mode: never touch the user's files. Tell the model what
                # WOULD happen so it can keep planning and summarize at the end.
                self.view.info(f"[dry-run] skipped: {desc}")
                return f"[dry-run] No changes made. Would have: {desc}"

            if self.auto:
                self.view.info(f"(auto-approved) {desc}")          # autonomous: no prompt
            elif self.confirm_dangerous:
                if not self.view.confirm(desc):
                    return "Blocked by user: action not performed."

        # Note: file tools also enforce the sandbox internally (path checks),
        # so even an approved call can't escape the allowed folders.
        return self.registry.run(call.name, call.arguments)

    @staticmethod
    def _confirm_text(call) -> str:
        """A human-readable description of what's about to happen."""
        if call.name == "run_shell":
            return f"Run command: {call.arguments.get('command', '')}"
        if call.name == "write_file":
            return f"Write/overwrite file: {call.arguments.get('path', '')}"
        return f"Run {call.name} with {call.arguments}"
