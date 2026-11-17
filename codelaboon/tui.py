"""
Interactive terminal UI for codelaboon, built on Textual.

The TUI follows the interaction model of the terminal coding agents this
project is modelled on (OpenCode, Codex CLI and Pi): a centered home with a
composer, a persistent session rail, selection dialogs that work from the
keyboard alone, a slash-command surface and an auto-selected free model.

`codelaboon` (with no subcommand) opens it. The directory codelaboon is
launched from is the project root for the session, and it is shown in the
header and saved with every conversation.

Keys: ctrl+p providers · ctrl+o models · ctrl+n/ctrl+l new chat ·
ctrl+s sessions · ctrl+b sidebar · ctrl+k account key · ctrl+r refresh ·
ctrl+d doctor · esc interrupt · ctrl+q quit. Up/down in the composer recall
sent prompts; up/down in a picker moves the highlight and Enter selects it.
"""

import functools
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text

from textual.binding import Binding
from textual.screen import ModalScreen
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Input, Label, ListItem, ListView, RichLog, Static

from codelaboon.cli import CodelaboonCLI


THEMES = {
    "default": {
        "bg": "#161618", "surface": "#111113", "surface_alt": "#1c1c20",
        "border": "#2a2a30", "border_soft": "#2f2f36", "fg": "#eeeeee",
        "muted": "#9a9aa5", "dim": "#7d7d88", "accent": "#73daca",
        "accent_alt": "#7aa2f7", "highlight": "#2a2a31", "error": "#e06c75",
        "warn": "#e5c07b", "success": "#98c379", "user_border": "#344957",
        "assistant_border": "#73daca", "overlay": "#000000aa",
    },
    "nord": {
        "bg": "#2e3440", "surface": "#242933", "surface_alt": "#3b4252",
        "border": "#434c5e", "border_soft": "#4c566a", "fg": "#eceff4",
        "muted": "#d8dee9", "dim": "#81a1c1", "accent": "#88c0d0",
        "accent_alt": "#81a1c1", "highlight": "#3b4252", "error": "#bf616a",
        "warn": "#ebcb8b", "success": "#a3be8c", "user_border": "#5e81ac",
        "assistant_border": "#88c0d0", "overlay": "#1b1f27cc",
    },
    "gruvbox": {
        "bg": "#282828", "surface": "#1d2021", "surface_alt": "#32302f",
        "border": "#504945", "border_soft": "#665c54", "fg": "#ebdbb2",
        "muted": "#d5c4a1", "dim": "#a89984", "accent": "#fabd2f",
        "accent_alt": "#83a598", "highlight": "#3c3836", "error": "#fb4934",
        "warn": "#fe8019", "success": "#b8bb26", "user_border": "#458588",
        "assistant_border": "#fabd2f", "overlay": "#000000aa",
    },
    "catppuccin": {
        "bg": "#1e1e2e", "surface": "#181825", "surface_alt": "#313244",
        "border": "#45475a", "border_soft": "#585b70", "fg": "#cdd6f4",
        "muted": "#bac2de", "dim": "#9399b2", "accent": "#cba6f7",
        "accent_alt": "#89b4fa", "highlight": "#313244", "error": "#f38ba8",
        "warn": "#f9e2af", "success": "#a6e3a1", "user_border": "#89b4fa",
        "assistant_border": "#cba6f7", "overlay": "#11111bcc",
    },
    "kanagawa": {
        "bg": "#1f1f28", "surface": "#16161d", "surface_alt": "#2a2a37",
        "border": "#363646", "border_soft": "#54546d", "fg": "#dcd7ba",
        "muted": "#c8c093", "dim": "#727169", "accent": "#7e9cd8",
        "accent_alt": "#957fb8", "highlight": "#2a2a37", "error": "#c34043",
        "warn": "#c0a36e", "success": "#76946a", "user_border": "#7fb4ca",
        "assistant_border": "#7e9cd8", "overlay": "#0d0d14cc",
    },
    "solarized": {
        "bg": "#002b36", "surface": "#073642", "surface_alt": "#073642",
        "border": "#586e75", "border_soft": "#657b83", "fg": "#eee8d5",
        "muted": "#93a1a1", "dim": "#839496", "accent": "#2aa198",
        "accent_alt": "#268bd2", "highlight": "#094352", "error": "#dc322f",
        "warn": "#b58900", "success": "#859900", "user_border": "#268bd2",
        "assistant_border": "#2aa198", "overlay": "#001f27cc",
    },
    "evergreen": {
        "bg": "#0f1f17", "surface": "#0b1712", "surface_alt": "#183126",
        "border": "#244637", "border_soft": "#2f5b48", "fg": "#dcefe4",
        "muted": "#b7d4c3", "dim": "#7ea893", "accent": "#6bcf9b",
        "accent_alt": "#3fbf7f", "highlight": "#1a3328", "error": "#e06c75",
        "warn": "#d7b56d", "success": "#7fd962", "user_border": "#2f7a5b",
        "assistant_border": "#6bcf9b", "overlay": "#06100ccc",
    },
    "sakura": {
        "bg": "#1f1a1d", "surface": "#181316", "surface_alt": "#2a2126",
        "border": "#3f3038", "border_soft": "#56414d", "fg": "#f6e9ee",
        "muted": "#e4cfd8", "dim": "#b89aa8", "accent": "#f4a7c1",
        "accent_alt": "#e07aa5", "highlight": "#33272d", "error": "#f06a8a",
        "warn": "#e7c080", "success": "#9fd3a6", "user_border": "#8e5a72",
        "assistant_border": "#f4a7c1", "overlay": "#120d10cc",
    },
}

