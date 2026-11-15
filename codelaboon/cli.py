#!/usr/bin/env python3
"""
codelaboon CLI interface - Harness for free AI model access

Declarative, provider-agnostic interface for accessing free AI models.
"""

import argparse
import json
import os
import stat
import sys
import subprocess
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from providers.base import BaseProvider
except ImportError:  # Allow running from a source checkout directly.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from providers.base import BaseProvider


class CodelaboonCLI:
    """Main CLI harness for free AI model access."""

    def __init__(self):
        from codelaboon.paths import config_dir

        self.config_dir = config_dir()
        # The directory codelaboon is launched from is the project root. TUI
        # sessions, the header and saved conversations use it.
        self.project_dir = Path.cwd().resolve()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.config_dir.chmod(0o700)
        except OSError:
            pass
        self.providers: Dict[str, BaseProvider] = {}

    def load_providers(self) -> None:
        """Load all configured providers."""
        from config.providers import get_providers_config

        providers_config = get_providers_config()

        for provider_name, provider_config in providers_config.items():
            try:
                provider_class = self._get_provider_class(provider_name)
            except (ImportError, AttributeError, ValueError):
                print(f"Warning: Provider {provider_name} not available")
                continue

            if not isinstance(provider_config, dict):
                print(f"Warning: Ignoring malformed configuration for {provider_name}")
                continue

            kwargs: Dict[str, Any] = {}
            base_url = provider_config.get("base_url")
            if isinstance(base_url, str) and base_url.strip():
                kwargs["base_url"] = base_url.strip()

            self.providers[provider_name] = provider_class(
                api_key=str(provider_config.get("api_key") or ""),
                models=provider_config.get("models") if isinstance(provider_config.get("models"), list) else [],
                **kwargs,
            )

        # Reuse a configured official OpenRouter key for its strictly free lane.
        paid=self.providers.get('openrouter')
        free=self.providers.get('openrouter_free')
        if paid and free and not free.api_key.strip() and getattr(paid,'base_url','').rstrip('/')==getattr(free,'base_url','').rstrip('/')=='https://openrouter.ai/api/v1':
            free.api_key=paid.api_key

    def _get_provider_class(self, provider_name: str):
        """Get provider class based on provider name."""
        provider_mapping = {
            "local": "providers.compatible.LocalProvider",
            "openrouter_free": "providers.compatible.OpenRouterFreeProvider",
            "zai_free": "providers.compatible.ZaiFreeProvider",
            "groq": "providers.compatible.GroqProvider",
            "cerebras": "providers.compatible.CerebrasProvider",
            "chatgpt": "providers.chatgpt.chatgpt_provider.ChatGPTProvider",
            "claude": "providers.claude.claude_provider.ClaudeProvider",
            "gemini": "providers.gemini.gemini_provider.GeminiProvider",
            "freebuff": "providers.freebuff.freebuff_provider.FreebuffProvider",
            "qoder": "providers.qoder.qoder_provider.QoderProvider",
            "nvidia": "providers.nvidia.nvidia_provider.NVIDIAProvider",
            "openrouter": "providers.openrouter.openrouter_provider.OpenRouterProvider",
            "luna": "providers.luna.luna_provider.LunaProvider",
            "ourfree": "providers.ourfree.ourfree_provider.OurFreeModelProvider",
            "kilo": "providers.kilo.kilo_provider.KiloProvider",
            "pollinations": "providers.pollinations.pollinations_provider.PollinationsProvider",
            "wusrouter": "providers.wusrouter.wusrouter_provider.WusRouterProvider",
        }

        if provider_name not in provider_mapping:
            raise ValueError(f"Unknown provider: {provider_name}")

        module_name, class_name = provider_mapping[provider_name].rsplit(".", 1)
        module = __import__(module_name, fromlist=[class_name])
        return getattr(module, class_name)

    @staticmethod
    def _tracked_secret_files() -> List[str]:
        """Return any tracked real configuration files, if this is a git repo."""
        expected = ("config/providers.toml", "config/api_keys.toml")
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return []

        tracked = set(result.stdout.splitlines())
        return [path for path in expected if path in tracked]

    def doctor(self) -> bool:
        """Diagnose local installation and configuration."""
        failures = 0

        def check(name: str, condition: bool, detail: str = "") -> None:
            nonlocal failures
            if condition:
                print(f"  âœ“ {name}")
            else:
                failures += 1
                suffix = f" â€” {detail}" if detail else ""
                print(f"  âœ— {name}{suffix}")

        print("codelaboon doctor")
        print("-" * 40)

        version = sys.version_info
        check(
            f"Python >= 3.11 ({version.major}.{version.minor}.{version.micro})",
            (version.major, version.minor) >= (3, 11),
        )

        try:
            import requests  # noqa: F401
            check("requests installed", True)
        except ImportError:
            check("requests installed", False, "install python3-requests or requests")

        for provider_name in (
            "chatgpt", "claude", "gemini", "freebuff", "qoder", "nvidia",
            "openrouter", "luna", "ourfree", "kilo", "pollinations",
            "wusrouter",
            "local", "openrouter_free", "groq", "cerebras",
        ):
            try:
                self._get_provider_class(provider_name)
                check(f"provider {provider_name} importable", True)
            except Exception as e:
                check(f"provider {provider_name} importable", False, str(e))

        config_file = self.config_dir / "providers.toml"
        if os.name == "posix":
            try:
                self.config_dir.mkdir(parents=True, exist_ok=True)
                self.config_dir.chmod(0o700)
                check("config directory is writable and private",
                      stat.S_IMODE(self.config_dir.stat().st_mode) & 0o077 == 0)
            except OSError as e:
                check("config directory is writable and private", False, str(e))
        else:
            print("  â„¹ config directory permissions: not applicable on this platform")

        from config.providers import get_providers_config

        config = get_providers_config()
        check("configuration loads", isinstance(config, dict))
        if os.name == "posix":
            try:
                mode = stat.S_IMODE(config_file.stat().st_mode) if config_file.exists() else None
                check("configuration file is private", mode == 0o600,
                      f"expected 600, got {oct(mode) if mode is not None else 'missing'}")
            except OSError as e:
                check("configuration file is private", False, str(e))
        else:
            print("  â„¹ configuration file permissions: not applicable on this platform")

        configured = sorted(
            name for name, values in config.items()
            if isinstance(values, dict) and str(values.get("api_key") or "").strip()
        )
        print(f"  â„¹ providers configured: {', '.join(configured) or 'none yet'}")

        tracked_secrets = self._tracked_secret_files()
        check("no real credentials are tracked by git", not tracked_secrets,
              "tracked: " + ", ".join(tracked_secrets))

        docs = Path(__file__).resolve().parent.parent / "docs"
        if docs.is_dir():
            for name in ("AGENTS.md", "ARCHITECTURE.md", "PROGRESS.md"):
                check(f"docs/{name} present", (docs / name).is_file())
        else:
            print("  â„¹ source documentation not present (installed package)")

        print("-" * 40)
        if failures:
            print(f"Doctor found {failures} problem(s).")
            return False
        print("Doctor passed.")
        return True

    def list_providers(self) -> None:
        """List all available providers."""
        print("Available Providers:")
        print("-" * 40)
        print("\nFREE (AUTO):")
        print("  Status: ✓ Ranks the free lanes by availability, intelligence and speed")
        print("  Models: free (Auto) — failover across ourfree/kilo/account lanes")

        for provider_name in sorted(self.providers):
            provider = self.providers[provider_name]
            print(f"\n{provider_name.upper()}:")
            if provider.keyless:
                print("  Status: âœ“ Free (no key needed)")
            else:
                try:
                    configured = bool(provider.api_key) or provider.validate_api_key()
                except Exception:
                    configured = bool(provider.api_key)
                print(f"  Status: {'âœ“ Configured' if configured else 'âœ— Not configured'}")

            try:
                models = provider.list_models()
                print(f"  Models ({len(models)}):")
                for model in models[:5]:
                    print(f"    - {model}")
                if len(models) > 5:
                    print(f"    ... and {len(models) - 5} more")
            except Exception as e:
                print(f"  Models: Error - {e}")

    @staticmethod
    def _qoder_alert() -> None:
        """Print the current Qoder limitation alert."""
        from codelaboon.qoder_auth import QODER_LIMITATION

        print(f"⚠ {QODER_LIMITATION}")

    def list_models(self, provider_name: str) -> None:
        """List models for a specific provider."""
        if provider_name == "free":
            from codelaboon.free_auto import AUTO_MODEL, describe

            print("\nModels for free:")
            print("-" * 40)
            print(f"1. {AUTO_MODEL} — best available free model (automatic failover)")
            for index, line in enumerate(describe(self.providers), 2):
                print(f"{index}. {line}")
            return

        provider = self._require_provider(provider_name)
        if provider is None:
            return
        if provider_name == "qoder":
            self._qoder_alert()

        print(f"\nModels for {provider_name}:")
        print("-" * 40)

        try:
            from codelaboon import model_health
            models = model_health.discover(provider_name,provider) if model_health.eligible(provider_name,provider) else provider.list_models()
            if model_health.enabled() and model_health.eligible(provider_name,provider):
                models=[model for model in models if model_health.verified(provider_name,provider,model)]
                if not models:
                    print('No verified models yet. Run codelaboon models check '+provider_name)
            for i, model in enumerate(models, 1):
                print(f"{i}. {model}")
        except Exception as e:
            print(f"Error listing models: {e}")

    def _require_provider(self, provider_name: str) -> Optional[BaseProvider]:
        provider = self.providers.get(provider_name)
        if provider is None:
            print(f"Error: Provider '{provider_name}' not found")
            print(f"Known providers: {', '.join(sorted(self.providers)) or 'none'}")
            return None
        return provider

    def chat(
        self,
        provider_name: str,
        model: str,
        prompt: str,
        system: str = "",
        **kwargs,
    ) -> bool:
        """Send a chat completion request. Returns True on success."""
        if provider_name == "free":
            from codelaboon import free_auto

            print("\nSending request to free (Auto):")
            print("-" * 40)
            print(f"Prompt: {prompt}")
            messages: List[Dict[str, str]] = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            try:
                chosen, response = free_auto.chat(
                    self.providers,
                    messages,
                    temperature=kwargs.get("temperature", 0.7),
                    max_tokens=kwargs.get("max_tokens", 1000),
                )
            except Exception as e:
                print(f"Error: {e}")
                return False
            print(f"\nAuto-selected: {chosen.provider}/{chosen.model} ({chosen.display})")
            print("\nResponse:")
            print("-" * 40)
            print(response)
            return True

        provider = self._require_provider(provider_name)
        if provider is None:
            return False
        if provider_name == "qoder":
            self._qoder_alert()

        print(f"\nSending request to {provider_name}/{model}:")
        print("-" * 40)
        print(f"Prompt: {prompt}")

        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = provider.chat(model, messages, **kwargs)
            print("\nResponse:")
            print("-" * 40)
            print(response)
            return True
        except Exception as e:
            print(f"Error: {e}")
            return False

    def decide(
        self,
        provider_name: str,
        model: str,
        input_text: str,
        questions: List[Any],
        as_json: bool = False,
    ) -> bool:
        """Send a typed decision request. Returns True on success."""
        provider = self._require_provider(provider_name)
        if provider is None:
            return False

        if not provider.supports_decisions():
            print(f"Error: provider '{provider_name}' has no decision route")
            print("Providers with decisions: chatgpt, openrouter")
            return False

        try:
            answers = provider.decision(model, input_text, questions)
        except Exception as e:
            print(f"Error: {e}")
            return False

        if as_json:
            from codelaboon.decision import answer_to_dict

            print(json.dumps([answer_to_dict(answer) for answer in answers], indent=2))
        else:
            from codelaboon.decision import format_answers

            print(format_answers(answers))
        return True

    @staticmethod
    def _current_provider_config(provider_name: str) -> Dict[str, Any]:
        """The provider's stored configuration with sane defaults."""
        from config.providers import get_providers_config

        config = get_providers_config().get(provider_name)
        if not isinstance(config, dict):
            config = {}
        config.setdefault("api_key", "")
        config.setdefault("models", [])
        return config

    def configure_provider(self, provider_name: str) -> None:
        """Configure a provider interactively."""
        if provider_name == "qoder":
            self._qoder_alert()
        print(f"\nConfiguring {provider_name}:")
        print("-" * 40)

        try:
            provider_class = self._get_provider_class(provider_name)
        except (ImportError, AttributeError, ValueError):
            provider_class = None

        if provider_class is not None and getattr(provider_class, "signup_url", None):
            print(f"Sign up and create an API key at {provider_class.signup_url}")

        if provider_class is not None and getattr(provider_class, "keyless", False):
            # Keyless pools need no credential; only a base URL override if
            # the gateway is reachable somewhere else.
            print(f"{provider_name} is keyless â€” no API key needed.")
            base_url = input("Enter a base URL override (enter to skip): ").strip()
            if not base_url:
                print("Using existing configuration.")
                return
            from config.providers import save_provider_config

            existing = self._current_provider_config(provider_name)
            existing["base_url"] = base_url
            if save_provider_config(provider_name, existing):
                print(f"âœ“ {provider_name} configured successfully")
                self.load_providers()
            else:
                print(f"âœ— Failed to configure {provider_name}")
            return

        if provider_name in ("claude", "gemini", "freebuff", "qoder"):
            # Subscription and free-tier accounts sign in instead of pasting
            # a key; an explicit key still works for all four providers.
            api_key = input(
                f"Enter an API key for {provider_name}, or leave blank to "
                "sign in with an account: "
            ).strip()
            if not api_key:
                if provider_name == "freebuff":
                    from codelaboon.freebuff_auth import login

                    try:
                        login()
                    except (ValueError, OSError) as error:
                        print(f"Sign-in failed: {error}")
                    else:
                        self.load_providers()
                    return

                if provider_name == "qoder":
                    from codelaboon.qoder_auth import login

                    try:
                        login()
                    except (ValueError, OSError) as error:
                        print(f"Sign-in failed: {error}")
                    else:
                        self.load_providers()
                    return

                if provider_name == "claude":
                    from codelaboon.claude_auth import login

                    try:
                        login()
                    except (ValueError, OSError) as error:
                        print(f"Sign-in failed: {error}")
                    else:
                        self.load_providers()
                    return

                from codelaboon import gemini_auth

                try:
                    gemini_auth.client()
                except ValueError:
                    print(
                        "Gemini account sign-in needs a Google OAuth client.\n"
                        "Create a free Desktop OAuth client in Google Cloud "
                        "Console, then import its JSON file or enter the values."
                    )
                    path = input(
                        "Path to the OAuth client JSON "
                        "(enter to type the values): "
                    ).strip()
                    try:
                        if path:
                            gemini_auth.import_oauth_client(path)
                        else:
                            client_id = input("OAuth client ID: ").strip()
                            client_secret = input(
                                "OAuth client secret: "
                            ).strip()
                            gemini_auth.save_oauth_client(
                                client_id, client_secret
                            )
                    except (OSError, ValueError) as error:
                        print(f"Could not save the OAuth client: {error}")
                        return
                try:
                    gemini_auth.login()
                except (ValueError, OSError) as error:
                    print(f"Sign-in failed: {error}")
                else:
                    self.load_providers()
                return
        else:
            api_key = input(f"Enter API key for {provider_name}: ").strip()

        if not api_key:
            print("No API key provided. Using existing configuration.")
            return

        config: Dict[str, Any] = {
            "api_key": api_key,
            "models": [],  # Will be populated automatically
        }

        if provider_name == "ourfree":
            # The forward gateway can move off port 18899 when it is taken;
            # the settings page shows the port it actually listens on.
            base_url = input(
                "Enter the gateway base URL (enter for http://127.0.0.1:18899/v1): "
            ).strip()
            if base_url:
                config["base_url"] = base_url
            else:
                existing = self._current_provider_config(provider_name)
                if str(existing.get("base_url") or "").strip():
                    config["base_url"] = str(existing["base_url"]).strip()

        from config.providers import save_provider_config

        success = save_provider_config(provider_name, config)

        if success:
            print(f"âœ“ {provider_name} configured successfully")
            self.load_providers()
        else:
            print(f"âœ— Failed to configure {provider_name}")

    def run(self) -> None:
        """Main CLI entry point."""
        parser = argparse.ArgumentParser(
            description="codelaboon - Harness for free AI model access",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        try:
            from codelaboon import __version__
        except ImportError:  # Running from a directly executed module.
            __version__ = "unknown"
        parser.add_argument(
            "--version", action="version", version=f"codelaboon {__version__}"
        )

        subparsers = parser.add_subparsers(dest="command", help="Available commands")
        subparsers.add_parser("work", help="Control background cloud workers (start/status/stop/add)")
        subparsers.add_parser("controller-eval", help="Evaluate the optional local supervisor against scope fixtures")
        subparsers.add_parser("routing", help="Measured task-aware routing status and policy")
        subparsers.add_parser("security", help="Run scoped, evidence-backed security assessment workflows")
        subparsers.add_parser("privilege", help="Review and approve bounded root/administrator cases")
        subparsers.add_parser("sessions", help="Share, resume or convert sessions across coding engines")
        subparsers.add_parser("ourfree", help="Run or connect the official standalone Our Free Model gateway")
        subparsers.add_parser("opencode", help="Open the default native OpenCode UI")
        subparsers.add_parser("omp", help="Open the optional OMP interface (automatic setup)")
        subparsers.add_parser("kilo", help="Open the optional official Kilo native CLI")
        subparsers.add_parser("claude", help="Open Claude Code on Codelaboon free models")
        subparsers.add_parser("ide", help="Connect official engine editor integrations to Codelaboon")
        subparsers.add_parser("storage", help="Audit or relocate development/cache bulk outside the project")
        subparsers.add_parser("swarm", help="Run a bounded lightweight Rust swarm on the free backend")
        subparsers.add_parser("codex", help="Open native Codex on the Codelaboon backend")
        subparsers.add_parser("jcode", help="Open the native Jcode UI (Rust, automatic setup, free backend)")
        subparsers.add_parser("crush", help="Open the optional Crush native UI on Codelaboon free models")

        # List providers command
        providers_parser = subparsers.add_parser("providers", help="Provider management")
        providers_subparsers = providers_parser.add_subparsers(dest="providers_command")
        providers_subparsers.add_parser("list", help="List all providers")
        health = providers_subparsers.add_parser("check", help="Check credential presence and catalogue access")
        health.add_argument("--live", action="store_true", help="Request provider catalogues; does not test inference quota")

        # Models command
        models_parser = subparsers.add_parser("models", help="Model management")
        models_subparsers = models_parser.add_subparsers(dest="models_command")
        list_models_parser = models_subparsers.add_parser("list", help="List models for a provider")
        list_models_parser.add_argument("provider", help="Provider name")

        check_models_parser = models_subparsers.add_parser("check", help="Verify free models with real replies and tool calls")
        check_models_parser.add_argument("provider", nargs="?", default="free")
        check_models_parser.add_argument("--force", action="store_true", help="Recheck fresh health records")
        check_models_parser.add_argument("--timeout", type=int, default=15)
        check_models_parser.add_argument("--chat-only", action="store_true")
        check_models_parser.add_argument("--require-working", action="store_true", help="Exit nonzero if no checked route passes")
        formats=check_models_parser.add_mutually_exclusive_group()
        formats.add_argument("--json", action="store_true")
        formats.add_argument("--jsonl", action="store_true", help="Stream one JSON health record per checked model")

        # Chat command
        chat_parser = subparsers.add_parser("chat", help="Send chat completion request")
        chat_parser.add_argument("provider", help="Provider name")
        chat_parser.add_argument("model", help="Model name")
        chat_parser.add_argument("prompt", help="Prompt text")
        chat_parser.add_argument("--system", help="System message", default="")
        chat_parser.add_argument("--temperature", type=float, default=0.7, help="Temperature (0-1)")
        chat_parser.add_argument("--max-tokens", type=int, default=1000, help="Max tokens")

        # Decision command
        decision_parser = subparsers.add_parser(
            "decision", help="Ask typed predicate/choice/score questions"
        )
        decision_parser.add_argument("provider", help="Provider name")
        decision_parser.add_argument("model", help="Decision model name")
        decision_parser.add_argument("input", help="Input text to evaluate")
        decision_parser.add_argument(
            "--questions", help="JSON file containing a list of questions"
        )
        decision_parser.add_argument(
            "--predicate",
            action="append",
            default=[],
            metavar="NAME=INSTRUCTIONS",
            help="Inline predicate question (repeatable)",
        )
        decision_parser.add_argument(
            "--choice",
            action="append",
            default=[],
            metavar="NAME=INSTRUCTIONS|VALUE1,VALUE2",
            help="Inline choice question (repeatable)",
        )
        decision_parser.add_argument(
            "--score",
            action="append",
            default=[],
            metavar="NAME=INSTRUCTIONS|LABEL1,LABEL2",
            help="Inline score question (repeatable)",
        )
        decision_parser.add_argument(
            "--json", action="store_true", help="Print answers as JSON"
        )

        login_parser = subparsers.add_parser(
            "login", help="Sign in with an account for plan or free-tier access"
        )
        login_parser.add_argument(
            "provider", choices=["chatgpt", "claude", "gemini", "freebuff", "qoder"]
        )

        # Configure command
        configure_parser = subparsers.add_parser("configure", help="Configure provider")
        configure_parser.add_argument("provider", help="Provider name")

        # Doctor command
        subparsers.add_parser("doctor", help="Diagnose installation and configuration")

        # TUI command
        tui_parser = subparsers.add_parser("tui", help="Native OpenCode/OMP source TUI")
        tui_parser.add_argument("--engine", choices=["opencode", "omp", "kilo", "claude", "crush", "jcode", "codex"], default="opencode", help=argparse.SUPPRESS)
        tui_parser.add_argument("--setup", action="store_true", help="Install the selected fork's dependencies")
        tui_parser.add_argument("--profile", choices=["coding", "security"], default="coding")
        tui_parser.add_argument("--local-only", action="store_true", help="Use only local inference; disable cloud model fallback")
        tui_parser.add_argument("--theme", help="Native theme name; saved native theme selections are preserved by default")
        tui_parser.add_argument("native_args", nargs=argparse.REMAINDER, help="Arguments after -- go to the native TUI")

        install_parser = subparsers.add_parser(
            "install", help="Install for the current user and add codelaboon to PATH"
        )
        install_parser.add_argument(
            "--editable", "-e", action="store_true", help="Install the source checkout in editable mode"
        )
        install_parser.add_argument(
            "--no-path", action="store_true", help="Do not modify PATH"
        )
        install_parser.add_argument("--prepare-runtime", action="store_true", help="Prepare the default engine now instead of on first use")
        install_parser.add_argument("--engine", choices=["opencode", "omp", "kilo", "claude", "crush", "jcode", "codex"], default="opencode", help=argparse.SUPPRESS)

        update_parser = subparsers.add_parser(
            "update", help="Pull latest source changes and reinstall codelaboon"
        )
        update_parser.add_argument(
            "--no-pull", action="store_true", help="Skip git pull; only reinstall"
        )
        update_parser.add_argument(
            "--no-editable", action="store_true", help="Install as a regular package instead of editable"
        )
        update_parser.add_argument("--prepare-runtime", action="store_true", help="Prepare the engine now instead of on first use")
        update_parser.add_argument("--engine", choices=["opencode", "omp", "kilo", "claude", "crush", "jcode", "codex"], default="opencode", help=argparse.SUPPRESS)

        web_parser = subparsers.add_parser("web", help="Open the localhost web workspace")
        web_parser.add_argument("--port", type=int, default=8765)
        web_parser.add_argument("--no-open", action="store_true")

        # Parse arguments
        args = parser.parse_args()

        if not args.command:
            run_tui()
            return

        if args.command == "install":
            from codelaboon.install import install

            if not install(editable=args.editable, update_path=not args.no_path,
                           runtime=args.prepare_runtime, engine=args.engine):
                sys.exit(1)
            return

        if args.command == "update":
            from codelaboon.update import update

            if not update(editable=not args.no_editable, pull=not args.no_pull,
                          runtime=args.prepare_runtime, engine=args.engine):
                sys.exit(1)
            return

        # Load providers
        self.load_providers()

        # Execute commands
        if args.command == "providers":
            if args.providers_command == "list":
                self.list_providers()
            elif args.providers_command == "check":
                from codelaboon.provider_health import inspect
                print(json.dumps(inspect(self.providers, args.live), indent=2))
            else:
                providers_parser.print_help()

        elif args.command == "models":
            if args.models_command == "list":
                self.list_models(args.provider)
            elif args.models_command == "check":
                from codelaboon import model_health
                if args.provider != 'free' and args.provider not in model_health.FREE_PROVIDERS:
                    parser.error('Choose free or a declared free provider')
                if not 1 <= args.timeout <= 120:
                    parser.error('--timeout must be 1–120 seconds')
                providers=self.providers if args.provider=='free' else {args.provider:self.providers[args.provider]} if args.provider in self.providers else {}
                import threading
                progress_lock=threading.Lock()
                def progress(row):
                    with progress_lock:
                        if args.jsonl:
                            print(json.dumps(row),flush=True)
                        else:
                            print(row['provider']+'/'+row.get('model','*')+' | '+row['status']+
                                  (' | tools: '+str(row['tools']) if 'tools' in row else ' | '+row.get('reason',''))+
                                  (' | cached' if row.get('cached') else ''),flush=True)
                rows=model_health.check(providers,args.timeout,not args.chat_only,args.force,
                                        None if args.json else progress)
                if args.json:print(json.dumps(rows,indent=2))
                elif not args.jsonl:print('Health cache updated. Reopen the engine to refresh its model picker.')
                if args.require_working and not any(row['status']=='working' and (args.chat_only or row.get('tools') is True) for row in rows):
                    print('No checked free route passed the required verification.',file=sys.stderr)
                    raise SystemExit(1)
            else:
                models_parser.print_help()

        elif args.command == "chat":
            if not self.chat(
                args.provider,
                args.model,
                args.prompt,
                system=args.system,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
            ):
                sys.exit(1)

        elif args.command == "decision":
            from codelaboon.decision import (
                DecisionError,
                parse_question_spec,
                questions_from_json,
            )

            try:
                inline = (
                    [("predicate", spec) for spec in args.predicate]
                    + [("choice", spec) for spec in args.choice]
                    + [("score", spec) for spec in args.score]
                )
                if args.questions:
                    questions = questions_from_json(args.questions)
                else:
                    questions = []
                questions.extend(parse_question_spec(kind, spec) for kind, spec in inline)
                if not questions:
                    raise DecisionError(
                        "provide --questions or at least one --predicate/--choice/--score"
                    )
                names = [question.name for question in questions]
                if len(set(names)) != len(names):
                    raise DecisionError("question names must be unique")
            except (DecisionError, OSError) as e:
                print(f"Error: {e}")
                sys.exit(2)

            if not self.decide(
                args.provider,
                args.model,
                args.input,
                questions,
                as_json=args.json,
            ):
                sys.exit(1)

        elif args.command == "login":
            if args.provider == "claude":
                from codelaboon.claude_auth import login
            elif args.provider == "gemini":
                from codelaboon.gemini_auth import login
            elif args.provider == "freebuff":
                from codelaboon.freebuff_auth import login
            elif args.provider == "qoder":
                from codelaboon.qoder_auth import login

                self._qoder_alert()
            else:
                from codelaboon.chatgpt_auth import login
            try:
                login()
            except (ValueError, OSError) as error:
                print(f"Sign-in failed: {error}")
                sys.exit(1)

        elif args.command == "configure":
            self.configure_provider(args.provider)

        elif args.command == "doctor":
            if not self.doctor():
                sys.exit(1)

        elif args.command == "web":
            from codelaboon.web import serve
            serve(args.port, open_browser=not args.no_open)

        elif args.command == "tui":
            if args.setup:
                from codelaboon.native_tui import setup
                try:
                    setup(args.engine)
                except (RuntimeError, OSError, ValueError, requests.RequestException, subprocess.CalledProcessError) as error:
                    print(f"TUI setup failed: {error}", file=sys.stderr)
                    sys.exit(2)
            else:
                arguments = args.native_args
                if arguments[:1] == ["--"]:
                    arguments = arguments[1:]
                run_tui(args.engine, arguments, args.profile, args.local_only, args.theme)


def run_tui(engine="opencode", arguments=(), profile="coding", local_only=False, theme=None) -> None:
    """Launch the actual source fork; never silently fall back to Textual."""
    try:
        from codelaboon.native_tui import launch
        code = launch(engine, arguments, profile, local_only, theme)
    except (RuntimeError, OSError, subprocess.CalledProcessError, requests.RequestException) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
    if code:
        sys.exit(code)


def main() -> None:
    """Main entry point."""
    # Piped/redirected streams on Windows default to a legacy code page that
    # cannot encode the status marks; degrade instead of crashing.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except (OSError, ValueError):
                pass
    if sys.argv[1:2] and sys.argv[1] in ("opencode", "omp", "kilo", "claude", "crush", "jcode", "codex"):
        run_tui(sys.argv[1], sys.argv[2:])
        return
    if sys.argv[1:2] == ['controller-eval']:
        from codelaboon.controller_evaluation import main as evaluate
        raise SystemExit(evaluate(sys.argv[2:]))
    if sys.argv[1:2] == ['doctor']:
        if len(sys.argv)==2:
            ok=CodelaboonCLI().doctor()
            from codelaboon.doctor import main as doctor
            doctor([])
            if not ok:raise SystemExit(1)
        else:
            from codelaboon.doctor import main as doctor
            doctor(sys.argv[2:])
        return
    if sys.argv[1:2] == ['routing']:
        from codelaboon.routing_metrics import main as routing_main
        routing_main(sys.argv[2:]);return
    if sys.argv[1:2] == ['security']:
        from codelaboon.security_assessment import main as security_main
        security_main(sys.argv[2:]);return
    if sys.argv[1:2] == ['privilege']:
        from codelaboon.privilege import main as privilege_main
        privilege_main(sys.argv[2:]);return
    if sys.argv[1:2] == ['sessions']:
        from codelaboon.session_transfer import main as session_main
        session_main(sys.argv[2:])
        return
    if sys.argv[1:2] == ['ide']:
        from codelaboon.ide import main as ide_main
        ide_main(sys.argv[2:])
        return
    if sys.argv[1:2] == ['storage']:
        from codelaboon.storage import main as storage_main
        storage_main(sys.argv[2:])
        return
    if sys.argv[1:2] == ['swarm']:
        from codelaboon.swarm import main as swarm_main
        swarm_main(sys.argv[2:])
        return
    if sys.argv[1:2] == ['work']:
        from codelaboon.work import main as work_main
        work_main(sys.argv[2:])
        return
    if sys.argv[1:2] == ['ourfree']:
        from codelaboon.ourfree_service import main as ourfree_main
        ourfree_main(sys.argv[2:])
        return
    cli = CodelaboonCLI()
    cli.run()


if __name__ == "__main__":
    main()
