"""Offline tests for the Claude.ai browser provider."""

import json
import os
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import requests

from codelaboon.web import create_server
from providers.claude import browser_provider


class ClaudeBrowserProviderTests(unittest.TestCase):
    def setUp(self):
        self.config = tempfile.TemporaryDirectory()
        self.addCleanup(self.config.cleanup)
        environment = patch.dict(os.environ, {"CODELABOON_CONFIG_DIR": self.config.name})
        environment.start()
        self.addCleanup(environment.stop)
        self.provider = browser_provider.ClaudeBrowserProvider("")

    def enable(self):
        browser_provider.profile_marker().parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        browser_provider.profile_marker().touch(mode=0o600)

    def test_provider_stays_hidden_until_setup(self):
        self.assertFalse(self.provider.validate_api_key())
        self.assertEqual(self.provider.list_models(), [])
        with self.assertRaisesRegex(ValueError, "claude-browser setup"):
            self.provider.chat(browser_provider.MODEL, [{"role": "user", "content": "hi"}])

    def test_setup_writes_marker_and_opens_claude(self):
        with (
            patch.object(browser_provider.webbrowser, "open", return_value=True) as browser,
            patch("builtins.print") as output,
        ):
            browser_provider.setup()
        self.assertTrue(browser_provider.profile_marker().is_file())
        browser.assert_called_once_with("https://claude.ai/new", new=2)
        self.assertTrue(any("manifest" in call.args[0] for call in output.call_args_list))

    def test_chat_sends_one_text_prompt_in_the_background(self):
        self.enable()
        with patch.object(browser_provider, "chat", return_value="hello back") as chat:
            reply = self.provider.chat(
                browser_provider.MODEL,
                [
                    {"role": "system", "content": "Be brief."},
                    {"role": "user", "content": "hi"},
                ],
                background=True,
            )
        self.assertEqual(reply, "hello back")
        self.assertEqual(chat.call_args.args[0], "system:\nBe brief.\n\nuser:\nhi")
        self.assertEqual(chat.call_args.kwargs, {"background": True})

    def test_web_setup_and_test_use_the_shared_provider(self):
        with create_server(0, Mock(providers={"claude_browser": self.provider})) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}"
                token = requests.get(url + "/api/session", timeout=5).json()["token"]
                headers = {"X-Codelaboon-Token": token}
                setup = url + "/api/claude-browser/setup"
                test = url + "/api/claude-browser/test"
                self.assertEqual(requests.post(setup, timeout=5).status_code, 403)
                self.assertEqual(requests.post(test, headers=headers, timeout=5).status_code, 400)
                result = requests.post(setup, headers=headers, timeout=5)
                self.assertEqual(result.json(), {"manifest": str(browser_provider.extension_manifest())})
                self.assertTrue(self.provider.validate_api_key())
                connections = requests.get(url + "/api/connections", headers=headers, timeout=5).json()
                self.assertEqual(connections["claude_browser"], {"enabled": True})
                with patch.object(browser_provider, "chat", return_value="Verified") as chat:
                    self.assertEqual(requests.post(test, headers=headers, timeout=5).json(), {"connected": True})
                    self.assertIn("Codelaboon browser bridge works", chat.call_args.args[0])
            finally:
                server.shutdown()
                thread.join()

    def test_chat_rejects_tools_and_non_text_content(self):
        self.enable()
        with self.assertRaisesRegex(ValueError, "text only"):
            self.provider.chat(
                browser_provider.MODEL,
                [{"role": "user", "content": "hi"}],
                tools=[{"type": "function"}],
            )
        with self.assertRaisesRegex(ValueError, "text messages only"):
            self.provider.chat(
                browser_provider.MODEL,
                [{"role": "user", "content": [{"type": "image"}]}],
            )

    def test_engine_response_returns_chat_completion(self):
        self.enable()
        with patch.object(browser_provider, "chat", return_value="engine reply"):
            response = self.provider.engine_response(
                browser_provider.MODEL,
                {"model": "claude_browser/web-default",
                 "messages": [{"role": "user", "content": "hi"}]},
            )
        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["model"], "claude_browser/web-default")
        self.assertEqual(payload["choices"][0]["message"]["content"], "engine reply")

    def test_engine_response_streams_text(self):
        self.enable()
        with patch.object(browser_provider, "chat", return_value="streamed"):
            response = self.provider.engine_response(
                browser_provider.MODEL,
                {"model": "claude_browser/web-default", "stream": True,
                 "messages": [{"role": "user", "content": "hi"}]},
            )
        wire = response.content.decode()
        self.assertTrue(wire.endswith("data: [DONE]\n\n"))
        self.assertIn('"content": "streamed"', wire)

    def test_engine_response_rejects_tool_history(self):
        self.enable()
        with self.assertRaisesRegex(ValueError, "new text conversation"):
            self.provider.engine_response(
                browser_provider.MODEL,
                {"model": "claude_browser/web-default",
                 "messages": [
                     {"role": "assistant", "content": "", "tool_calls": [{"id": "call"}]},
                     {"role": "tool", "content": "result"},
                 ]},
            )


if __name__ == "__main__":
    unittest.main()