THEME_ALIASES = {
    "catpuccin": "catppuccin",
    "gruvbox-dark": "gruvbox",
    "solarized-dark": "solarized",
    "default-dark": "default",
}


def normalize_theme_name(name: str) -> str:
    key = (name or "").strip().lower()
    return THEME_ALIASES.get(key, key)


def theme_palette(name: str) -> dict:
    return THEMES.get(normalize_theme_name(name), THEMES["default"]).copy()


def app_css(p: dict) -> str:
    return f"""
    Screen {{ background: {p['bg']}; color: {p['fg']}; }}
    #body {{ height: 1fr; }}
    #main {{ width: 1fr; padding: 1 3; }}
    #sidebar {{
        width: 38; background: {p['surface']}; padding: 1 2;
        border-left: solid {p['border']};
    }}
    #topbar {{ height: 1; color: {p['dim']}; margin-bottom: 1; }}
    #status {{ height: 1; color: {p['muted']}; margin-bottom: 1; }}
    #chat {{ height: 1fr; background: {p['bg']}; padding-right: 1; }}
    #home {{ height: 1fr; min-height: 10; content-align: center bottom; color: {p['accent']}; padding-bottom: 1; }}
    #prompt {{
        background: {p['surface']}; border: tall {p['border_soft']};
        border-left: tall {p['accent']}; padding: 0 1; height: 5; margin-top: 1;
    }}
    #prompt:focus {{ border: tall {p['accent_alt']}; border-left: tall {p['accent']}; }}
    #hint {{ height: 1; color: {p['dim']}; margin-top: 1; }}
    .home #chat {{ display: none; }}
    .home #hint {{ height: 2; }}

    #sb-title {{ color: {p['accent']}; text-style: bold; height: 1; margin-bottom: 1; }}
    .sb-section {{ color: {p['dim']}; text-style: bold; height: 1; margin-top: 1; }}
    .sb-label {{ color: {p['dim']}; height: 1; }}
    .sb-value {{ color: {p['fg']}; height: auto; margin-bottom: 0; }}
    .sb-accent {{ color: {p['accent']}; height: auto; }}
    .sb-muted {{ color: {p['muted']}; height: auto; }}
    .sb-ok {{ color: {p['success']}; }}
    .sb-warn {{ color: {p['warn']}; }}
    .sb-rule {{ height: 1; color: {p['border']}; }}
    #session-info {{ display: none; }}
    #providers, #models, .catalog-label {{ display: none; }}

    Footer {{ background: {p['surface']}; color: {p['dim']}; }}
    Footer > .footer--key {{ color: {p['accent']}; background: {p['surface']}; }}
    Footer > .footer--description {{ color: {p['muted']}; background: {p['surface']}; }}
    ListView {{ background: {p['surface']}; }}
    ListView > ListItem.--highlight {{ background: {p['highlight']}; color: {p['fg']}; }}
    """


def modal_css(p: dict) -> str:
    return f"""
    Picker {{ align: center middle; background: {p['overlay']}; }}
    #picker-dialog {{
        width: 78; max-width: 96%; height: 28;
        background: {p['surface']}; border: round {p['border_soft']}; padding: 1 2;
    }}
    #picker-title {{ height: 1; text-style: bold; color: {p['fg']}; }}
    #picker-hint {{ height: 1; color: {p['dim']}; }}
    #picker-search {{ height: 3; margin: 1 0; border: tall {p['border']}; }}
    #picker-search:focus {{ border: tall {p['accent']}; }}
    #picker-list {{ height: 1fr; background: {p['surface']}; }}
    #picker-list > ListItem {{ padding: 0 1; }}
    Picker ListView > ListItem.--highlight {{ background: {p['highlight']}; color: {p['fg']}; }}

    ProviderKey {{ align: center middle; background: {p['overlay']}; }}
    #key-dialog {{ width: 72; max-width: 96%; height: auto; padding: 2 3; background: {p['surface']}; border: round {p['border_soft']}; }}
    #key-dialog Static {{ height: auto; margin-bottom: 1; color: {p['muted']}; }}
    #key-dialog Label {{ color: {p['fg']}; text-style: bold; }}
    #key-actions {{ height: 3; margin-top: 1; }}
    #key-dialog Input {{ border: tall {p['border']}; }}
    #key-dialog Input:focus {{ border: tall {p['accent']}; }}

    ProviderLogin {{ align: center middle; background: {p['overlay']}; }}
    #login-dialog {{ width: 68; max-width: 96%; height: auto; background: {p['surface']}; padding: 2 3; border: round {p['border_soft']}; }}
    #login-dialog Label {{ color: {p['fg']}; text-style: bold; }}
    #login-message {{ height: auto; margin: 1 0; color: {p['muted']}; }}
    #login-error {{ height: auto; margin: 1 0; color: {p['error']}; }}
    #login-actions {{ height: 3; }}
    """


class Picker(ModalScreen[str]):
    """Keyboard-first selection dialog used for providers, models and sessions."""

    BINDINGS = [
        Binding("escape", "dismiss_picker", "Close", show=False),
        # The search field keeps focus so typing filters immediately. Arrow
        # keys are not consumed by Input, so these screen bindings move the
        # list highlight without ever reaching for the mouse.
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("pageup", "page_up", "Page up", show=False),
        Binding("pagedown", "page_down", "Page down", show=False),
    ]
    DEFAULT_CSS = modal_css(THEMES["default"])

    def __init__(self, title, choices):
        super().__init__()
        self.heading, self.choices = title, choices
        self.filtered = list(choices)

    def compose(self):
        with Vertical(id="picker-dialog"):
            yield Label(self.heading, id="picker-title")
            yield Label("↑↓ move   enter select   esc close", id="picker-hint")
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
        self._select_current()

    def on_list_view_selected(self, event):
        self._select_current()

    def _select_current(self):
        if not self.filtered:
            return
        view = self.query_one(ListView)
        index = view.index if view.index is not None else 0
        if 0 <= index < len(self.filtered):
            self.dismiss(self.filtered[index][0])

    def _move(self, delta):
        view = self.query_one(ListView)
        if not self.filtered:
            return
        if view.index is None:
            view.index = 0
            return
        view.index = max(0, min(len(self.filtered) - 1, view.index + delta))

    def action_cursor_up(self):
        self._move(-1)

    def action_cursor_down(self):
        self._move(1)

    def action_page_up(self):
        self._move(-8)

    def action_page_down(self):
        self._move(8)

    def action_dismiss_picker(self):
        self.dismiss("")


