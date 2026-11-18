"""Text chat through Codelaboon's Firefox extension."""

import json
import secrets
import time
import webbrowser
from pathlib import Path

from requests import Response

from codelaboon.paths import config_dir
from providers.base import BaseProvider
from providers.claude.firefox_bridge import chat

MODEL = "web-default"


def profile_marker():
    return config_dir() / "claude-browser-extension-enabled"


def extension_manifest():
    manifest = Path(__file__).resolve().parents[2] / "codelaboon/integrations/claude-browser/manifest.json"
    if not manifest.is_file():
        raise ValueError("The Codelaboon browser extension files are missing.")
    return manifest


def enable():
    manifest = extension_manifest()
    marker = profile_marker()
    marker.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    marker.touch(mode=0o600)
    return manifest


def setup():
    manifest = enable()
    print("In Firefox, open about:debugging#/runtime/this-firefox and select Load Temporary Add-on.")
    print(f"Select this manifest: {manifest}")
    print("Then run codelaboon claude-browser test.")
    webbrowser.open("https://claude.ai/new", new=2)


def test_connection(provider):
    return provider.chat(
        MODEL, [{"role": "user", "content": "Reply with only: Codelaboon browser bridge works."}]
    )


class ClaudeBrowserProvider(BaseProvider):
    """Use the account's current browser model for explicit text requests."""

    display_name = "Claude.ai (Firefox)"
    model_names = {MODEL: "Claude · Browser default (Firefox)"}
    model_descriptions = {MODEL: "Text chat using the model available in your signed-in Claude.ai session."}
    default_models = (MODEL,)

    def validate_api_key(self):
        return profile_marker().is_file()

    def list_models(self):
        return [MODEL] if self.validate_api_key() else []

    def chat(self, model, messages, **kwargs):
        if not self.validate_api_key():
            raise ValueError("Run codelaboon claude-browser setup to enable the browser provider.")
        if model != MODEL:
            raise ValueError("Use web-default for the Claude.ai browser provider.")
        if kwargs.get("tools"):
            raise ValueError("Claude.ai browser chat supports text only.")
        if not messages or messages[-1].get("role") != "user":
            raise ValueError("Claude.ai browser chat requires a final user message.")
        parts = []
        for message in messages:
            role, content = message.get("role"), message.get("content")
            if role not in ("system", "user", "assistant") or not isinstance(content, str):
                raise ValueError("Claude.ai browser chat supports text messages only.")
            parts.append(f"{role}:\n{content}" if len(messages) > 1 else content)
        prompt = "\n\n".join(parts)
        if not prompt.strip():
            raise ValueError("Claude.ai browser chat requires a nonempty prompt.")

        return chat(prompt, background=kwargs.get("background", False))

    def engine_response(self, model, body):
        """Return a text completion on the shared engine gateway."""
        messages = []
        for message in body.get("messages", []):
            role = message.get("role")
            content = message.get("content")
            if message.get("tool_calls") or message.get("function_call") or role in ("tool", "function"):
                raise ValueError("Start a new text conversation to use Claude.ai browser chat.")
            if role == "developer":
                role = "system"
            if isinstance(content, list):
                if any(part.get("type") != "text" for part in content):
                    raise ValueError("Claude.ai browser chat accepts text input only.")
                content = "\n".join(part.get("text", "") for part in content)
            messages.append({"role": role, "content": content})

        reply = self.chat(model, messages, background=True)
        response = Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response.codelaboon_google_oauth = False
        metadata = {
            "id": "chatcmpl-" + secrets.token_hex(12),
            "created": int(time.time()),
            "model": body["model"],
        }
        if body.get("stream"):
            response.headers["Content-Type"] = "text/event-stream"
            chunk = dict(metadata, object="chat.completion.chunk")
            data = (
                dict(chunk, choices=[{"index": 0, "delta": {"role": "assistant", "content": reply},
                                      "finish_reason": None}]),
                dict(chunk, choices=[{"index": 0, "delta": {}, "finish_reason": "stop"}]),
            )
            wire = "".join(f"data: {json.dumps(event)}\n\n" for event in data) + "data: [DONE]\n\n"
        else:
            response.headers["Content-Type"] = "application/json"
            wire = json.dumps(dict(
                metadata, object="chat.completion",
                choices=[{"index": 0, "message": {"role": "assistant", "content": reply},
                          "finish_reason": "stop"}],
            ))
        response._content = wire.encode("utf-8")
        response._content_consumed = True
        return response
