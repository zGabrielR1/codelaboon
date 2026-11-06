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
import secrets
from typing import Any, Dict, List, Optional

from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text

from textual.screen import ModalScreen
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, RichLog, Static

from codelaboon.cli import CodelaboonCLI


class Picker(ModalScreen[str]):
    BINDINGS = [("escape", "dismiss_picker", "Close")]
    DEFAULT_CSS = """
    Picker { align: center middle; background: #00000088; }
    #picker-dialog { width: 70; max-width: 95%; height: 24; background: #131315; padding: 1 2; }
    #picker-title { height: 2; text-style: bold; }
    #picker-list { height: 1fr; }
    """

    def __init__(self, title, choices):
        super().__init__()
        self.heading, self.choices = title, choices
        self.filtered = list(choices)

    def compose(self):
        with Vertical(id="picker-dialog"):
            yield Label(self.heading + "  /  esc close", id="picker-title")
            yield Input(placeholder="Search...", id="picker-search")
            yield ListView(id="picker-list")

    def on_mount(self):
        self.fill("")
        self.query_one(Input).focus()

    def fill(self, value):
        self.filtered = [(key, label) for key, label in self.choices if value.lower() in label.lower()]
        view = self.query_one(ListView)
        view.clear()
        view.extend([ListItem(Label(label, markup=False)) for _, label in self.filtered])
        if self.filtered:
            view.index = 0

    def on_input_changed(self, event):
        self.fill(event.value)

    def on_input_submitted(self, event):
        if self.filtered:
            self.dismiss(self.filtered[0][0])

    def on_list_view_selected(self, event):
        if event.control.index is not None:
            self.dismiss(self.filtered[event.control.index][0])

    def action_dismiss_picker(self):
        self.dismiss("")


ACCOUNT_PROVIDERS = {"chatgpt", "claude", "gemini", "freebuff"}
ACCOUNT_LABELS = {"chatgpt": "ChatGPT", "claude": "Claude", "gemini": "Gemini", "freebuff": "Freebuff"}