ACCOUNT_PROVIDERS = {"chatgpt", "claude", "gemini", "freebuff", "qoder", "copilot"}
ACCOUNT_LABELS = {
    "chatgpt": "ChatGPT",
    "claude": "Claude",
    "gemini": "Gemini",
    "freebuff": "Freebuff",
    "qoder": "Qoder",
    "copilot": "GitHub Copilot",
}
# Lanes already covered by free (Auto); their individual catalogues stay out
# of the picker so the list is short and the default is obvious.
FREE_PROVIDERS = {
    "ourfree", "kilo", "pollinations", "gemini", "freebuff", "qoder"
}
AUTO_PROVIDER = "free"
AUTO_MODEL = "free (Auto)"


class ProviderKey(ModalScreen[bool]):
    """Account-independent API key setup, including browser signup."""

    BINDINGS = [("escape", "dismiss", "Close")]
    DEFAULT_CSS = modal_css(THEMES["default"])

    def __init__(self, provider):
        super().__init__()
        self.provider = provider

    def compose(self):
        url = {"wusrouter":"https://wusrouter.com/","howtofix":"https://howtofix.id/"}.get(self.provider,"https://qoder.com/account/integrations")
        with Vertical(id="key-dialog"):
            yield Label(f"Connect {self.provider.title()}", markup=False)
            yield Static(f"Sign in or create an account in your browser:\n{url}\nPaste its API key here. Save a new key to switch accounts.", markup=False)
            if self.provider == "qoder":
                yield Static("A PAT uses Cloud Agents without a local CLI. Cloud access, quota and an existing environment are required.")
            yield Input(placeholder="API key / Personal Access Token", password=True, id="provider-key")
            with Horizontal(id="key-actions"):
                yield Button("Open signup / account", id="key-signup")
                yield Button("Save key", id="key-save")
                yield Button("Later", id="key-later")

    def on_button_pressed(self, event):
        if event.button.id == "key-later":
            self.dismiss(False)
        elif event.button.id == "key-signup":
            import webbrowser
            url = {"wusrouter":"https://wusrouter.com/","howtofix":"https://howtofix.id/"}.get(self.provider,"https://qoder.com/account/integrations")
            webbrowser.open(url)
        elif event.button.id == "key-save":
            key = self.query_one("#provider-key", Input).value.strip()
            if not key:
                self.notify("Enter a key first.", severity="warning")
                return
            from config.providers import save_provider_config
            config = self.app.cli._current_provider_config(self.provider)
            config["api_key"] = key
            if not save_provider_config(self.provider, config):
                self.notify("Could not save the key.", severity="error")
                return
            self.app.cli.load_providers()
            self.app._save_conversation()
            self.app.history.clear()
            self.app._session_id = secrets.token_hex(16)
            self.app._generation += 1
            self.app._busy = False
            self.app._current_model = None
            self.app._model_names = []
            self.dismiss(True)
            self.app._load_models(self.provider)
            self.app._update_status()


