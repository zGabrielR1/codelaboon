"""Offline smoke and unit tests for the codelaboon harness."""

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_ORIGINAL_CONFIG_DIR = os.environ.get("CODELABOON_CONFIG_DIR")
_TMPDIR = tempfile.TemporaryDirectory()
os.environ["CODELABOON_CONFIG_DIR"] = _TMPDIR.name

from config.providers import get_providers_config, save_provider_config  # noqa: E402
from codelaboon.cli import CodelaboonCLI  # noqa: E402
from providers.chatgpt.chatgpt_provider import ChatGPTProvider  # noqa: E402
from providers.luna.luna_provider import LunaProvider  # noqa: E402
from providers.nvidia.nvidia_provider import NVIDIAProvider  # noqa: E402
from providers.openrouter.openrouter_provider import OpenRouterProvider  # noqa: E402


def tearDownModule():
    if _ORIGINAL_CONFIG_DIR is None:
        os.environ.pop("CODELABOON_CONFIG_DIR", None)
    else:
        os.environ["CODELABOON_CONFIG_DIR"] = _ORIGINAL_CONFIG_DIR
    _TMPDIR.cleanup()


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class ConfigTests(unittest.TestCase):
    def test_default_config_is_created_with_restrictive_permissions(self):
        config_dir = Path(os.environ["CODELABOON_CONFIG_DIR"])

        config = get_providers_config()

        self.assertEqual(set(config), {"chatgpt", "nvidia", "openrouter", "luna"})
        self.assertTrue((config_dir / "providers.toml").is_file())
        self.assertEqual((config_dir / "providers.toml").stat().st_mode & 0o777, 0o600)

    def test_save_provider_config_roundtrips(self):
        self.assertTrue(
            save_provider_config("openrouter", {"api_key": "test-key", "models": ["a/b"]})
        )
        reloaded = get_providers_config()
        self.assertEqual(reloaded["openrouter"]["api_key"], "test-key")
        self.assertEqual(reloaded["openrouter"]["models"], ["a/b"])


class DoctorTests(unittest.TestCase):
    def test_doctor_passes_on_a_clean_checkout(self):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertTrue(CodelaboonCLI().doctor())
        self.assertIn("Doctor passed.", out.getvalue())


class ProviderTests(unittest.TestCase):
    def test_default_model_lists_are_non_empty(self):
        for provider_class in (ChatGPTProvider, NVIDIAProvider, OpenRouterProvider, LunaProvider):
            with self.subTest(provider=provider_class.__name__):
                provider = provider_class(api_key="", models=[])
                models = provider.list_models()
                self.assertTrue(models)

    def test_chat_requires_a_key(self):
        provider = OpenRouterProvider(api_key="", models=["model"])
        with self.assertRaises(ValueError):
            provider.chat("model", [{"role": "user", "content": "hi"}])

    def test_chat_sends_expected_payload(self):
        payload = {"choices": [{"message": {"content": "hello back"}}]}
        with mock.patch("requests.post", return_value=FakeResponse(payload)) as request:
            provider = ChatGPTProvider(api_key="test-key", models=["gpt-x"])
            answer = provider.chat("gpt-x", [{"role": "user", "content": "hi"}], temperature=0)

        self.assertEqual(answer, "hello back")
        _, kwargs = request.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(kwargs["json"]["model"], "gpt-x")

    def test_chat_surfaces_api_errors(self):
        fake = FakeResponse({"error": "nope"}, status_code=429)
        with mock.patch("requests.post", return_value=fake):
            provider = NVIDIAProvider(api_key="test-key", models=["model"])
            with self.assertRaises(Exception):
                provider.chat("model", [{"role": "user", "content": "hi"}])


if __name__ == "__main__":
    unittest.main()
