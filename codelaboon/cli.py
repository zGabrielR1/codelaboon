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
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from providers.base import BaseProvider
except ImportError:  # Allow running from a source checkout directly.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from providers.base import BaseProvider


class CodelaboonCLI:
    """Main CLI harness for free AI model access."""

    def __init__(self):
        self.config_dir = Path(
            os.environ.get("CODELABOON_CONFIG_DIR", str(Path.home() / ".config" / "codelaboon"))
        )
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

    def _get_provider_class(self, provider_name: str):
        """Get provider class based on provider name."""
        provider_mapping = {
            "chatgpt": "providers.chatgpt.chatgpt_provider.ChatGPTProvider",
            "nvidia": "providers.nvidia.nvidia_provider.NVIDIAProvider",
            "openrouter": "providers.openrouter.openrouter_provider.OpenRouterProvider",
            "luna": "providers.luna.luna_provider.LunaProvider",
            "ourfree": "providers.ourfree.ourfree_provider.OurFreeModelProvider",
            "kilo": "providers.kilo.kilo_provider.KiloProvider",
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
                print(f"  ✓ {name}")
            else:
                failures += 1
                suffix = f" — {detail}" if detail else ""
                print(f"  ✗ {name}{suffix}")

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

        for provider_name in ("chatgpt", "nvidia", "openrouter", "luna", "ourfree", "kilo"):
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
            print("  ℹ config directory permissions: not applicable on this platform")

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
            print("  ℹ configuration file permissions: not applicable on this platform")

        configured = sorted(
            name for name, values in config.items()
            if isinstance(values, dict) and str(values.get("api_key") or "").strip()
        )
        print(f"  ℹ providers configured: {', '.join(configured) or 'none yet'}")

        tracked_secrets = self._tracked_secret_files()
        check("no real credentials are tracked by git", not tracked_secrets,
              "tracked: " + ", ".join(tracked_secrets))

        docs = Path(__file__).resolve().parent.parent / "docs"
        if docs.is_dir():
            for name in ("AGENTS.md", "ARCHITECTURE.md", "PROGRESS.md"):
                check(f"docs/{name} present", (docs / name).is_file())
        else:
            print("  ℹ source documentation not present (installed package)")

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

        for provider_name in sorted(self.providers):
            provider = self.providers[provider_name]
            print(f"\n{provider_name.upper()}:")
            if provider.keyless:
                print("  Status: ✓ Free (no key needed)")
            else:
                print(f"  Status: {'✓ Configured' if provider.api_key else '✗ Not configured'}")

            try:
                models = provider.list_models()
                print(f"  Models ({len(models)}):")
                for model in models[:5]:
                    print(f"    - {model}")
                if len(models) > 5:
                    print(f"    ... and {len(models) - 5} more")
            except Exception as e:
                print(f"  Models: Error - {e}")

    def list_models(self, provider_name: str) -> None:
        """List models for a specific provider."""
        provider = self._require_provider(provider_name)
        if provider is None:
            return

        print(f"\nModels for {provider_name}:")
        print("-" * 40)

        try:
            models = provider.list_models()
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
        provider = self._require_provider(provider_name)
        if provider is None:
            return False

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
        print(f"\nConfiguring {provider_name}:")
        print("-" * 40)

        try:
            provider_class = self._get_provider_class(provider_name)
        except (ImportError, AttributeError, ValueError):
            provider_class = None

        if provider_class is not None and getattr(provider_class, "keyless", False):
            # Keyless pools need no credential; only a base URL override if
            # the gateway is reachable somewhere else.
            print(f"{provider_name} is keyless — no API key needed.")
            base_url = input("Enter a base URL override (enter to skip): ").strip()
            if not base_url:
                print("Using existing configuration.")
                return
            from config.providers import save_provider_config

            existing = self._current_provider_config(provider_name)
            existing["base_url"] = base_url
            if save_provider_config(provider_name, existing):
                print(f"✓ {provider_name} configured successfully")
                self.load_providers()
            else:
                print(f"✗ Failed to configure {provider_name}")
            return

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
            print(f"✓ {provider_name} configured successfully")
            self.load_providers()
        else:
            print(f"✗ Failed to configure {provider_name}")

    def run(self) -> None:
        """Main CLI entry point."""
        parser = argparse.ArgumentParser(
            description="codelaboon - Harness for free AI model access",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        subparsers = parser.add_subparsers(dest="command", help="Available commands")

        # List providers command
        providers_parser = subparsers.add_parser("providers", help="Provider management")
        providers_subparsers = providers_parser.add_subparsers(dest="providers_command")
        providers_subparsers.add_parser("list", help="List all providers")

        # Models command
        models_parser = subparsers.add_parser("models", help="Model management")
        models_subparsers = models_parser.add_subparsers(dest="models_command")
        list_models_parser = models_subparsers.add_parser("list", help="List models for a provider")
        list_models_parser.add_argument("provider", help="Provider name")

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

        # Configure command
        configure_parser = subparsers.add_parser("configure", help="Configure provider")
        configure_parser.add_argument("provider", help="Provider name")

        # Doctor command
        subparsers.add_parser("doctor", help="Diagnose installation and configuration")

        # TUI command
        subparsers.add_parser("tui", help="Interactive terminal UI (needs the textual extra)")

        # Parse arguments
        args = parser.parse_args()

        if not args.command:
            parser.print_help()
            return

        # Load providers
        self.load_providers()

        # Execute commands
        if args.command == "providers":
            if args.providers_command == "list":
                self.list_providers()
            else:
                providers_parser.print_help()

        elif args.command == "models":
            if args.models_command == "list":
                self.list_models(args.provider)
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

        elif args.command == "configure":
            self.configure_provider(args.provider)

        elif args.command == "doctor":
            if not self.doctor():
                sys.exit(1)

        elif args.command == "tui":
            run_tui()


def run_tui() -> None:
    """Launch the terminal UI, with a hint when its extra is missing."""
    try:
        from codelaboon.tui import run_app
    except ImportError:
        print("The TUI needs the 'textual' package, which is an optional extra.")
        print("Install it with:  python3 -m pip install 'codelaboon[tui]'")
        print("or directly:       python3 -m pip install textual")
        sys.exit(2)
    run_app()


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
    cli = CodelaboonCLI()
    cli.run()


if __name__ == "__main__":
    main()
