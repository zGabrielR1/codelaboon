"""Qoder provider for codelaboon.

Qoder (qoder.com) is an agentic coding platform whose accounts include
a free plan. Sign in with ``codelaboon login qoder`` (the official
browser device flow — see ``codelaboon.qoder_auth``) or with a Personal
Access Token from https://qoder.com/account/integrations (the ``qoder``
provider's ``api_key`` or ``QODER_PERSONAL_ACCESS_TOKEN``).

Why chat goes through the ``qodercli`` binary: Qoder's inference
gateway only accepts requests signed by the official client (the
signature and response encryption live in that client's WASM module,
and personal-account requests without it are rejected with
``Signature invalid``). codelaboon therefore does not mint inference
requests itself; when the official ``qodercli``/``qoder`` binary is on
PATH it runs the turn through its non-interactive print mode
(``qoder -p --model <model> --tools ""``), which is tool-free plain
conversation on the signed-in account. A PAT, when configured, is
forwarded to that binary via ``QODER_PERSONAL_ACCESS_TOKEN`` — the same
variable the official CLI reads. Without the binary, chat says so
plainly instead of failing with a signature error from the gateway.

Free-tier terms apply: prompts may be processed under Qoder's data
policy for the plan in use. Use it for throwaway work, not secrets.
"""

import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from providers.base import BaseProvider

# The CLI's documented --model tiers, most recommended first. Specific
# frontier model ids come from `qodercli --list-models` when the binary
# is present; these tiers are the portable offline fallback.
DEFAULT_MODELS = ["auto", "performance", "efficient", "ultimate"]
MODEL_NAMES = {
    "auto": "Smart Routing (Auto)",
    "performance": "Performance",
    "efficient": "Efficient",
    "ultimate": "Ultimate",
}
TURN_TIMEOUT = 300

_INSTALL_HINT = (
    "Qoder chat runs through the official qodercli binary, which is not "
    "on PATH. Install it with: curl -fsSL https://qoder.com/install | bash\n"
    "Then sign in once with `qoder login` (or set "
    "QODER_PERSONAL_ACCESS_TOKEN to a Personal Access Token from "
    "https://qoder.com/account/integrations) and retry."
)


def _binary() -> Optional[str]:
    """Return the official Qoder CLI binary on PATH, if installed."""
    return shutil.which("qodercli") or shutil.which("qoder")


def _render_prompt(messages: List[Dict[str, str]], system: str = "") -> str:
    """Flatten a conversation into one print-mode prompt."""
    parts = []
    if system:
        parts.append(f"System: {system}")
    for message in messages or []:
        role = str(message.get("role") or "user").title()
        content = str(message.get("content") or "").strip()
        if content:
            parts.append(f"{role}: {content}")
    return "\n\n".join(parts).strip()


class QoderProvider(BaseProvider):
    """Provider for Qoder accounts, driven through the official CLI."""

    def __init__(
        self,
        api_key: str,
        models: List[str] = None,
        base_url: Optional[str] = None,
    ):
        super().__init__(api_key, models, base_url)
        self.default_models = list(DEFAULT_MODELS)
        self.model_names: Dict[str, str] = dict(MODEL_NAMES)

    def _pat(self) -> str:
        """Return the configured Personal Access Token, if any."""
        if self.api_key.strip():
            return self.api_key.strip()
        return os.environ.get("QODER_PERSONAL_ACCESS_TOKEN", "").strip()

    def validate_api_key(self) -> bool:
        if self._pat():
            return True
        from codelaboon.qoder_auth import token

        return bool(token())

    def _environment(self) -> Dict[str, str]:
        env = dict(os.environ)
        pat = self._pat()
        if pat:
            env["QODER_PERSONAL_ACCESS_TOKEN"] = pat
        return env

    def list_models(self) -> List[str]:
        """List the account's models, live from the CLI when available."""
        if not self.validate_api_key():
            return []
        if self.models:
            return list(self.models)
        binary = _binary()
        if binary:
            try:
                completed = subprocess.run(
                    [binary, "--list-models"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    env=self._environment(),
                )
            except (OSError, subprocess.SubprocessError):
                completed = None
            if completed is not None and completed.returncode == 0:
                models = []
                for line in completed.stdout.splitlines():
                    # The listing is human-readable; keep the first token
                    # of each non-empty line as the model identifier.
                    value = line.strip().lstrip("-*•0123456789. ")
                    if value:
                        models.append(value.split()[0].strip(","))
                if models:
                    return models
        return list(DEFAULT_MODELS)

    def chat(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        if not self.validate_api_key():
            raise ValueError("Invalid or missing Qoder credential")
        binary = _binary()
        if not binary:
            raise ValueError(_INSTALL_HINT)

        wire_model = str(model or "").strip() or "auto"
        prompt = _render_prompt(messages, str(kwargs.get("system") or ""))
        if not prompt:
            raise ValueError("Qoder needs a prompt")
        timeout = int(kwargs.get("timeout", TURN_TIMEOUT))
        command = [
            binary,
            "-p",
            "--model",
            wire_model,
            # Plain conversation: no file or shell tools for a chat turn.
            "--tools",
            "",
            "--permission-mode",
            "plan",
            prompt,
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self._environment(),
            )
        except subprocess.TimeoutExpired as error:
            raise ValueError(
                f"Qoder did not answer within {timeout} seconds."
            ) from error
        except OSError as error:
            raise ValueError(
                f"Qoder could not start ({error.filename or error}). {_INSTALL_HINT}"
            ) from error
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            detail = " ".join(detail.split())[:400]
            raise ValueError(
                detail
                or "Qoder failed to answer. Sign in with `qoder login` "
                "or check QODER_PERSONAL_ACCESS_TOKEN and retry."
            )
        answer = completed.stdout.strip()
        if not answer:
            raise ValueError("Qoder returned an empty response.")
        return answer
