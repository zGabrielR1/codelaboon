"""Offline tests for the Freebuff account lane."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from codelaboon import freebuff_auth as auth
from providers.freebuff.freebuff_provider import (
    DEFAULT_BASE_URL,
    DEFAULT_MODELS,
    FreebuffProvider,
)


def _response(status_code, payload=None, text=""):
    response = Mock(status_code=status_code)
    response.text = text
    if payload is None and text:
        response.json.side_effect = ValueError("not json")
    else:
        response.json.return_value = payload
    return response


def _admission(status="active", message=None, instance_id=None):
    payload = {"status": status}
    if message:
        payload["message"] = message
    if instance_id:
        payload["instanceId"] = instance_id
    return _response(200, payload)


def _completion(text="hello back"):
    return _response(
        200,
        {"choices": [{"message": {"content": text}, "finish_reason": "stop"}]},
    )


class FreebuffProviderTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_compiled_catalog_is_the_offline_fallback(self):
        provider = FreebuffProvider("", models=[])
        with patch.object(provider, "validate_api_key", return_value=True):
            self.assertEqual(provider.list_models(), DEFAULT_MODELS)
        self.assertEqual(
            provider.model_names["mimo/mimo-v2.5"], "MiMo v2.6 Flash Fast"
        )

    def test_configured_roster_takes_precedence(self):
        provider = FreebuffProvider("", models=["pinned"])
        with patch.object(provider, "validate_api_key", return_value=True):
            self.assertEqual(provider.list_models(), ["pinned"])

    def test_no_credential_lists_nothing(self):
        provider = FreebuffProvider("", models=[])
        self.assertEqual(provider.list_models(), [])

    def test_chat_admits_then_completes_with_free_metadata(self):
        provider = FreebuffProvider("", models=[])
        with (
            patch.object(provider, "validate_api_key", return_value=True),
            patch.object(provider, "_credential", return_value=("token", "account")),
            patch("requests.post", side_effect=[_admission(), _completion()]) as request,
        ):
            answer = provider.chat(
                "mimo/mimo-v2.5",
                [{"role": "user", "content": "hi"}],
                max_tokens=64,
                temperature=0.2,
            )
        self.assertEqual(answer, "hello back")
        self.assertEqual(request.call_count, 2)
        admission, completion = request.call_args_list
        self.assertTrue(
            admission.args[0].endswith("/api/v1/freebuff/session/admission")
        )
        admit_headers = admission.kwargs["headers"]
        self.assertEqual(admit_headers["Authorization"], "Bearer token")
        self.assertTrue(admit_headers["x-freebuff-instance-id"].startswith("cli:"))
        self.assertEqual(admit_headers["x-freebuff-model"], "mimo/mimo-v2.5")
        self.assertEqual(
            admit_headers["x-freebuff-wallet-spend-limit"], "session"
        )
        self.assertTrue(
            completion.args[0].endswith("/api/v1/chat/completions")
        )
        body = completion.kwargs["json"]
        self.assertEqual(body["model"], "mimo/mimo-v2.5")
        self.assertEqual(body["stream"], False)
        metadata = body["codebuff_metadata"]
        self.assertEqual(metadata["cost_mode"], "free")
        self.assertTrue(metadata["freebuff_instance_id"].startswith("cli:"))
        self.assertEqual(metadata["surface"], "cli")
        self.assertTrue(metadata["run_id"])
        self.assertTrue(metadata["client_id"])

    def test_second_chat_reuses_the_live_slot(self):
        provider = FreebuffProvider("", models=[])
        with (
            patch.object(provider, "validate_api_key", return_value=True),
            patch.object(provider, "_credential", return_value=("token", "account")),
            patch(
                "requests.post",
                side_effect=[
                    _admission(),
                    _completion("one"),
                    _completion("two"),
                ],
            ) as request,
        ):
            provider.chat("mimo/mimo-v2.5", [{"role": "user", "content": "a"}])
            provider.chat("mimo/mimo-v2.5", [{"role": "user", "content": "b"}])
        self.assertEqual(request.call_count, 3)

    def test_expired_slot_re_admits_and_retries_once(self):
        provider = FreebuffProvider("", models=[])
        gone = _response(410, {"error": "session_expired", "statusCode": 410})
        with (
            patch.object(provider, "validate_api_key", return_value=True),
            patch.object(provider, "_credential", return_value=("token", "account")),
            patch(
                "requests.post",
                side_effect=[
                    _admission(),
                    gone,
                    _admission(),
                    _completion("recovered"),
                ],
            ) as request,
        ):
            answer = provider.chat(
                "mimo/mimo-v2.5", [{"role": "user", "content": "hi"}]
            )
        self.assertEqual(answer, "recovered")
        self.assertEqual(request.call_count, 4)

    def test_country_blocked_is_explained(self):
        provider = FreebuffProvider("", models=[])
        with (
            patch.object(provider, "validate_api_key", return_value=True),
            patch.object(provider, "_credential", return_value=("token", "account")),
            patch(
                "requests.post",
                return_value=_admission(
                    "country_blocked", "Blocked in your country"
                ),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "Blocked in your country"):
                provider.chat("mimo/mimo-v2.5", [{"role": "user", "content": "hi"}])

    def test_account_tokens_never_go_to_custom_endpoint(self):
        provider = FreebuffProvider("", base_url="https://example.com")
        with patch.object(auth, "access_token") as token:
            with self.assertRaises(ValueError):
                provider._credential()
            token.assert_not_called()

    def test_grace_window_completion_still_flows(self):
        payload = _response(
            200, {"status": "ended", "instanceId": "cli:live"}
        )
        provider = FreebuffProvider("", models=[])
        with (
            patch.object(provider, "validate_api_key", return_value=True),
            patch.object(provider, "_credential", return_value=("token", "account")),
            patch(
                "requests.post",
                side_effect=[payload, _completion("grace")],
            ),
        ):
            self.assertEqual(
                provider.chat(
                    "mimo/mimo-v2.5", [{"role": "user", "content": "hi"}]
                ),
                "grace",
            )

    def test_waiting_room_is_explained(self):
        provider = FreebuffProvider("", models=[])
        with (
            patch.object(provider, "validate_api_key", return_value=True),
            patch.object(provider, "_credential", return_value=("token", "account")),
            patch(
                "requests.post",
                side_effect=[
                    _admission(),
                    _response(
                        428,
                        {"error": "waiting_room_required", "statusCode": 428},
                    ),
                ],
            ),
        ):
            with self.assertRaisesRegex(ValueError, "waiting room"):
                provider.chat("mimo/mimo-v2.5", [{"role": "user", "content": "hi"}])


class FreebuffAuthTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_fingerprint_is_stable_per_install(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(
                os.environ, {"CODELABOON_CONFIG_DIR": root}, clear=True
            ):
                first = auth.fingerprint_id()
                self.assertTrue(first.startswith("codebuff-cli-"))
                self.assertEqual(auth.fingerprint_id(), first)
                mode = os.stat(
                    os.path.join(root, "freebuff-fingerprint.json")
                ).st_mode
                self.assertEqual(mode & 0o777, 0o600)

    def test_token_precedence_session_then_env(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(
                os.environ, {"CODELABOON_CONFIG_DIR": root}, clear=True
            ):
                auth.save_record(
                    "freebuff-session.json", {"authToken": "session-token"}
                )
                with patch.dict(os.environ, {"CODEBUFF_API_KEY": "env-token"}):
                    self.assertEqual(auth.token(), "session-token")
            with patch.dict(
                os.environ, {"CODELABOON_CONFIG_DIR": root}, clear=True
            ):
                auth.clear_session()
                with patch.dict(os.environ, {"CODEBUFF_API_KEY": "env-token"}):
                    self.assertEqual(auth.token(), "env-token")
                self.assertEqual(auth.token(), "")

    def test_manicode_credentials_are_honored(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as root:
            credentials = Path(home) / ".config" / "manicode" / "credentials.json"
            credentials.parent.mkdir(parents=True)
            credentials.write_text(
                json.dumps({"default": {"authToken": "cli-token"}}),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"CODELABOON_CONFIG_DIR": root, "HOME": home},
                clear=True,
            ):
                self.assertEqual(auth.token(), "cli-token")

    def test_login_code_url_flow_saves_the_session(self):
        code = _response(
            200,
            {
                "loginUrl": "https://freebuff.com/login?auth_code=abc",
                "fingerprintHash": "hash",
                "expiresAt": 1793926598052,
            },
        )
        status = _response(
            200,
            {
                "user": {
                    "id": "u1",
                    "name": "Test",
                    "email": "t@example.com",
                    "authToken": "login-token",
                }
            },
        )
        with tempfile.TemporaryDirectory() as root:
            with (
                patch.dict(
                    os.environ, {"CODELABOON_CONFIG_DIR": root}, clear=True
                ),
                patch("requests.post", return_value=code) as code_request,
                patch("requests.get", return_value=status) as status_request,
                patch("webbrowser.open", return_value=True),
            ):
                auth.login(report=lambda message: None)
                self.assertEqual(code_request.call_args.kwargs["json"]["fingerprintId"], auth.fingerprint_id())
                self.assertTrue(status_request.called)
                self.assertEqual(auth.token(), "login-token")
                mode = os.stat(
                    os.path.join(root, "freebuff-session.json")
                ).st_mode
                self.assertEqual(mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
