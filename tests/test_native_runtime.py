"""Tool-wire integrity, routing boundaries, packaging and install regressions."""
import io
import json
import os
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import xml.etree.ElementTree as ET

import requests

from codelaboon.autostart import specification
from codelaboon.native_gateway import Gateway, serve
from codelaboon.native_tui import opencode_config, omp_config
from providers.compatible import LocalProvider, OpenRouterFreeProvider


class Provider:
    api_key = "provider-secret"
    base_url = "https://provider.example/v1"
    models = ["kilo-auto/free"]
    def validate_api_key(self):
        return True
    def list_models(self):
        return self.models


class GatewayTests(unittest.TestCase):
    def test_tool_messages_and_sse_pass_through_without_text_conversion(self):
        body = {"model": "kilo/tool-model", "stream": True,
                "messages": [{"role": "assistant", "tool_calls": [{"id": "call-1", "type": "function",
                    "function": {"name": "read", "arguments": '{"path":"a.py"}'}}]},
                    {"role": "tool", "tool_call_id": "call-1", "content": "source"}],
                "tools": [{"type": "function", "function": {"name": "read", "parameters": {"type": "object"}}}]}
        wire = b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{}"}}]}}]}\n\ndata: [DONE]\n\n'
        response = MagicMock(status_code=200)
        response.headers = {"Content-Type": "text/event-stream"}
        response.iter_content.return_value = iter([wire[:20], wire[20:]])
        with serve({"kilo": Provider()}) as (gateway, url), patch("codelaboon.native_gateway.requests.post", return_value=response) as post:
            # Use a Session so mocking the upstream requests.post does not mock the client.
            client = requests.Session()
            client.trust_env = False
            denied = client.post(url + "/chat/completions", json=body)
            self.assertEqual(denied.status_code, 401)
            post.assert_not_called()
            answer = client.post(url + "/chat/completions", json=body,
                                 headers={"Authorization": "Bearer " + gateway.token})
            self.assertEqual(answer.content, wire)
            sent = post.call_args.kwargs
            self.assertEqual(sent["json"], dict(body, model="tool-model"))
            self.assertEqual(sent["headers"]["authorization"], "Bearer provider-secret")
            self.assertNotEqual(gateway.token, "provider-secret")
            response.close.assert_called_once()

    def test_free_failover_moves_to_another_provider_before_replaying_a_turn(self):
        one, two = Provider(), Provider()
        one.models = ["deepseek-v4.1-flash-free"]
        two.models = ["kilo-auto/free"]
        gateway = Gateway({"ourfree": one, "kilo": two})
        limited, answer = MagicMock(status_code=429), MagicMock(status_code=200)
        with patch("codelaboon.native_gateway.requests.post", side_effect=[limited, answer]) as post:
            self.assertIs(gateway.request({"model": "free", "messages": []}, "chat"), answer)
        self.assertEqual([call.kwargs["json"]["model"] for call in post.call_args_list],
                         ["deepseek-v4.1-flash-free", "kilo-auto/free"])
        limited.close.assert_called_once()
        self.assertIn("ourfree", gateway.cooldowns)

    def test_responses_keeps_tool_inputs_and_disables_storage(self):
        provider = Provider()
        provider.base_url = "https://api.openai.com/v1"
        provider._credential = lambda: ("account-token", True)
        body = {"model": "chatgpt/current", "input": [{"type": "function_call_output", "call_id": "c", "output": "ok"}], "store": True}
        with patch("codelaboon.native_gateway.requests.post", return_value=MagicMock(status_code=200)) as post:
            Gateway({"chatgpt": provider}).request(body, "responses")
        self.assertFalse(post.call_args.kwargs["json"]["store"])
        self.assertEqual(post.call_args.kwargs["json"]["input"], body["input"])

    def test_free_provider_rejects_explicit_paid_model(self):
        gateway = Gateway({"openrouter_free": OpenRouterFreeProvider("key")})
        with self.assertRaisesRegex(ValueError, "does not allow"):
            gateway.routes("openrouter_free/vendor/paid")

    def test_models_expose_free_lanes_and_local_models_individually(self):
        provider = Provider()
        provider.models = ["my-local-model"]
        rows = Gateway({"local": provider, "kilo": Provider()}).models()
        self.assertEqual({row["id"] for row in rows}, {"free", "local/my-local-model", "kilo/kilo-auto/free"})
        config = opencode_config(rows, "http://127.0.0.1:1234/v1", "private")
        self.assertTrue(config["compaction"]["auto"])
        self.assertEqual(omp_config(rows, "url")["providers"]["codelaboon"]["models"][1]["api"], "openai-completions")

    def test_anthropic_messages_preserve_tool_blocks(self):
        provider = Provider()
        provider._credential = lambda: ("claude-token", "oauth")
        provider._headers = lambda token, mode: {"Authorization": "Bearer " + token}
        body = {"model": "claude/current", "messages": [{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "read-1", "content": "source"}]}],
            "tools": [{"name": "read", "input_schema": {"type": "object"}}], "stream": True}
        with patch("codelaboon.native_gateway.requests.post", return_value=MagicMock(status_code=200)) as post:
            Gateway({"claude": provider}).request(body, "anthropic")
        self.assertEqual(post.call_args.kwargs["json"], dict(body, model="current"))
        self.assertTrue(post.call_args.args[0].endswith("/messages"))

    def test_gemini_account_wraps_requests_and_unwraps_sse_without_losing_function_calls(self):
        provider = Provider()
        provider._credential = lambda: ("google-token", "oauth")
        provider._headers = lambda token, mode: {"Authorization": "Bearer " + token}
        body = {"contents": [{"role": "user", "parts": [{"functionResponse": {
            "name": "read", "response": {"result": "source"}}}]}]}
        result = {"candidates": [{"content": {"parts": [{"functionCall": {"name": "read", "args": {"path": "a"}}}]}}]}
        response = MagicMock(status_code=200)
        response.headers = {"Content-Type": "text/event-stream"}
        response.iter_lines.return_value = iter(["data: " + json.dumps({"response": result}), ""])
        with serve({"gemini": provider}) as (gateway, url), \
                patch("codelaboon.gemini_auth.project_id", return_value="project"), \
                patch("codelaboon.native_gateway.requests.post", return_value=response) as post:
            client = requests.Session()
            client.trust_env = False
            answer = client.post(url + "/models/gemini/current:streamGenerateContent?alt=sse",
                                 headers={"x-goog-api-key": gateway.token}, json=body)
            self.assertEqual(answer.status_code, 200)
            self.assertEqual(json.loads(answer.text[6:].strip()), result)
        self.assertEqual(post.call_args.kwargs["json"], {"model": "current", "project": "project", "request": body})

    def test_freebuff_keeps_tools_and_uses_free_admission_metadata(self):
        provider = Provider()
        provider._credential = lambda: ("freebuff-token", "account")
        provider._ensure_slot = lambda token, model: "slot"
        provider._completion_body = lambda *args: {"codebuff_metadata": {"cost_mode": "free", "freebuff_instance_id": "slot"},
                                                  "provider": {"allow_fallbacks": True}}
        body = {"model": "freebuff/model", "tools": [{"type": "function", "function": {"name": "read"}}],
                "codebuff_metadata": {"cost_mode": "paid"}, "stream": True}
        with patch("codelaboon.native_gateway.requests.post", return_value=MagicMock(status_code=200)) as post:
            Gateway({"freebuff": provider}).request(body, "chat")
        sent = post.call_args.kwargs["json"]
        self.assertEqual(sent["tools"], body["tools"])
        self.assertEqual(sent["codebuff_metadata"]["cost_mode"], "free")


