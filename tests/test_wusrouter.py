"""Offline gateway discovery and credential tests."""
import unittest
from unittest.mock import Mock, patch
import requests
from providers.wusrouter.wusrouter_provider import WusRouterProvider


class WusRouterTests(unittest.TestCase):
    def test_public_discovery_keeps_all_ids_and_deduplicates(self):
        provider = WusRouterProvider()
        response = Mock(status_code=200)
        response.json.return_value = {"data": [{"id": "model:free"}, {"id": "model-paid"},
            {"id": "model:free"}, {"id": None}, {"id": {}}, "bad"]}
        with patch("requests.get", return_value=response) as get:
            self.assertEqual(provider.list_models(), ["model:free", "model-paid"])
        self.assertNotIn("Authorization", get.call_args.kwargs["headers"])
        self.assertFalse(provider.validate_api_key())

    def test_failure_uses_configured_fallback(self):
        provider = WusRouterProvider(models=["saved-model"])
        with patch("requests.get", side_effect=requests.ConnectionError()):
            self.assertEqual(provider.list_models(), ["saved-model"])

    def test_chat_uses_account_key_and_correct_endpoint(self):
        provider = WusRouterProvider("test-key")
        response = Mock(status_code=200)
        response.json.return_value = {"choices": [{"message": {"content": "hello"}}]}
        with patch("requests.post", return_value=response) as post:
            self.assertEqual(provider.chat("model", [{"role": "user", "content": "hi"}]), "hello")
        self.assertEqual(post.call_args.args[0], "https://wusrouter.com/v1/chat/completions")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")