class ProviderLogin(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel_login", "Close")]
    DEFAULT_CSS = modal_css(THEMES["default"])

    def __init__(self, provider: str = "chatgpt"):
        super().__init__()
        self.provider = provider
        self.label = ACCOUNT_LABELS.get(provider, provider.title())

    def compose(self):
        with Vertical(id="login-dialog"):
            yield Label(f"Connect {self.label}", markup=False)
            yield Static("Sign in to load your account's available models.\nComplete authorization in your browser, then return here.", id="login-message")
            yield Static("", id="login-error", markup=False)
            with Horizontal(id="login-actions"):
                yield Button(f"Continue with {self.label}", id="continue-login")
                yield Button("Later", id="later-login")

    def on_button_pressed(self, event):
        if event.button.id == "later-login":
            self.dismiss(False)
        else:
            self.query_one("#continue-login", Button).disabled = True
            self.query_one("#login-error", Static).update("")
            self.query_one("#login-message", Static).update("Waiting for browser authorization...\nThis can take up to five minutes.")
            self.app.start_provider_login(self, self.provider)

    def show_error(self, message: str) -> None:
        """Surface the real failure instead of a generic retry prompt."""
        self.query_one("#continue-login", Button).disabled = False
        self.query_one("#login-error", Static).update(f"Sign-in failed: {message}")
        self.query_one("#login-message", Static).update(
            "Complete authorization in your browser, then return here."
        )

    def action_cancel_login(self):
        self.dismiss(False)


# Kept for callers that imported the ChatGPT-only dialog.
ChatGPTLogin = ProviderLogin


class CodelaboonTuiApp(App[None]):
    """OpenCode/Codex/Pi-style terminal workspace for the codelaboon harness."""

    TITLE = "codelaboon"
    SUB_TITLE = "model workspace"

    CSS = app_css(THEMES["default"])

    # NOTE: there is deliberately no ctrl+m binding. In terminals Ctrl+M is
    # carriage return (0x0D) — byte-for-byte identical to Enter — so Textual
    # delivers it to the prompt as a submit, never as this action. The model
    # picker lives on ctrl+o, which terminals deliver distinctly.
    BINDINGS = [
        Binding("ctrl+k", "provider_key", "API key", priority=True),
        ("ctrl+s", "sessions", "Sessions"),
        ("ctrl+n", "new_conversation", "New chat"),
        ("ctrl+l", "new_conversation", "New chat"),
        ("ctrl+b", "toggle_sidebar", "Sidebar"),
        ("ctrl+p", "focus_providers", "Providers"),
        ("ctrl+o", "focus_models", "Models"),
        ("ctrl+r", "refresh_models", "Refresh models"),
        ("ctrl+t", "theme", "Theme"),
        ("ctrl+d", "run_doctor", "Doctor"),
        ("ctrl+q", "quit", "Quit"),
        Binding("escape", "interrupt", "Interrupt", show=False),
        Binding("up", "history_previous", "Previous prompt", show=False),
        Binding("down", "history_next", "Next prompt", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.cli = CodelaboonCLI()
        self.project_dir: Path = self.cli.project_dir
        self.history: List[Dict[str, str]] = []
        self._provider_names: List[str] = []
        self._model_names: List[str] = []
        self._current_provider: Optional[str] = None
        self._current_model: Optional[str] = None
        self._models_worker: Any = None
        self._chat_worker: Any = None
        self._pending: Any = None
        self._pending_model: Optional[str] = None
        self._generation = 0
        self._busy = False
        self._session_id = secrets.token_hex(16)
        self._discovery = 0
        self._login_pending = False
        self._prompt_history: List[str] = []
        self._history_cursor: Optional[int] = None
        self.theme_name = self._load_theme_name()
        self.palette = theme_palette(self.theme_name)
        self.CSS = app_css(self.palette)

    # ── theming ─────────────────────────────────────────────────────────────

    def _ui_config_path(self) -> Path:
        return self.cli.config_dir / "ui.json"

    def _load_theme_name(self) -> str:
        try:
            import json

            data = json.loads(self._ui_config_path().read_text(encoding="utf-8"))
            if isinstance(data, dict):
                name = normalize_theme_name(str(data.get("theme", "default")))
                if name in THEMES:
                    return name
        except Exception:
            pass
        return "default"

    def _save_theme_name(self) -> None:
        try:
            import json

            path = self._ui_config_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"theme": self.theme_name}, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _themed(self, screen):
        try:
            screen.CSS = modal_css(self.palette)
        except Exception:
            pass
        return screen

    def _apply_theme(self, name: str, announce: bool = True) -> None:
        original = name
        name = normalize_theme_name(name)
        if name not in THEMES:
            if announce:
                available = ", ".join(THEMES)
                self.notify(f"Unknown theme '{original}'. Try: {available}", timeout=5)
            name = "default"
        self.theme_name = name
        self.palette = theme_palette(name)
        self.CSS = app_css(self.palette)
        self._save_theme_name()
        # Best-effort live stylesheet refresh across Textual versions.
        for apply in (
            lambda: self.stylesheet.read(self.CSS),
            lambda: self.stylesheet.parse(self.CSS),
            lambda: setattr(self.screen, "CSS", self.CSS) or self.screen.refresh_css(),
            lambda: self.refresh_css(),
        ):
            try:
                apply()
            except Exception:
                continue
        try:
            self.refresh(layout=True, repaint=True)
        except Exception:
            pass
        self._update_status()
        self._refresh_welcome()
        if announce and name == normalize_theme_name(original):
            self.notify(f"Theme: {name}", timeout=3)
            self._log(f"theme> {name}")
        elif announce and normalize_theme_name(original) not in THEMES and str(original).strip():
            self._log(f"theme> {name} (fallback)")

    # ── layout ─────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Horizontal(id="body", classes="home"):
            with Vertical(id="main"):
                yield Static("", id="topbar", markup=False)
                yield Static("", id="status", markup=False)
                yield Static(self._welcome(80), id="home", markup=False)
                yield RichLog(id="chat", markup=False, highlight=False, wrap=True)
                yield Input(placeholder="Ask anything...  /help for commands", id="prompt")
                yield Static(
                    "ctrl+p providers   ctrl+o models   ctrl+n new   esc interrupt",
                    id="hint",
                )
            with Vertical(id="sidebar"):
                yield Static("▲ codelaboon", id="sb-title", markup=False)
                yield Static("", id="sb-project", classes="sb-muted", markup=False)
                yield Static("Session", classes="sb-section", markup=False)
                yield Static("", id="sb-session", markup=False)
                yield Static("Status", classes="sb-section", markup=False)
                yield Static("", id="sb-status", markup=False)
                yield Static("Shortcuts", classes="sb-section", markup=False)
                yield Static("", id="sb-shortcuts", classes="sb-muted", markup=False)
                # Hidden compatibility widgets (kept for existing logic/tests).
                yield Static("New conversation", id="session-info", markup=False)
                yield Label("Providers", classes="catalog-label")
                yield ListView(id="providers")
                yield Label("Models", classes="catalog-label")
                yield ListView(id="models")
        yield Footer()

    def _welcome(self, width, height=40, project=None):
        whale = r"""           .  |  .
            \ | /
             \|/
       .-----' `----.          /\_/\
     .'              `-.     /     /
    /    o              \___/     /
    |                           .'
     \     ._______________.--'
      `---'"""
        wordmark = r"""  ___ ___  ___  ___ _      _   ___  ___   ___  _  _
 / __/ _ \|   \/ __| |    /_\ | _ )/ _ \ / _ \| \| |
| (_| (_) | |) | _|| |__ / _ \| _ \ (_) | (_) | .` |
 \___\___/|___/\___|____/_/ \_\___/\___/ \___/|_|\_|"""
        if width < 54 or height < 32:
            wordmark = "C O D E L A B O O N"
        if width < 35 or height < 32:
            whale = r"""    __     /\_/\
  __/ o\___/    /
  \_________.-'"""
        project = self.project_dir if project is None else project
        name = getattr(project, "name", "") or str(project)
        where = f"{name}  ·  {project}" if name else str(project)
        where = where[:width] if width > 0 else where
        return whale + "\n\n" + wordmark + "\n\n" + where + "\nYour next idea starts here."

    def _refresh_welcome(self):
        available = max(1, self.query_one("#main").size.width - 8)
        self.query_one("#home", Static).update(self._welcome(available, self.size.height))

    def _refresh_topbar(self):
        project = self.project_dir
        self.query_one("#topbar", Static).update(
            f"codelaboon   {project.name}\n{project}"
        )

    def on_resize(self, event):
        self.call_after_refresh(self._refresh_welcome)

    def on_mount(self) -> None:
        self._apply_theme(self.theme_name, announce=False)
        self.cli.load_providers()
        self.sub_title = str(self.project_dir)
        providers_list = self.query_one("#providers", ListView)
        # free (Auto) is the first provider and therefore the default: the
        # free lanes are what codelaboon is for, and Auto removes the need to
        # choose between dozens of free model ids.
        self._provider_names = [AUTO_PROVIDER] + sorted(
            name for name in self.cli.providers if name not in {AUTO_PROVIDER}
        )
        providers_list.extend(
            [ListItem(Label(self._provider_label(name))) for name in self._provider_names]
        )
        self._log("codelaboon TUI — free (Auto) is selected; just type.")
        self._log("ctrl+p provider · ctrl+o model · ctrl+s sessions · /help for commands")
        self._refresh_topbar()
        self._select_provider(AUTO_PROVIDER, prompt_login=False)
        self.call_after_refresh(self._refresh_welcome)
        self.query_one("#prompt", Input).focus()
        if self.size.width < 100:
            self.query_one("#sidebar").display = False

    # ── helpers ────────────────────────────────────────────────────────────

    def _provider_label(self, name: str) -> str:
        if name == AUTO_PROVIDER:
            return f"● {AUTO_PROVIDER} (Auto)"
        provider = self.cli.providers.get(name)
        configured = bool(provider and provider.validate_api_key())
        return f"{'●' if configured else '○'} {name}"

    def _log(self, text: str) -> None:
        log = self.query_one("#chat", RichLog)
        p = getattr(self, "palette", theme_palette("default"))
        if text.startswith("you> "):
            log.write(Panel(Text(text[5:]), title="You", title_align="left", border_style=p["user_border"], padding=(0, 1)))
        elif text.startswith("assistant> "):
            log.write(Panel(Markdown(text[11:]), title="Assistant", title_align="left", border_style=p["assistant_border"], padding=(1, 1)))
        else:
            style = p["error"] if text.startswith("error>") else p["dim"]
            log.write(Text(text, style=style))

    def _selected_provider(self) -> Optional[str]:
        return self._current_provider

    def _selected_model(self) -> Optional[str]:
        return self._current_model

    def _update_status(self) -> None:
        provider = self._current_provider or "no provider"
        model = self._current_model or "no model"
        turns = len([m for m in self.history if m["role"] == "user"])
        project = self.project_dir.name
        state = "Responding…" if self._busy else "Ready"
        theme = self.theme_name

        # Backward-compatible text block (hidden, but kept coherent).
        self.query_one("#session-info", Static).update(
            f"{project}\n{self.project_dir}\n\n"
            f"Conversation\n\n{provider}\n{model}\n\n"
            f"Context\n{turns} turn(s)\n\n"
            f"Status\n{state}\nTheme\n{theme}\n\n"
            f"ctrl+p  provider\nctrl+o  model\nctrl+n  new chat\nctrl+s  sessions"
        )
        self.query_one("#status", Static).update(
            f"{provider}  •  {model}  •  {turns} turn(s)"
        )

        def set_text(selector: str, text: str) -> None:
            try:
                self.query_one(selector, Static).update(text)
            except Exception:
                pass

        set_text("#sb-project", f"{project}\n{self.project_dir}")
        set_text(
            "#sb-session",
            f"Provider  {provider}\nModel     {model}\nTurns     {turns}",
        )
        set_text("#sb-status", f"{state}  ·  theme: {theme}")
        set_text(
            "#sb-shortcuts",
            "ctrl+p  providers\n"
            "ctrl+o  models\n"
            "ctrl+n  new chat\n"
            "ctrl+s  sessions\n"
            "ctrl+t  theme\n"
            "ctrl+b  sidebar\n"
            "ctrl+d  doctor\n"
            "/help   commands",
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
        if name == "qoder":
            from codelaboon.qoder_auth import QODER_LIMITATION

            # Explain which account types can use the native cloud lane.
            self._log(f"note> {QODER_LIMITATION}")
            self.notify(QODER_LIMITATION, timeout=10)
        self._update_status()
        providers_list = self.query_one("#providers", ListView)
        if name in self._provider_names:
            try:  # Keep the widget highlight in step with programmatic picks.
                providers_list.index = self._provider_names.index(name)
            except (ValueError, IndexError):
                pass
        if name == AUTO_PROVIDER:
            self._on_models(name, self._auto_models(), "")
        elif name in ("wusrouter","howtofix") and prompt_login and not self.cli.providers[name].validate_api_key():
            self.push_screen(ProviderKey(name))
        elif (
            name in ACCOUNT_PROVIDERS
            and prompt_login
            and not self.cli.providers[name].validate_api_key()
        ):
            self.push_screen(ProviderLogin(name))
        else:
            self._load_models(name)

    def _auto_models(self) -> List[str]:
        """The synthetic free (Auto) row followed by its ranked candidates."""
        from codelaboon import free_auto

        rows = [AUTO_MODEL]
        for provider, model, _label in free_auto.candidates(self.cli.providers):
            rows.append(f"{provider}/{model}")
        return rows

    def _load_models(self, name: str) -> None:
        if name == AUTO_PROVIDER:
            self._on_models(name, self._auto_models(), "")
            return
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
            names = getattr(self.cli.providers.get(name), "model_names", {}) or {}
            if name == AUTO_PROVIDER:
                labels = [
                    model if model == AUTO_MODEL else model.replace("/", " · ", 1)
                    for model in self._model_names
                ]
            else:
                labels = [names.get(model, model) for model in self._model_names]
            models_list.extend([ListItem(Label(label)) for label in labels])
            try:
                models_list.index = 0
            except (ValueError, IndexError):
                pass
            if self._pending_model in self._model_names:
                # A cross-provider pick from the unified model picker: land
                # on the requested model, not the catalogue's first row.
                self._current_model = self._pending_model
                self._pending_model = None
                self.history.clear()
                self._log("─ model switched, context cleared ─")
            else:
                self._pending_model = None
                self._current_model = previous if previous in self._model_names else self._model_names[0]
        if error:
            self._log(f"error> {error}")
        if name == AUTO_PROVIDER:
            from codelaboon import free_auto

            best = free_auto.select(self.cli.providers)
            if best is None:
                self._log(
                    "error> free (Auto): no free lane is ready. Sign in to Gemini/Freebuff/Qoder, "
                    "or configure ourfree; kilo and pollinations are keyless."
                )
            else:
                self._log(
                    f"free (Auto) will use {best.provider}/{best.model} ({best.display}) and fail over if it is busy."
                )
        else:
            self._log(f"{len(self._model_names)} model(s) available for {name}.")
        self._update_status()

    # ── chat ───────────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value
        was_busy = self._busy
        self._send(value)
        if (not was_busy and self._busy) or value.startswith("/"):
            event.input.value = ""
        if not was_busy and value.strip() and not value.startswith("/"):
            self._prompt_history.append(value.strip())
            self._history_cursor = None

    def _set_prompt(self, value: str) -> None:
        field = self.query_one("#prompt", Input)
        field.value = value
        field.cursor_position = len(value)

    def action_history_previous(self) -> None:
        field = self.query_one("#prompt", Input)
        if not field.has_focus or not self._prompt_history:
            return
        if self._history_cursor is None:
            self._history_cursor = len(self._prompt_history)
        self._history_cursor = max(0, self._history_cursor - 1)
        self._set_prompt(self._prompt_history[self._history_cursor])

    def action_history_next(self) -> None:
        field = self.query_one("#prompt", Input)
        if not field.has_focus or self._history_cursor is None:
            return
        self._history_cursor = min(len(self._prompt_history), self._history_cursor + 1)
        if self._history_cursor >= len(self._prompt_history):
            self._history_cursor = None
            self._set_prompt("")
        else:
            self._set_prompt(self._prompt_history[self._history_cursor])

    def _slash_commands(self):
        return {
            "/models": self.action_focus_models,
            "/connect": self.action_focus_providers,
            "/new": self.action_new_conversation,
            "/clear": self.action_new_conversation,
            "/sidebar": self.action_toggle_sidebar,
            "/sessions": self.action_sessions,
            "/export": self.action_export,
            "/free": self.action_use_free,
            "/project": self.action_project,
            "/doctor": self.action_run_doctor,
            "/update": self.action_update,
            "/retry": self.action_retry,
            "/theme": self.action_theme,
            "/quit": self.action_quit,
        }

    def _slash_aliases(self):
        return {
            "/h": "/help",
            "/?": "/help",
            "/m": "/models",
            "/c": "/connect",
            "/n": "/new",
            "/s": "/sessions",
            "/q": "/quit",
            "/d": "/doctor",
            "/u": "/update",
            "/r": "/retry",
            "/p": "/project",
            "/k": "/key",
            "/t": "/theme",
        }

    def _resolve_slash_command(self, text: str) -> str:
        """Autocorrect mistyped slash commands to the closest known one."""
        if not text.startswith("/"):
            return text
        commands = self._slash_commands()
        aliases = self._slash_aliases()
        head = text.split(maxsplit=1)[0].lower()
        if head in aliases:
            head = aliases[head]
            return head
        if head in commands or head in ("/help", "/key"):
            return head + text[len(text.split(maxsplit=1)[0]):]
        import difflib

        known = sorted(set(commands) | set(aliases) | {"/help", "/key"})
        matches = difflib.get_close_matches(head, known, n=1, cutoff=0.55)
        if matches:
            corrected = aliases.get(matches[0], matches[0])
            if corrected != head:
                self._log(f"↳ corrected {head} to {corrected}")
                self.notify(f"Corrected to {corrected}", timeout=2)
            return corrected
        return text

    def _send(self, text: str) -> None:
        text = text.strip()
        if text.startswith("/"):
            text = self._resolve_slash_command(text)
        commands = self._slash_commands()
        if text == "/key":
            self.action_provider_key()
            return
        if text.startswith("/theme"):
            parts = text.split(maxsplit=1)
            if len(parts) == 2 and parts[1].strip():
                self._apply_theme(parts[1].strip())
            else:
                self.action_theme()
            return
        if text in commands:
            commands[text]()
            return
        if text == "/help":
            self._log(
                "Commands: /models /connect /new /sessions /free /doctor /update /retry /theme "
                "/project /sidebar /export /key /quit  (aliases: /m /c /n /s /d /u /r /h /k)"
            )
            self.notify("/models /connect /new /sessions /free /doctor /update /retry /theme /help")
            return
        if text.startswith("/"):
            known = ", ".join(sorted(set(commands) | {"/help", "/key"}))
            self._log(f"error> unknown command: {text}")
            self._log(f"hint> try: {known}")
            self.notify("Unknown command. Type /help", timeout=4)
            return
        if not text:
            return
        if self._busy:
            self._log("A reply is pending. Wait, or press esc to interrupt the wait.")
            return

        provider_name = self._selected_provider()
        if not provider_name:
            self._log("error> select a provider first (ctrl+p)")
            return
        if provider_name == AUTO_PROVIDER:
            from codelaboon import free_auto

            if not free_auto.ranked(self.cli.providers):
                self._log(
                    "error> free (Auto): no free lane is ready. Sign in to Gemini/Freebuff/Qoder, "
                    "or configure ourfree; kilo and pollinations are keyless."
                )
                return
            provider = None
        else:
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
            self._log("error> select a model first (ctrl+o)")
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
            if provider_name == AUTO_PROVIDER:
                from codelaboon import free_auto

                chosen, reply = free_auto.chat(
                    self.cli.providers, messages, temperature=0.7, max_tokens=1000
                )
                self.call_from_thread(
                    self._log, f"auto> {chosen.provider}/{chosen.model} ({chosen.display})"
                )
            else:
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
        self.query_one("#prompt", Input).focus()

    # ── actions ────────────────────────────────────────────────────────────

    def action_interrupt(self) -> None:
        """Stop waiting for the current reply (the provider may keep running)."""
        if not self._busy:
            return
        self._generation += 1
        self._busy = False
        if self.history and self.history[-1]["role"] == "user":
            self.history.pop()
        self._log("interrupted> stopped waiting for the reply")
        self._update_status()
        self.query_one("#prompt", Input).focus()

    def action_use_free(self) -> None:
        self._pending_model = None
        self._select_provider(AUTO_PROVIDER, prompt_login=False)

    def action_project(self) -> None:
        self.notify(f"Project root: {self.project_dir}", timeout=8)

    def action_toggle_sidebar(self) -> None:
        sidebar = self.query_one("#sidebar")
        sidebar.display = not sidebar.display

    def action_theme(self) -> None:
        choices = []
        for name in THEMES:
            mark = " (current)" if name == self.theme_name else ""
            label = name
            if name == "catppuccin":
                label = "catppuccin"
            choices.append((name, f"{label}{mark}"))
        self.push_screen(Picker("Select theme", choices), self._pick_theme)

    def _pick_theme(self, name):
        if name:
            self._apply_theme(name)

    def action_new_conversation(self) -> None:
        self._save_conversation()
        self._session_id = secrets.token_hex(16)
        self._generation += 1
        self._busy = False
        self.history.clear()
        self._history_cursor = None
        self.query_one("#body").add_class("home")
        self.query_one("#home").display = True
        self.query_one("#chat", RichLog).clear()
        self._log("New conversation. free (Auto) is ready; select another model with ctrl+o.")
        self._update_status()
        self.query_one("#prompt", Input).focus()

    def _save_conversation(self):
        if not self.history or not self._current_provider or not self._current_model:
            return
        from codelaboon.sessions import save_session
        title = next((m["content"][:60] for m in self.history if m["role"] == "user"), "Conversation")
        try:
            return save_session(self.cli.config_dir, {
                "id": self._session_id,
                "title": title,
                "provider": self._current_provider,
                "model": self._current_model,
                "project": str(self.project_dir),
                "messages": list(self.history),
            })
        except (OSError, ValueError):
            self.notify("Could not save conversation. Check config directory permissions.", severity="error")

    def action_sessions(self):
        from codelaboon.sessions import list_sessions
        self._saved_sessions = {item["id"]: item for item in list_sessions(self.cli.config_dir)}
        if not self._saved_sessions:
            self.notify("No saved conversations yet. Completed replies are saved automatically.")
            return
        choices = []
        for key, item in self._saved_sessions.items():
            project = Path(item["project"]).name if item.get("project") else "?"
            choices.append((key, f"{item['title']} / {item['provider']} / {project}"))
        self.push_screen(Picker("Resume conversation", choices), self._resume_session)

    def _resume_session(self, identifier):
        if not identifier:
            return
        item = self._saved_sessions[identifier]
        if item["provider"] not in self.cli.providers and item["provider"] != AUTO_PROVIDER:
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
        if self._current_provider == AUTO_PROVIDER:
            self._on_models(AUTO_PROVIDER, self._auto_models(), "")
        else:
            self._load_models(self._current_provider)

    def action_export(self):
        path = self._save_conversation()
        if path:
            self.notify(f"Conversation JSON: {path}", timeout=10)

    def action_focus_providers(self) -> None:
        self.push_screen(
            Picker(
                "Connect a provider",
                [(name, self._provider_label(name)) for name in self._provider_names],
            ),
            self._pick_provider,
        )

    def _pick_provider(self, name):
        if name:
            self._pending_model = None
            self._select_provider(name)


    def action_focus_models(self) -> None:
        """Open the unified model picker (ctrl+o).

        free (Auto) is the first row. The free lanes it covers are collapsed
        into it, so the user does not have to scroll through dozens of free
        model ids; paid providers keep their full catalogues. The catalogue
        build runs in a worker because several providers discover models over
        the network.
        """
        self.run_worker(
            functools.partial(self._model_choices_job),
            thread=True,
            exclusive=True,
            group="models",
        )

    def _model_choices_job(self) -> None:
        from codelaboon import free_auto

        choices = [
            (f"{AUTO_PROVIDER}\x00{AUTO_MODEL}", "free · free (Auto) — best available free model")
        ]
        best = free_auto.select(self.cli.providers)
        if best is not None:
            choices[0] = (
                f"{AUTO_PROVIDER}\x00{AUTO_MODEL}",
                f"free · free (Auto) — now {best.provider}/{best.model}",
            )
        for name in self._provider_names:
            if name == AUTO_PROVIDER:
                continue
            provider = self.cli.providers.get(name)
            if provider is None:
                continue
            label = ACCOUNT_LABELS.get(name, name.title())
            connected = False
            try:
                connected = bool(provider.validate_api_key())
            except Exception:
                connected = False
            if name in FREE_PROVIDERS:
                # Covered by free (Auto); only surface the sign-in row when
                # the lane is not usable yet.
                if not connected and name in ACCOUNT_PROVIDERS:
                    choices.append((f"__login__\x00{name}", f"{label} · Connect account…"))
                continue
            if name in ACCOUNT_PROVIDERS and not connected:
                choices.append((f"__login__\x00{name}", f"{label} · Connect account…"))
                continue
            if name == self._current_provider and self._model_names:
                models = list(self._model_names)
            else:
                # No network here: the picker must open instantly. Use
                # the configured roster (or built-in defaults); picking
                # the row loads that provider's live catalogue anyway.
                models = list(
                    getattr(provider, "models", None)
                    or getattr(provider, "default_models", [])
                    or []
                )
            if not models:
                choices.append((f"__login__\x00{name}", f"{label} · Discover models / connect…"))
            names = getattr(provider, "model_names", {}) or {}
            for model in models:
                choices.append((f"{name}\x00{model}", f"{name} · {names.get(model, model)}"))
        self.call_from_thread(self._show_model_picker, choices)

    def _show_model_picker(self, choices) -> None:
        if not choices:
            self.notify("No models available. Connect a provider first (ctrl+p).")
            return
        self.push_screen(
            Picker("Select model (switches provider too)", choices),
            self._pick_model_key,
        )

    def _pick_model_key(self, key):
        if not key:
            return
        kind, _, value = str(key).partition("\x00")
        if kind == "__login__":
            # _select_provider itself raises the sign-in dialog for an
            # unconnected account provider.
            self._select_provider(value)
            return
        if kind == AUTO_PROVIDER:
            self._select_provider(AUTO_PROVIDER, prompt_login=False)
            return
        provider_name, model = kind, value
        if provider_name != self._current_provider:
            self._pending_model = model
            self._select_provider(provider_name, prompt_login=False)
            return
        self._pick_model(model)

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

        try:
            module = importlib.import_module(f"codelaboon.{provider}_auth")
            module.login(report=lambda message: self.call_from_thread(self.notify, message))
        except Exception as error:
            # Never swallow the reason: the dialog shows the provider's own
            # message (network error, invalid token, declined scope, ...).
            self.call_from_thread(self._login_done, dialog, False, str(error))
        else:
            self.call_from_thread(self._login_done, dialog, True, "")

    def _login_done(self, dialog, success, error: str = ""):
        self._login_pending = False
        provider = getattr(dialog, "provider", self._current_provider or "chatgpt")
        label = ACCOUNT_LABELS.get(provider, provider.title())
        if success:
            if dialog in self.screen_stack:
                dialog.dismiss(True)
            if self._current_provider == provider:
                self._load_models(provider)
            self.notify(f"{label} connected", severity="information")
            return
        # Keep the dialog open so the failure is readable and retryable.
        if dialog in self.screen_stack and hasattr(dialog, "show_error"):
            dialog.show_error(error or "unknown error")
        else:
            if dialog in self.screen_stack:
                dialog.dismiss(False)
            self.notify(f"{label} sign-in failed: {error or 'unknown error'}", severity="error")

    def action_provider_key(self):
        if self._current_provider in ("wusrouter", "qoder", "howtofix"):
            self.push_screen(ProviderKey(self._current_provider))
        else:
            self.notify("Select HowToFix, WusRouter or Qoder to configure its account key.")

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

    def action_retry(self) -> None:
        if self._busy:
            self.notify("A reply is pending. Wait or press Esc.", timeout=3)
            return
        last = None
        for item in reversed(self.history):
            if item.get("role") == "user":
                content = item.get("content")
                if isinstance(content, str) and content.strip():
                    last = content
                    break
        if not last:
            self.notify("Nothing to retry yet.", timeout=3)
            return
        self._log("↻ retrying last message…")
        self._send(last)

    def action_update(self) -> None:
        self._log("Checking for updates and reinstalling…")
        self.notify("Updating codelaboon…", timeout=3)
        self.run_worker(self._update_job, thread=True, exclusive=False, group="update")

    def _update_job(self) -> None:
        import contextlib
        import io

        buffer = io.StringIO()
        ok = False
        try:
            from codelaboon.update import update

            with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
                ok = update(editable=True, pull=True)
        except Exception as error:
            buffer.write(f"\n{error}")
        output = buffer.getvalue().strip()
        if not output:
            output = "Update complete. Restart codelaboon to use the new version." if ok else "Update failed."
        self.call_from_thread(self._log, output)
        self.call_from_thread(self.notify, "Update complete" if ok else "Update failed", timeout=4)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Route list selections: provider picks load models, model picks switch."""
        index = event.control.index
        if event.control.id == "providers":
            if index is not None and 0 <= index < len(self._provider_names):
                self._pending_model = None
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
    """Run the TUI in the current directory, which becomes the project root."""
    CodelaboonTuiApp().run()