class ProviderBoundaryTests(unittest.TestCase):
    def test_local_provider_rejects_remote_and_credentialed_urls(self):
        for url in ("https://cloud.example/v1", "http://127.0.0.1.evil/v1", "http://token@127.0.0.1/v1"):
            with self.assertRaises(ValueError):
                LocalProvider(base_url=url)

    def test_openrouter_free_catalogue_filters_paid_and_preserves_slashes(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.json.return_value = {"data": [{"id": "vendor/model:free"}, {"id": "vendor/paid"}]}
        with patch("providers.compatible.requests.get", return_value=response):
            self.assertEqual(OpenRouterFreeProvider("key").list_models(), ["vendor/model:free"])

    def test_qoder_pat_uses_http_even_when_cli_is_installed(self):
        from providers.qoder.qoder_provider import QoderProvider
        from providers.qoder.cloud import QoderCloud
        with patch("providers.qoder.qoder_provider._binary", return_value="qodercli"), \
                patch.object(QoderCloud, "chat", return_value="answer") as chat:
            self.assertEqual(QoderProvider("pat").chat("auto", [{"role": "user", "content": "hello"}]), "answer")
            chat.assert_called_once()

    def test_paid_credential_lanes_never_enter_free_auto(self):
        from codelaboon.free_auto import ranked
        qoder = Provider()
        qoder._pat = lambda: "pat"
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(ranked({"gemini": Provider(), "qoder": qoder}), [])


class InstallationTests(unittest.TestCase):
    def test_virtualenv_install_does_not_use_user_site(self):
        from codelaboon.install import install_package
        with patch("codelaboon.install.sys.prefix", "venv"), \
                patch("codelaboon.install.sys.base_prefix", "system"), \
                patch("codelaboon.install.subprocess.run", return_value=MagicMock(returncode=0)) as run:
            self.assertEqual(install_package(extra=None)[0], 0)
        self.assertNotIn("--user", run.call_args.args[0])

    def test_update_stops_after_failed_pull(self):
        from codelaboon.update import update
        with patch("codelaboon.update._run", return_value=(1, "local changes")), \
                patch("codelaboon.update._is_git_checkout", return_value=True), \
                patch("codelaboon.update.shutil.which", return_value="git"), \
                patch("codelaboon.install.install_package") as install, \
                patch("sys.stdout", new_callable=io.StringIO):
            self.assertFalse(update())
        install.assert_not_called()

    def test_platform_autostart_specs_restart_without_a_shell(self):
        config = Path("/tmp/project with spaces/worker.json")
        name, linux = specification(config, "Linux")
        self.assertEqual(name, "codelaboon.service")
        self.assertIn(b"Restart=on-failure", linux)
        self.assertIn(b'"/tmp/project with spaces/worker.json"', linux)
        _, mac = specification(config, "Darwin")
        self.assertEqual(plistlib.loads(mac)["ProgramArguments"][-1], str(config))
        _, windows = specification(config, "Windows")
        root = ET.fromstring(windows)
        ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
        self.assertEqual(root.find("t:Settings/t:ExecutionTimeLimit", ns).text, "PT0S")
        self.assertNotIn("/bin/sh", windows.decode())


if __name__ == "__main__":
    unittest.main()