class ProviderLogin(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel_login", "Close")]
    DEFAULT_CSS = """
    ProviderLogin { align: center middle; background: #00000088; }
    #login-dialog { width: 66; max-width: 95%; height: auto; background: #131315; padding: 2 3; }
    #login-message { height: auto; margin: 1 0; }
    #login-actions { height: 3; }
    """

    def __init__(self, provider: str = "chatgpt"):
        super().__init__()
        self.provider = provider
        self.label = ACCOUNT_LABELS.get(provider, provider.title())

    def compose(self):
        with Vertical(id="login-dialog"):
            yield Label(f"Connect {self.label}", markup=False)
            yield Static("Sign in to load your account's available models.\nComplete authorization in your browser, then return here.", id="login-message")
            with Horizontal(id="login-actions"):
                yield Button(f"Continue with {self.label}", id="continue-login")
                yield Button("Later", id="later-login")

    def on_button_pressed(self, event):
        if event.button.id == "later-login":
            self.dismiss(False)
        else:
            self.query_one("#continue-login", Button).disabled = True
            self.query_one("#login-message", Static).update("Waiting for browser authorization...\nThis can take up to five minutes.")
            self.app.start_provider_login(self, self.provider)

    def action_cancel_login(self):
        self.dismiss(False)


# Kept for callers that imported the ChatGPT-only dialog.
ChatGPTLogin = ProviderLogin


class CodelaboonTuiApp(App[None]):
    """Provider browser and multi-turn chat for the codelaboon harness."""

    TITLE = "codelaboon"
    SUB_TITLE = "model workspace"

    CSS = """
    Screen { background: #171719; color: #eeeeee; }
    #body { height: 1fr; }
    #main { width: 1fr; padding: 1 4; }
    #sidebar { width: 32; background: #131315; padding: 2 3; border-left: solid #2b2b2e; }
    #session-info { height: auto; color: #a3a3ac; }
    #providers, #models, .catalog-label { display: none; }
    #status { height: 2; color: #a3a3ac; }
    #chat { height: 1fr; background: #171719; }
    #home { height: 1fr; content-align: left bottom; color: #eeeeee; padding-bottom: 3; }
    #prompt { background: #131315; border: none; border-left: solid #73daca; padding: 1 2; height: 5; }
    #prompt:focus { border-left: solid #73daca; }
    #hint { height: 2; padding-top: 1; color: #a3a3ac; }
    .home #chat { display: none; }
    .home #hint { height: 1fr; }
    Footer { background: #171719; }
    ListView { background: #131315; }
    ListView > ListItem.--highlight { background: #333333; }
    """

    BINDINGS = [
        ("ctrl+s", "sessions", "Sessions"),
        ("ctrl+l", "new_conversation", "New chat"),
        ("ctrl+b", "toggle_sidebar", "Sidebar"),
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
        self._generation = 0
        self._busy = False
        self._session_id = secrets.token_hex(16)
        self._discovery = 0

    def compose(self) -> ComposeResult:
        with Horizontal(id="body", classes="home"):
            with Vertical(id="main"):
                yield Static("", id="status", markup=False)
                yield Static("codelaboon / model workspace\n\nMake room for your next idea.\nChoose a model. Follow a question.", id="home", markup=False)
                yield RichLog(id="chat", markup=False, highlight=False, wrap=True)
                yield Input(placeholder="Ask anything...  /help for commands", id="prompt")
                yield Static("ctrl+p providers    ctrl+m models    ctrl+b sidebar", id="hint")
            with Vertical(id="sidebar"):
                yield Static("New conversation", id="session-info", markup=False)
                yield Label("Providers", classes="catalog-label")
                yield ListView(id="providers")
                yield Label("Models", classes="catalog-label")
                yield ListView(id="models")
        yield Footer()

    def on_mount(self) -> None:
        self.cli.load_providers()
        providers_list = self.query_one("#providers", ListView)
        self._provider_names = sorted(self.cli.providers)
        providers_list.extend(
            [ListItem(Label(self._provider_label(name))) for name in self._provider_names]
        )
        self._log("codelaboon TUI — pick a provider (ctrl+p), a model (ctrl+m), then type.")
        self._log("Gemini (Google account), ourfree and kilo are free; other providers need their own key or plan.")
        if self._provider_names:
            self._select_provider(self._provider_names[0], prompt_login=False)
        self.query_one("#prompt", Input).focus()
        if self.size.width < 100:
            self.query_one("#sidebar").display = False

    # ── helpers ────────────────────────────────────────────────────────────

    def _provider_label(self, name: str) -> str:
        provider = self.cli.providers.get(name)
        configured = bool(provider and provider.validate_api_key())
        return f"{'●' if configured else '○'} {name}"

    def _log(self, text: str) -> None:
        log = self.query_one("#chat", RichLog)
        if text.startswith("you> "):
            log.write(Panel(Text(text[5:]), title="You", title_align="left", border_style="#344957", padding=(0, 1)))
        elif text.startswith("assistant> "):
            log.write(Panel(Markdown(text[11:]), title="Assistant", title_align="left", border_style="#73daca", padding=(1, 1)))
        else:
            log.write(Text(text, style="#d48787" if text.startswith("error>") else "#8395a7"))

    def _selected_provider(self) -> Optional[str]:
        return self._current_provider

    def _selected_model(self) -> Optional[str]:
        return self._current_model

    def _update_status(self) -> None:
        provider = self._current_provider or "no provider"
        model = self._current_model or "no model"
        turns = len([m for m in self.history if m["role"] == "user"])
        self.query_one("#session-info", Static).update(f"Conversation\n\n{provider}\n{model}\n\nContext\n{turns} turns\n\nStatus\n{'Responding...' if self._busy else 'Ready'}\n\nctrl+p  provider\nctrl+m  model\nctrl+l  new chat")
        self.query_one("#status", Static).update(
            f"{provider} · {model} · {turns} turn(s) this session"
        )

    # ── providers and models ───────────────────────────────────────────────

    def _select_provider(self, name: str, prompt_login: bool = True) -> None:
        self._generation += 1
        self._busy = False
        self._save_conversation()
        self._session_id = secrets.token_hex(16)
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
        if (
            name in ACCOUNT_PROVIDERS
            and prompt_login
            and not self.cli.providers[name].validate_api_key()
        ):
            self.push_screen(ProviderLogin(name))
        else:
            self._load_models(name)

    def _load_models(self, name: str) -> None:
        provider = self.cli.providers.get(name)
        if provider is None:
            return
        self._discovery += 1
        self._models_worker = self.run_worker(
            functools.partial(self._models_job, name, provider, self._discovery),
            thread=True,
            exclusive=True,
            group="models",
        )

    def _models_job(self, name: str, provider: Any, discovery: int) -> None:
        try:
            models = provider.list_models()
        except Exception as e:  # Discovery must never take the TUI down.
            self.call_from_thread(self._models_result, discovery, name, [], f"model discovery failed: {e}")
            return
        self.call_from_thread(self._models_result, discovery, name, models, "")

    def _models_result(self, discovery, name, models, error):
        if discovery == self._discovery:
            self._on_models(name, models, error)

    def _on_models(self, name: str, models: List[str], error: str) -> None:
        if name != self._current_provider:
            return
        models_list = self.query_one("#models", ListView)
        models_list.clear()
        previous = self._current_model
        self._current_model = None
        self._model_names = list(models)
        if self._model_names:
            models_list.extend(
                [ListItem(Label(getattr(self.cli.providers[name], "model_names", {}).get(model, model))) for model in self._model_names]
            )
            try:
                models_list.index = 0
            except (ValueError, IndexError):
                pass
            self._current_model = previous if previous in self._model_names else self._model_names[0]
        if error:
            self._log(f"error> {error}")
        self._log(f"{len(self._model_names)} model(s) available for {name}.")
        self._update_status()

    # ── chat ───────────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        was_busy = self._busy
        self._send(event.value)
        if (not was_busy and self._busy) or event.value.startswith("/"):
            event.input.value = ""

    def _send(self, text: str) -> None:
        text = text.strip()
        commands = {"/models": self.action_focus_models, "/connect": self.action_focus_providers, "/new": self.action_new_conversation, "/sidebar": self.action_toggle_sidebar, "/sessions": self.action_sessions, "/export": self.action_export}
        if text in commands:
            commands[text]()
            return
        if text == "/help":
            self.notify("/connect provider / /models model / /new conversation / /sidebar toggle")
            return
        if not text:
            return
        if self._busy:
            self._log("A reply is pending. Wait before sending another message.")
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

        self.query_one("#body").remove_class("home")
        self.query_one("#home").display = False
        self.history.append({"role": "user", "content": text})
        self._log(f"you> {text}")
        self._update_status()
        # The snapshot freezes the turn so a mid-flight selection change
        # cannot mix contexts.
        self._pending = (provider_name, provider, model, list(self.history))
        self._busy = True
        self._update_status()
        self._chat_worker = self.run_worker(
            functools.partial(self._chat_job, self._generation, self._pending),
            thread=True, exclusive=True, group="chat"
        )

    def _chat_job(self, generation: int, pending: Any) -> None:
        provider_name, provider, model, messages = pending
        try:
            reply = provider.chat(model, messages, temperature=0.7, max_tokens=1000)
        except Exception as e:
            self.call_from_thread(self._on_chat_error, generation, str(e))
            return
        self.call_from_thread(self._finish_reply, generation, messages, reply)

    def _on_chat_error(self, generation: int, error: str) -> None:
        if generation != self._generation:
            return
        self._busy = False
        if self.history and self.history[-1]["role"] == "user":
            self.history.pop()
        self._log(f"error> {error}")
        self._update_status()

    def _finish_reply(self, generation: int, messages: List[Dict[str, str]], reply: str) -> None:
        if generation != self._generation:
            return
        self._busy = False
        self._on_reply(messages, reply)
        self._save_conversation()

    def _on_reply(self, messages: List[Dict[str, str]], reply: str) -> None:
        self.history.clear()
        self.history.extend(messages)
        self.history.append({"role": "assistant", "content": reply})
        self._log(f"assistant> {reply}")
        self._update_status()

    # ── actions ────────────────────────────────────────────────────────────

    def action_toggle_sidebar(self) -> None:
        sidebar = self.query_one("#sidebar")
        sidebar.display = not sidebar.display

    def action_new_conversation(self) -> None:
        self._save_conversation()
        self._session_id = secrets.token_hex(16)
        self._generation += 1
        self._busy = False
        self.history.clear()
        self.query_one("#body").add_class("home")
        self.query_one("#home").display = True
        self.query_one("#chat", RichLog).clear()
        self._log("New conversation. Select a model and start writing.")
        self._update_status()
        self.query_one("#prompt", Input).focus()

    def _save_conversation(self):
        if not self.history or not self._current_provider or not self._current_model:
            return
        from codelaboon.sessions import save_session
        title = next((m["content"][:60] for m in self.history if m["role"] == "user"), "Conversation")
        try:
            return save_session(self.cli.config_dir, {"id": self._session_id, "title": title, "provider": self._current_provider, "model": self._current_model, "messages": list(self.history)})
        except (OSError, ValueError):
            self.notify("Could not save conversation. Check config directory permissions.", severity="error")

    def action_sessions(self):
        from codelaboon.sessions import list_sessions
        self._saved_sessions = {item["id"]: item for item in list_sessions(self.cli.config_dir)}
        if not self._saved_sessions:
            self.notify("No saved conversations yet. Completed replies are saved automatically.")
            return
        self.push_screen(Picker("Resume conversation", [(key, item["title"] + " / " + item["provider"]) for key, item in self._saved_sessions.items()]), self._resume_session)

    def _resume_session(self, identifier):
        if not identifier:
            return
        item = self._saved_sessions[identifier]
        if item["provider"] not in self.cli.providers:
            self.notify("This conversation's provider is unavailable.", severity="error")
            return
        self._save_conversation()
        self._generation += 1
        self._discovery += 1
        self._busy = False
        self._session_id = item["id"]
        self._current_provider = item["provider"]
        self._current_model = item["model"]
        self.history = [dict(message) for message in item["messages"]]
        self.query_one("#chat", RichLog).clear()
        self.query_one("#body").remove_class("home")
        self.query_one("#home").display = False
        for message in self.history:
            self._log(("you> " if message["role"] == "user" else "assistant> ") + message["content"])
        self._update_status()
        self.query_one("#prompt", Input).focus()
        self._load_models(self._current_provider)

    def action_export(self):
        path = self._save_conversation()
        if path:
            self.notify(f"Conversation JSON: {path}", timeout=10)

    def action_focus_providers(self) -> None:
        self.push_screen(Picker("Connect a provider", [(name, self._provider_label(name)) for name in self._provider_names]), self._pick_provider)

    def _pick_provider(self, name):
        if name:
            self._select_provider(name)


    def action_focus_models(self) -> None:
        provider = self.cli.providers.get(self._current_provider)
        if (
            self._current_provider in ACCOUNT_PROVIDERS
            and provider is not None
            and not provider.validate_api_key()
        ):
            self.push_screen(ProviderLogin(self._current_provider))
            return
        names = getattr(provider, "model_names", {})
        self.push_screen(Picker("Select model", [(m, names.get(m, m)) for m in self._model_names]), self._pick_model)

    def _pick_model(self, model):
        if model:
            self._save_conversation()
            self._session_id = secrets.token_hex(16)
            self._generation += 1
            self._busy = False
            self._current_model = model
            self.history.clear()
            self._update_status()
            self.query_one("#prompt", Input).focus()

    def start_provider_login(self, dialog, provider: str = "chatgpt"):
        if getattr(self, "_login_pending", False):
            return
        self._login_pending = True
        self.run_worker(
            functools.partial(self._login_job, dialog, provider),
            thread=True,
            group="login",
        )

    def start_chatgpt_login(self, dialog):
        self.start_provider_login(dialog, getattr(dialog, "provider", "chatgpt"))

    def _login_job(self, dialog, provider: str):
        import importlib

        module = importlib.import_module(f"codelaboon.{provider}_auth")
        try:
            module.login(report=lambda message: self.call_from_thread(self.notify, message))
        except Exception:
            self.call_from_thread(self._login_done, dialog, False)
        else:
            self.call_from_thread(self._login_done, dialog, True)

    def _login_done(self, dialog, success):
        self._login_pending = False
        provider = getattr(dialog, "provider", self._current_provider or "chatgpt")
        label = ACCOUNT_LABELS.get(provider, provider.title())
        if dialog in self.screen_stack:
            dialog.dismiss(success)
        if success and self._current_provider == provider:
            self._load_models(provider)
        self.notify(
            f"{label} connected" if success
            else f"Sign-in did not complete. Select {label} to retry.",
            severity="information" if success else "error",
        )


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
                self._generation += 1
                self._busy = False
                self._current_model = self._model_names[index]
                self.history.clear()
                self._log("─ model switched, context cleared ─")
                self._update_status()


def run_app() -> None:
    """Run the TUI."""
    CodelaboonTuiApp().run()
