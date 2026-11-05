"""Offline tests for the Claude account lane."""

import base64
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from codelaboon import claude_auth as auth
from providers.claude.claude_provider import (
    CLAUDE_CODE_USER_AGENT,
    OAUTH_BETA,
    ClaudeProvider,
)


class ClaudeProviderTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_api_key_discovery_uses_messages_catalogue(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "data": [
                {"id": "claude-sonnet-5-5", "display_name": "Claude Sonnet 5.5"},
                {"id": "claude-opus-5-5", "display_name": "Claude Opus 5.5"},
            ]
        }
        provider = ClaudeProvider("key", models=[])
        with patch("requests.get", return_value=response) as request:
            self.assertEqual(
                provider.list_models(),
                ["claude-sonnet-5-5", "claude-opus-5-5"],
            )
        self.assertEqual(provider.model_names["claude-sonnet-5-5"], "Claude Sonnet 5.5")
        self.assertEqual(request.call_args.kwargs["headers"]["x-api-key"], "key")

    def test_oauth_discovery_falls_back_to_pinned_roster(self):
        provider = ClaudeProvider("", models=["claude-sonnet-5-5"])
        response = Mock(status_code=403)
        with (
            patch.object(provider, "validate_api_key", return_value=True),
            patch.object(provider, "_credential", return_value=("token", "oauth")),
            patch("requests.get", return_value=response),
        ):
            self.assertEqual(provider.list_models(), ["claude-sonnet-5-5"])

    def test_oauth_chat_uses_bearer_and_claude_code_headers(self):
        payload = {
            "content": [
                {"type": "thinking", "thinking": "internal"},
                {"type": "text", "text": "hello back"},
            ]
        }
        response = Mock(status_code=200)
        response.json.return_value = payload
        provider = ClaudeProvider("")
        with (
            patch.object(provider, "validate_api_key", return_value=True),
            patch.object(provider, "_credential", return_value=("token", "oauth")),
            patch("requests.post", return_value=response) as request,
        ):
            answer = provider.chat(
                "claude-sonnet-5-5",
                [
                    {"role": "system", "content": "Be brief."},
                    {"role": "user", "content": "hi"},
                ],
            )
        self.assertEqual(answer, "hello back")
        headers = request.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer token")
        self.assertEqual(headers["anthropic-beta"], OAUTH_BETA)
        self.assertEqual(headers["user-agent"], CLAUDE_CODE_USER_AGENT)
        self.assertEqual(headers["x-app"], "cli")
        self.assertEqual(request.call_args.kwargs["json"]["system"], "Be brief.")

    def test_oauth_tokens_never_go_to_custom_endpoint(self):
        provider = ClaudeProvider("", base_url="https://example.com/v1")
        with patch.object(auth, "access_token") as token:
            with self.assertRaises(ValueError):
                provider._credential()
            token.assert_not_called()

    def test_free_plan_rejection_is_explained(self):
        provider = ClaudeProvider("key")
        with patch("requests.post", return_value=Mock(status_code=403)):
            with self.assertRaisesRegex(ValueError, "free plan does not"):
                provider.chat(
                    "claude-sonnet-5-5",
                    [{"role": "user", "content": "hi"}],
                )


class ClaudeAuthTests(unittest.TestCase):
    def test_pkce_challenge_matches_verifier(self):
        verifier, challenge = auth._pkce()
        expected = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        self.assertEqual(challenge, expected)
        self.assertGreaterEqual(len(verifier), 43)

    def test_refresh_rotates_token_but_keeps_refresh_token(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"CODELABOON_CONFIG_DIR": root}):
                auth.save_record(
                    "claude-session.json",
                    {
                        "access_token": "old",
                        "refresh_token": "refresh",
                        "expires_at": 0,
                    },
                )
                response = Mock(status_code=200)
                response.json.return_value = {
                    "access_token": "new",
                    "expires_in": 3600,
                }
                with patch("requests.post", return_value=response):
                    self.assertEqual(auth.access_token(), "new")
                self.assertEqual(auth.read_session()["refresh_token"], "refresh")

    def test_session_file_is_private(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"CODELABOON_CONFIG_DIR": root}):
                auth.save_record(
                    "claude-session.json",
                    {"access_token": "token", "refresh_token": "refresh"},
                )
                path = os.path.join(root, "claude-session.json")
                mode = os.stat(path).st_mode & 0o777
                self.assertEqual(mode, 0o600)
                self.assertEqual(
                    json.loads(Path(path).read_text(encoding="utf-8"))["access_token"],
                    "token",
                )


if __name__ == "__main__":
    unittest.main()
