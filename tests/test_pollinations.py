"""Offline tests for the keyless Pollinations lane."""

import unittest
from unittest.mock import Mock, patch

import requests

from providers.pollinations.pollinations_provider import PollinationsProvider


class PollinationsTests(unittest.TestCase):
    def test_keyless_validation(self):
        provider = PollinationsProvider()
        self.assertTrue(provider.validate_api_key())

    def test_discovery_keeps_text_models_and_deduplicates(self):
        response = Mock(status_code=200)
        response.json.return_value = [
            {"name": "openai-fast", "output_modalities": ["text"]},
            {"name": "openai-fast", "output_modalities": ["text"]},
            {"name": "flux", "output_modalities": ["image"]},
            {"name": None},
            "bad",
        ]
        provider = PollinationsProvider(models=[])
        with patch("requests.get", return_value=response) as request:
            self.assertEqual(provider.list_models(), ["openai-fast"])
        self.assertTrue(
            request.call_args.args[0].endswith("/models")
        )
        self.assertNotIn("authorization", request.call_args.kwargs["headers"])

    def test_discovery_failure_uses_configured_then_default(self):
        with patch("requests.get", side_effect=requests.ConnectionError()):
            self.assertEqual(
                PollinationsProvider(models=["pinned"]).list_models(), ["pinned"]
            )
            self.assertEqual(
                PollinationsProvider(models=[]).list_models(), ["openai-fast"]
            )

    def test_chat_uses_openai_endpoint_and_anonymous_request(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "choices": [{"message": {"content": "hello"}}]
        }
        provider = PollinationsProvider()
        with patch("requests.post", return_value=response) as request:
            reply = provider.chat(
                "openai-fast", [{"role": "user", "content": "hi"}]
            )
        self.assertEqual(reply, "hello")
        self.assertEqual(
            request.call_args.args[0], "https://text.pollinations.ai/openai"
        )
        self.assertNotIn("authorization", request.call_args.kwargs["headers"])
        self.assertEqual(request.call_args.kwargs["json"]["model"], "openai-fast")

    def test_configured_token_is_sent_as_bearer(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        provider = PollinationsProvider(api_key="token")
        with patch("requests.post", return_value=response) as request:
            provider.chat("openai-fast", [{"role": "user", "content": "hi"}])
        self.assertEqual(
            request.call_args.kwargs["headers"]["authorization"], "Bearer token"
        )

    def test_error_status_and_error_document_are_reported(self):
        with patch(
            "requests.post",
            return_value=Mock(status_code=429, text="rate limited"),
        ):
            with self.assertRaisesRegex(Exception, "429"):
                PollinationsProvider().chat(
                    "openai-fast", [{"role": "user", "content": "hi"}]
                )

        response = Mock(status_code=200)
        response.json.return_value = {"error": {"message": "quota exhausted"}}
        with patch("requests.post", return_value=response):
            with self.assertRaisesRegex(Exception, "quota exhausted"):
                PollinationsProvider().chat(
                    "openai-fast", [{"role": "user", "content": "hi"}]
                )


if __name__ == "__main__":
    unittest.main()
