"""Offline tests for the Gemini account lane."""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from codelaboon import gemini_auth as auth
from providers.gemini.gemini_provider import GeminiProvider


class GeminiProviderTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_api_key_discovery_filters_non_chat_models(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "models": [
                {
                    "name": "models/gemini-4-argon",
                    "displayName": "Gemini 4 Argon",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {"name": "models/text-embedding-004"},
                {"name": "models/imagen-4"},
            ]
        }
        provider = GeminiProvider("key", models=[])
        with patch("requests.get", return_value=response) as request:
            self.assertEqual(provider.list_models(), ["gemini-4-argon"])
        self.assertEqual(provider.model_names["gemini-4-argon"], "Gemini 4 Argon")
        self.assertEqual(request.call_args.kwargs["headers"]["x-goog-api-key"], "key")

    def test_oauth_discovery_uses_cloud_code_and_falls_back(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "models": {
                "gemini-4-argon": {"displayName": "Gemini 4 Argon"},
                "gemini-3.8-flash": {"displayName": "Gemini 3.8 Flash"},
                "imagen-4": {"displayName": "Imagen 4"},
            }
        }
        provider = GeminiProvider("", models=["pinned"])
        with (
            patch.object(provider, "validate_api_key", return_value=True),
            patch.object(provider, "_credential", return_value=("token", "oauth")),
            patch("codelaboon.gemini_auth.project_id", return_value="project-1"),
            patch("requests.post", return_value=response) as request,
        ):
            self.assertEqual(
                provider.list_models(), ["gemini-4-argon", "gemini-3.8-flash"]
            )
        self.assertTrue(request.call_args.args[0].endswith(":fetchAvailableModels"))
        self.assertEqual(request.call_args.kwargs["json"], {"project": "project-1"})

    def test_oauth_discovery_failure_returns_pinned_roster(self):
        provider = GeminiProvider("", models=["pinned"])
        with (
            patch.object(provider, "validate_api_key", return_value=True),
            patch.object(provider, "_credential", return_value=("token", "oauth")),
            patch("codelaboon.gemini_auth.project_id", return_value=""),
            patch("requests.post") as request,
        ):
            self.assertEqual(provider.list_models(), ["pinned"])
            request.assert_not_called()

    def test_pending_onboarding_still_shows_the_fallback_roster(self):
        provider = GeminiProvider("", models=["pinned"])
        with (
            patch.object(provider, "validate_api_key", return_value=True),
            patch.object(provider, "_credential", return_value=("token", "oauth")),
            patch(
                "codelaboon.gemini_auth.project_id",
                side_effect=ValueError("onboarding pending"),
            ),
        ):
            self.assertEqual(provider.list_models(), ["pinned"])

    def test_api_key_chat_builds_generate_content_request(self):
        payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "ignored", "thought": True},
                            {"text": "hello "},
                            {"text": "back"},
                        ]
                    }
                }
            ]
        }
        response = Mock(status_code=200)
        response.json.return_value = payload
        provider = GeminiProvider("key", models=[])
        with patch("requests.post", return_value=response) as request:
            answer = provider.chat(
                "gemini-4-argon",
                [
                    {"role": "system", "content": "Be brief."},
                    {"role": "user", "content": "hi"},
                ],
                max_tokens=64,
                temperature=0.2,
            )
        self.assertEqual(answer, "hello back")
        self.assertTrue(
            request.call_args.args[0].endswith(
                "/models/gemini-4-argon:generateContent"
            )
        )
        body = request.call_args.kwargs["json"]
        self.assertEqual(body["systemInstruction"]["parts"][0]["text"], "Be brief.")
        self.assertEqual(
            body["contents"], [{"role": "user", "parts": [{"text": "hi"}]}]
        )
        self.assertEqual(body["generationConfig"]["maxOutputTokens"], 64)

    def test_oauth_chat_uses_cloud_code_envelope(self):
        payload = {
            "response": {
                "candidates": [{"content": {"parts": [{"text": "free reply"}]}}]
            }
        }
        response = Mock(status_code=200)
        response.json.return_value = payload
        provider = GeminiProvider("", models=[])
        with (
            patch.object(provider, "validate_api_key", return_value=True),
            patch.object(provider, "_credential", return_value=("token", "oauth")),
            patch("codelaboon.gemini_auth.project_id", return_value="project-9"),
            patch("codelaboon.gemini_auth.user_agent", return_value="ua"),
            patch("requests.post", return_value=response) as request,
        ):
            answer = provider.chat(
                "gemini-3.8-flash", [{"role": "user", "content": "hi"}]
            )
        self.assertEqual(answer, "free reply")
        body = request.call_args.kwargs["json"]
        self.assertEqual(body["model"], "gemini-3.8-flash")
        self.assertEqual(body["project"], "project-9")
        self.assertIn("contents", body["request"])
        self.assertEqual(
            request.call_args.kwargs["headers"]["Authorization"], "Bearer token"
        )

    def test_oauth_tokens_never_go_to_custom_endpoint(self):
        provider = GeminiProvider("", base_url="https://example.com/v1beta")
        with patch.object(auth, "access_token") as token:
            with self.assertRaises(ValueError):
                provider._credential()
            token.assert_not_called()

    def test_blocked_prompt_is_reported(self):
        payload = {"promptFeedback": {"blockReason": "SAFETY"}}
        response = Mock(status_code=200)
        response.json.return_value = payload
        provider = GeminiProvider("key", models=[])
        with patch("requests.post", return_value=response):
            with self.assertRaisesRegex(ValueError, "SAFETY"):
                provider.chat("gemini-4-argon", [{"role": "user", "content": "hi"}])

    def test_free_tier_rejection_is_explained(self):
        provider = GeminiProvider("key", models=[])
        with patch("requests.post", return_value=Mock(status_code=403)):
            with self.assertRaisesRegex(ValueError, "free tier is limited"):
                provider.chat(
                    "gemini-4-argon", [{"role": "user", "content": "hi"}]
                )


