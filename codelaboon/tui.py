"""
Interactive terminal UI for codelaboon, built on Textual.

The TUI is an optional surface: the core harness stays dependency-light
(`requests` only), and this module imports `textual` lazily through
`codelaboon.cli.run_tui`. Install it with `pip install 'codelaboon[tui]'`.

Layout: a sidebar browses providers and their model catalogue (fed live by
providers such as `ourfree`), and the main pane is a multi-turn chat against
the selected provider/model. `ctrl+d` runs the same diagnostics as
`codelaboon doctor` inline.
"""

import functools
from typing import Any, Dict, List, Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, RichLog, Static

from codelaboon.cli import CodelaboonCLI


class CodelaboonTuiApp(App[None]):
    """Provider browser and multi-turn chat for the codelaboon harness."""

    TITLE = "codelaboon"
    SUB_TITLE = "free model harness"

    CSS = """
    #body { height: 1fr; }
    #sidebar { width: 34; border-right: solid $primary; }
    #sidebar Label { padding: 0 1; }
    #providers, #models { height: 1fr; }
    #main { width: 1fr; }
    #status { height: 1; padding: 0 1; background: $panel; }
    #chat { height: 1fr; border-bottom: solid $primary; }
    #prompt { border-title-align: left; }
    """

    BINDINGS = [
        ("ctrl+p", "focus_providers", "Providers"),
        ("ctrl+m", "focus_models", "Models"),
        ("ctrl+r", "refresh_models", "Refresh models"),
        ("ctrl+d", "run_doctor", "Doctor"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.cli = CodelaboonCLI()
        self.history: List[Dict[str, str]] = []
        self._provider_names: List[str] = []
        self._model_names: List[str] = []
        self._current_provider: Optional[str] = None
        self._current_model: Optional[str] = None
        self._models_worker: Any = None
        self._chat_worker: Any = None
        self._pending: Any = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            with Vertical(id="sidebar"):
                yield Label("Providers [dim](ctrl+p)[/]")
                yield ListView(id="providers")
                yield Label("Models [dim](ctrl+m)[/]")
                yield ListView(id="models")
            with Vertical(id="main"):
                yield Static("no provider selected", id="status")
                yield RichLog(id="chat", markup=False, highlight=False, wrap=True)
                yield Input(placeholder="Type a message, Enter to send…", id="prompt")
        yield Footer()

    def on_mount(self) -> None:
        self.cli.load_providers()
        providers_list = self.query_one("#providers", ListView)
        self._provider_names = sorted(self.cli.providers)
        providers_list.extend(
            [ListItem(Label(self._provider_label(name))) for name in self._provider_names]
        )
        self._log("codelaboon TUI — pick a provider (ctrl+p), a model (ctrl+m), then type.")
        self._log("ourfree and kilo models are free; other providers need their own API key.")
        if self._provider_names:
            self._select_provider(self._provider_names[0])

    # ── helpers ────────────────────────────────────────────────────────────

    def _provider_label(self, name: str) -> str:
        provider = self.cli.providers.get(name)
        configured = bool(provider and provider.validate_api_key())
        return f"{'●' if configured else '○'} {name}"

    def _log(self, text: str) -> None:
        self.query_one("#chat", RichLog).write(text)

    def _selected_provider(self) -> Optional[str]:
        return self._current_provider

    def _selected_model(self) -> Optional[str]:
        return self._current_model

    def _update_status(self) -> None:
        provider = self._current_provider or "no provider"
        model = self._current_model or "no model"
        turns = len([m for m in self.history if m["role"] == "user"])
        self.query_one("#status", Static).update(
            f"{provider} · {model} · {turns} turn(s) this session"
        )

    # ── providers and models ───────────────────────────────────────────────

    def _select_provider(self, name: str) -> None:
        self._current_provider = name
        self._current_model = None
        self.history.clear()
        self._log(f"─ provider: {name} ─")
        self._update_status()
        providers_list = self.query_one("#providers", ListView)
        if name in self._provider_names:
            try:  # Keep the widget highlight in step with programmatic picks.
                providers_list.index = self._provider_names.index(name)
            except (ValueError, IndexError):
                pass
        self._load_models(name)

    def _load_models(self, name: str) -> None:
        provider = self.cli.providers.get(name)
        if provider is None:
            return
        self._models_worker = self.run_worker(
            functools.partial(self._models_job, name, provider),
            thread=True,
            exclusive=True,
            group="models",
        )

    def _models_job(self, name: str, provider: Any) -> None:
        try:
            models = provider.list_models()
        except Exception as e:  # Discovery must never take the TUI down.
            self.call_from_thread(self._on_models, name, [], f"model discovery failed: {e}")
            return
        self.call_from_thread(self._on_models, name, models, "")

    def _on_models(self, name: str, models: List[str], error: str) -> None:
        models_list = self.query_one("#models", ListView)
        models_list.clear()
        self._model_names = list(models)
        if self._model_names:
            models_list.extend(
                [ListItem(Label(model)) for model in self._model_names]
            )
            try:
                models_list.index = 0
            except (ValueError, IndexError):
                pass
            self._current_model = self._model_names[0]
        if error:
            self._log(f"error> {error}")
        self._log(f"{len(self._model_names)} model(s) available for {name}.")
        self._update_status()

    # ── chat ───────────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._send(event.value)
        event.input.value = ""

    def _send(self, text: str) -> None:
        text = text.strip()
        if not text:
            return

        provider_name = self._selected_provider()
        if not provider_name:
            self._log("error> select a provider first (ctrl+p)")
            return
        provider = self.cli.providers.get(provider_name)
        if provider is None:
            self._log(f"error> provider '{provider_name}' is not loaded")
            return
        if not provider.validate_api_key():
            self._log(
                f"error> {provider_name} is not configured — run: "
                f"codelaboon configure {provider_name}"
            )
            return
        model = self._selected_model()
        if not model:
            self._log("error> select a model first (ctrl+m)")
            return

        self.history.append({"role": "user", "content": text})
        self._log(f"you> {text}")
        self._update_status()
        # The snapshot freezes the turn so a mid-flight selection change
        # cannot mix contexts.
        self._pending = (provider_name, provider, model, list(self.history))
        self._chat_worker = self.run_worker(
            self._chat_job, thread=True, exclusive=True, group="chat"
        )

    def _chat_job(self) -> None:
        provider_name, provider, model, messages = self._pending
        try:
            reply = provider.chat(model, messages, temperature=0.7, max_tokens=1000)
        except Exception as e:
            self.call_from_thread(self._log, f"error> {e}")
            return
        self.call_from_thread(self._on_reply, messages, reply)

    def _on_reply(self, messages: List[Dict[str, str]], reply: str) -> None:
        self.history.clear()
        self.history.extend(messages)
        self.history.append({"role": "assistant", "content": reply})
        self._log(f"assistant> {reply}")
        self._update_status()

    # ── actions ────────────────────────────────────────────────────────────

    def action_focus_providers(self) -> None:
        self.query_one("#providers", ListView).focus()

    def action_focus_models(self) -> None:
        self.query_one("#models", ListView).focus()

    def action_refresh_models(self) -> None:
        name = self._selected_provider()
        if name:
            self._log(f"refreshing the catalogue for {name}…")
            self._load_models(name)

    def action_run_doctor(self) -> None:
        import contextlib
        import io

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.cli.doctor()
        self._log(buffer.getvalue().rstrip())

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Route list selections: provider picks load models, model picks switch."""
        index = event.control.index
        if event.control.id == "providers":
            if index is not None and 0 <= index < len(self._provider_names):
                self._select_provider(self._provider_names[index])
        elif event.control.id == "models":
            if index is not None and 0 <= index < len(self._model_names):
                self._current_model = self._model_names[index]
                self.history.clear()
                self._log("─ model switched, context cleared ─")
                self._update_status()


def run_app() -> None:
    """Run the TUI."""
    CodelaboonTuiApp().run()
