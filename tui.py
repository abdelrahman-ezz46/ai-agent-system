"""
The full-screen Textual UI (M6).

Run with:  python main.py --tui

Layout: a scrolling transcript of the agent's narration (thinking, actions,
results, answers) with an input box at the bottom. The agent runs in a
background worker thread so the UI stays responsive; dangerous actions pop a
modal confirmation.

The trick that makes this clean: the Agent narrates through an injectable
`view` object (see agent.py). In the terminal that's the rich `ui` module; here
it's `TuiView`, which forwards the same calls into the Textual log via
`call_from_thread` (safe cross-thread UI updates).
"""

from __future__ import annotations

import threading

from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, RichLog, Static


class ConfirmScreen(ModalScreen[bool]):
    """A modal that asks the user to approve a dangerous action.

    Approve/deny by clicking a button or pressing y / n.
    """

    BINDINGS = [
        Binding("y", "yes", "Yes"),
        Binding("n", "no", "No"),
        Binding("escape", "no", "No"),
    ]

    def __init__(self, prompt: str):
        super().__init__()
        self.prompt = prompt

    def compose(self) -> ComposeResult:
        with Container(id="confirm-box"):
            yield Static(f"⚠  Confirm action\n\n{self.prompt}", markup=False)
            with Horizontal(id="confirm-buttons"):
                yield Button("Yes (y)", variant="error", id="yes")
                yield Button("No (n)", variant="primary", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


class TuiView:
    """Narration sink that writes the agent's output into the Textual log.

    Has the same method surface the agent expects (show_thinking, show_action,
    show_result, show_answer, info, confirm) — so it's a drop-in for the rich
    `ui` module. Every call hops back onto the UI thread via call_from_thread.
    """

    def __init__(self, app: "AgentTUI"):
        self.app = app

    def _write(self, renderable) -> None:
        self.app.call_from_thread(self.app.log_widget.write, renderable)

    def show_thinking(self, text: str) -> None:
        if text and text.strip():
            self._write(Text("🧠 " + text.strip(), style="yellow"))

    def show_action(self, name: str, arguments: dict) -> None:
        args = "  ".join(f"{k}={v!r}" for k, v in arguments.items())
        self._write(Panel(Text.assemble((name, "bold"), ("  " + args, "")),
                          title="🔧 action", border_style="blue", title_align="left"))

    def show_result(self, output: str) -> None:
        self._write(Panel(Text(output), title="📄 result",
                          border_style="grey50", title_align="left"))

    def show_answer(self, text: str) -> None:
        self._write(Panel(Markdown(text or "(no answer)"), title="✅ answer",
                          border_style="green", title_align="left"))

    def info(self, message: str) -> None:
        self._write(Text(message, style="dim"))

    def confirm(self, prompt: str) -> bool:
        # Called from the worker thread. We can't await a modal across threads,
        # so we push the screen with a callback and block this thread on an
        # Event until the user answers. push_screen (callback form) doesn't need
        # a worker context — unlike push_screen_wait, which does.
        done = threading.Event()
        box = {"result": False}

        def on_close(value) -> None:
            box["result"] = bool(value)
            done.set()

        # IMPORTANT: build the ConfirmScreen ON the UI thread. Textual widgets
        # create an asyncio.Lock in __init__, which (on Python 3.9) needs a
        # running loop — constructing it in this worker thread would crash.
        self.app.call_from_thread(self.app.open_confirm, prompt, on_close)
        done.wait()
        return box["result"]


class AgentTUI(App):
    TITLE = "🤖 Terminal Agent"
    CSS = """
    #log { height: 1fr; border: round $primary; padding: 0 1; }
    #goal { dock: bottom; }
    ConfirmScreen { align: center middle; }
    #confirm-box {
        width: 70%; height: auto; padding: 1 2;
        border: round $warning; background: $surface;
    }
    #confirm-buttons { height: auto; align: center middle; margin-top: 1; }
    #confirm-buttons Button { margin: 0 1; }
    """
    BINDINGS = [Binding("ctrl+q", "quit", "Quit")]

    def __init__(self, agent, subtitle: str = "", initial_goal: str | None = None):
        super().__init__()
        self.agent = agent
        self._subtitle = subtitle
        self._initial_goal = initial_goal

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="log", wrap=True, markup=False, highlight=False)
        yield Input(placeholder="Type a goal and press Enter…  (Ctrl+Q to quit)", id="goal")
        yield Footer()

    def on_mount(self) -> None:
        self.log_widget = self.query_one("#log", RichLog)
        self.sub_title = self._subtitle
        self.agent.view = TuiView(self)             # redirect narration into the UI
        self.log_widget.write(Text("Welcome. Type a goal below to get started.", style="dim"))
        self.query_one("#goal", Input).focus()
        if self._initial_goal:
            self._submit(self._initial_goal)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        goal = event.value.strip()
        self.query_one("#goal", Input).value = ""
        if goal:
            self._submit(goal)

    def _submit(self, goal: str) -> None:
        self.log_widget.write(Text(f"› {goal}", style="bold green"))
        self._run_agent(goal)

    def _run_agent(self, goal: str) -> None:
        # thread=True so the (blocking) agent loop doesn't freeze the UI.
        self.run_worker(lambda: self._safe_run(goal), thread=True, exclusive=True)

    def _safe_run(self, goal: str) -> None:
        try:
            self.agent.run(goal)
        except Exception as e:
            self.call_from_thread(self.log_widget.write, Text(f"error: {e}", style="red"))

    def open_confirm(self, prompt: str, on_close) -> None:
        """Build + push the confirm modal. Runs on the UI thread (see TuiView)."""
        self.push_screen(ConfirmScreen(prompt), on_close)