class GeminiAuthTests(unittest.TestCase):
    def test_oauth_client_is_read_from_env_and_saved_privately(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(
                os.environ,
                {
                    "CODELABOON_CONFIG_DIR": root,
                    "CODELABOON_GEMINI_CLIENT_ID": "env-id",
                    "CODELABOON_GEMINI_CLIENT_SECRET": "env-secret",
                },
            ):
                self.assertEqual(auth.client(), ("env-id", "env-secret"))

            with patch.dict(
                os.environ,
                {"CODELABOON_CONFIG_DIR": root},
                clear=True,
            ):
                auth.save_oauth_client(" saved-id ", " saved-secret ")
                self.assertEqual(auth.client(), ("saved-id", "saved-secret"))
                mode = os.stat(
                    os.path.join(root, "gemini-oauth.json")
                ).st_mode
                self.assertEqual(mode & 0o777, 0o600)

    def test_oauth_client_import_accepts_google_download_shape(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "client.json")
            with open(source, "w", encoding="utf-8") as stream:
                stream.write(
                    '{"installed":{"client_id":"file-id",'
                    '"client_secret":"file-secret"}}'
                )
            with patch.dict(
                os.environ,
                {"CODELABOON_CONFIG_DIR": os.path.join(root, "config")},
                clear=True,
            ):
                self.assertEqual(
                    auth.import_oauth_client(source),
                    ("file-id", "file-secret"),
                )
                self.assertEqual(auth.client(), ("file-id", "file-secret"))

    def test_missing_oauth_client_explains_the_setup(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(
                os.environ,
                {"CODELABOON_CONFIG_DIR": root},
                clear=True,
            ):
                with self.assertRaisesRegex(ValueError, "configure gemini"):
                    auth.client()

    def test_onboarding_polls_until_the_project_is_ready(self):
        pending = Mock(status_code=200)
        pending.json.return_value = {"done": False}
        ready = Mock(status_code=200)
        ready.json.return_value = {
            "done": True,
            "response": {"cloudaicompanionProject": "free-project"},
        }
        with (
            patch("requests.post", side_effect=[pending, ready]) as request,
            patch("time.sleep"),
        ):
            self.assertEqual(auth._onboard("token", "free-tier"), "free-project")
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args.kwargs["json"]["tier_id"], "free-tier")

    def test_default_tier_prefers_the_provider_default(self):
        load = {
            "allowedTiers": [
                {"id": "legacy-tier"},
                {"id": "free-tier", "isDefault": True},
            ]
        }
        self.assertEqual(auth._default_tier(load), "free-tier")
        self.assertEqual(auth._default_tier({}), "free-tier")

    def test_refresh_rotates_token_but_keeps_refresh_token(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"CODELABOON_CONFIG_DIR": root}):
                auth.save_record(
                    "gemini-session.json",
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
                with (
                    patch.object(auth, "client", return_value=("id", "secret")),
                    patch("requests.post", return_value=response),
                ):
                    self.assertEqual(auth.access_token(), "new")
                self.assertEqual(auth.read_session()["refresh_token"], "refresh")

    def test_project_id_is_read_without_onboarding(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"CODELABOON_CONFIG_DIR": root}):
                auth.save_record(
                    "gemini-session.json",
                    {
                        "access_token": "token",
                        "refresh_token": "refresh",
                        "expires_at": 9999999999,
                        "project_id": "saved-project",
                    },
                )
                with patch.object(auth, "fetch_project") as onboard:
                    self.assertEqual(auth.project_id(), "saved-project")
                    onboard.assert_not_called()

    def test_session_file_is_private(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"CODELABOON_CONFIG_DIR": root}):
                auth.save_record(
                    "gemini-session.json",
                    {"access_token": "token", "refresh_token": "refresh"},
                )
                mode = os.stat(os.path.join(root, "gemini-session.json")).st_mode
                self.assertEqual(mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
