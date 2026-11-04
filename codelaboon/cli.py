#!/usr/bin/env python3
"""
codelaboon CLI interface - Harness for free AI model access

Declarative, provider-agnostic interface for accessing free AI models.
"""

import argparse
import sys
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
        self.config_dir = Path.home() / ".config" / "codelaboon"
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

            self.providers[provider_name] = provider_class(
                api_key=str(provider_config.get("api_key") or ""),
                models=provider_config.get("models") if isinstance(provider_config.get("models"), list) else [],
            )

    def _get_provider_class(self, provider_name: str):
        """Get provider class based on provider name."""
        provider_mapping = {
            "chatgpt": "providers.chatgpt.chatgpt_provider.ChatGPTProvider",
            "nvidia": "providers.nvidia.nvidia_provider.NVIDIAProvider",
            "openrouter": "providers.openrouter.openrouter_provider.OpenRouterProvider",
            "luna": "providers.luna.luna_provider.LunaProvider",
        }

        if provider_name not in provider_mapping:
            raise ValueError(f"Unknown provider: {provider_name}")

        module_name, class_name = provider_mapping[provider_name].rsplit(".", 1)
        module = __import__(module_name, fromlist=[class_name])
        return getattr(module, class_name)

    def list_providers(self) -> None:
        """List all available providers."""
        print("Available Providers:")
        print("-" * 40)

        for provider_name in sorted(self.providers):
            provider = self.providers[provider_name]
            print(f"\n{provider_name.upper()}:")
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
    ) -> None:
        """Send a chat completion request."""
        provider = self._require_provider(provider_name)
        if provider is None:
            return

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
        except Exception as e:
            print(f"Error: {e}")

    def configure_provider(self, provider_name: str) -> None:
        """Configure a provider interactively."""
        print(f"\nConfiguring {provider_name}:")
        print("-" * 40)

        api_key = input(f"Enter API key for {provider_name}: ").strip()

        if not api_key:
            print("No API key provided. Using existing configuration.")
            return

        from config.providers import save_provider_config

        success = save_provider_config(
            provider_name,
            {
                "api_key": api_key,
                "models": [],  # Will be populated automatically
            },
        )

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

        # Configure command
        configure_parser = subparsers.add_parser("configure", help="Configure provider")
        configure_parser.add_argument("provider", help="Provider name")

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
            self.chat(
                args.provider,
                args.model,
                args.prompt,
                system=args.system,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
            )

        elif args.command == "configure":
            self.configure_provider(args.provider)


def main() -> None:
    """Main entry point."""
    cli = CodelaboonCLI()
    cli.run()


if __name__ == "__main__":
    main()
