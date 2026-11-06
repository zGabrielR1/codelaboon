"""Offline tests for the Qoder account lane."""

import json
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from codelaboon import qoder_auth as auth
from providers.qoder.qoder_provider import DEFAULT_MODELS, QoderProvider


def _response(status_code, payload=None):
    response = Mock(status_code=status_code)
    response.json.return_value = payload
    return response


def _completed(stdout="", stderr="", returncode=0):
    completed = Mock(returncode=returncode)
    completed.stdout = stdout
    completed.stderr = stderr
    return completed


class QoderProviderTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_tier_catalogue_is_the_offline_fallback(self):
        provider = QoderProvider("", models=[])
        with (
            patch.object(provider, "validate_api_key", return_value=True),
            patch("providers.qoder.qoder_provider._binary", return_value=None),
        ):
            self.assertEqual(provider.list_models(), DEFAULT_MODELS)
            self.assertEqual(provider.model_names["auto"], "Smart Routing (Auto)")

    def test_configured_roster_takes_precedence(self):
        provider = QoderProvider("", models=["pinned"])
        with patch.object(provider, "validate_api_key", return_value=True):
            self.assertEqual(provider.list_models(), ["pinned"])

    def test_no_credential_lists_nothing(self):
        provider = QoderProvider("", models=[])
        self.assertEqual(provider.list_models(), [])

    def test_pat_from_env_counts_as_configured(self):
        with patch.dict(os.environ, {"QODER_PERSONAL_ACCESS_TOKEN": "pat-1"}):
            provider = QoderProvider("", models=[])
            self.assertTrue(provider.validate_api_key())
            self.assertEqual(provider._pat(), "pat-1")

    def test_chat_runs_tool_free_print_mode(self):
        provider = QoderProvider("", models=[])
        with (
            patch.object(provider, "validate_api_key", return_value=True),
            patch(
                "providers.qoder.qoder_provider._binary",
                return_value="/usr/local/bin/qodercli",
            ),
            patch(
                "subprocess.run",
                return_value=_completed("hello back\n"),
            ) as run,
        ):
            answer = provider.chat(
                "auto",
                [
                    {"role": "system", "content": "be brief"},
                    {"role": "user", "content": "hi"},
                ],
            )
        self.assertEqual(answer, "hello back")
        command = run.call_args.args[0]
        self.assertEqual(
            command[:5], ["/usr/local/bin/qodercli", "-p", "--model", "auto", "--tools"]
        )
        self.assertIn("User: hi", command[-1])
        self.assertIn("System: be brief", command[-1])

    def test_chat_without_binary_explains_the_install(self):
        provider = QoderProvider("", models=[])
        with (
            patch.object(provider, "validate_api_key", return_value=True),
            patch("providers.qoder.qoder_provider._binary", return_value=None),
        ):
            with self.assertRaisesRegex(ValueError, "qodercli binary"):
                provider.chat("auto", [{"role": "user", "content": "hi"}])

    def test_chat_surfaces_cli_errors(self):
        provider = QoderProvider("", models=[])
        with (
            patch.object(provider, "validate_api_key", return_value=True),
            patch(
                "providers.qoder.qoder_provider._binary",
                return_value="/usr/local/bin/qodercli",
            ),
            patch(
                "subprocess.run",
                return_value=_completed("", "not signed in", returncode=1),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "not signed in"):
                provider.chat("auto", [{"role": "user", "content": "hi"}])


class QoderAuthTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_machine_id_is_stable_per_install(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(
                os.environ, {"CODELABOON_CONFIG_DIR": root}, clear=True
            ):
                first = auth.machine_id()
                self.assertEqual(auth.machine_id(), first)
                mode = os.stat(os.path.join(root, "qoder-machine.json")).st_mode
                self.assertEqual(mode & 0o777, 0o600)

    def test_pkce_challenge_matches_verifier(self):
        import base64
        import hashlib

        verifier, challenge = auth._pkce()
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        self.assertEqual(challenge, expected)
        self.assertGreaterEqual(len(verifier), 43)

    def test_token_comes_from_the_saved_session(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(
                os.environ, {"CODELABOON_CONFIG_DIR": root}, clear=True
            ):
                self.assertEqual(auth.token(), "")
                auth.save_record(
                    "qoder-session.json", {"access_token": "session-token"}
                )
                self.assertEqual(auth.token(), "session-token")

    def test_refresh_exchanges_the_refresh_token(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(
                os.environ, {"CODELABOON_CONFIG_DIR": root}, clear=True
            ):
                auth.save_record(
                    "qoder-session.json",
                    {
                        "access_token": "old",
                        "refresh_token": "refresh-1",
                        "expires_at": 1,
                        "user_name": "Test",
                    },
                )
                fresh = _response(
                    200,
                    {
                        "device_token": "fresh-token",
                        "refresh_token": "refresh-2",
                        "expires_in": 3600,
                    },
                )
                with patch("requests.post", return_value=fresh) as post:
                    self.assertEqual(auth.access_token(), "fresh-token")
                body = post.call_args.kwargs["json"]
                self.assertEqual(body["refresh_token"], "refresh-1")
                self.assertTrue(body["machine_id"])
                session = auth.read_session()
                self.assertEqual(session["access_token"], "fresh-token")
                self.assertEqual(session["user_name"], "Test")

    def test_login_device_flow_saves_the_session(self):
        pending = _response(404, {})
        done = _response(
            200,
            {
                "token": "login-token",
                "refresh_token": "refresh-1",
                "user_id": "u1",
                "user_name": "Test",
                "expires_in": 3600,
            },
        )
        with tempfile.TemporaryDirectory() as root:
            with (
                patch.dict(
                    os.environ, {"CODELABOON_CONFIG_DIR": root}, clear=True
                ),
                patch(
                    "requests.get",
                    side_effect=[pending, done],
                ) as get,
                patch("webbrowser.open", return_value=True),
            ):
                auth.login(report=lambda message: None)
                # First poll is pending (404), second delivers the token.
                self.assertEqual(get.call_count, 2)
                self.assertEqual(auth.token(), "login-token")
                mode = os.stat(os.path.join(root, "qoder-session.json")).st_mode
                self.assertEqual(mode & 0o777, 0o600)
                session = json.loads(
                    Path(root, "qoder-session.json").read_text(encoding="utf-8")
                )
                self.assertEqual(session["user_name"], "Test")

    def test_client_id_is_the_official_prod_id(self):
        self.assertEqual(
            auth.client_id(), "e883ade2-e6e3-4d6d-adf7-f92ceff5fdcb"
        )


class QoderAlertTests(unittest.TestCase):
    def test_limitation_alert_is_shown_on_all_surfaces(self):
        from codelaboon.cli import CodelaboonCLI

        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            CodelaboonCLI._qoder_alert()
        self.assertIn("Qoder limitation", buffer.getvalue())
        self.assertIn("qodercli", buffer.getvalue())

        static = Path(__file__).resolve().parent.parent / "codelaboon" / "static"
        self.assertIn("Qoder limitation", (static / "index.html").read_text(encoding="utf-8"))
        self.assertIn("qoder-alert", (static / "app.js").read_text(encoding="utf-8"))
        self.assertIn("#qoder-alert", (static / "style.css").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
