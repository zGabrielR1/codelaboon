"""Claude account sign-in using Anthropic's Claude Code OAuth flow.

The flow is the same public-client + PKCE flow Claude Code uses. It works with
claude.ai accounts (Pro, Max, Ultra, Team and Enterprise) and does not require
an Anthropic Console API key. A free claude.ai account can complete the same
sign-in; whether Anthropic grants inference for it is decided by Anthropic.

Credentials are stored in ``claude-session.json`` inside the codelaboon config
directory with owner-only permissions and refresh automatically.
"""

import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

import requests

AUTH_URL = "https://claude.ai/oauth/authorize"
TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
PROFILE_URL = "https://api.anthropic.com/api/oauth/profile"
CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
SCOPE = (
    "user:profile user:inference user:sessions:claude_code "
    "user:mcp_servers user:file_upload"
)
PREFERRED_PORT = 54545
LOGIN_TIMEOUT = 300

_lock = threading.RLock()


def directory() -> Path:
    return Path(
        os.environ.get(
            "CODELABOON_CONFIG_DIR", str(Path.home() / ".config" / "codelaboon")
        )
    )


def read_session():
    """Return the saved Claude session, or an empty dict."""
    try:
        data = json.loads(
            (directory() / "claude-session.json").read_text(encoding="utf-8")
        )
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def save_record(name: str, data: dict) -> None:
    """Atomically write a private credential record."""
    root = directory()
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    temporary = root / (name + "." + secrets.token_hex(8) + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(96)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return verifier, challenge


def _open_server(state: str):
    """Start a loopback callback server, preferring Claude Code's port."""
    result = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            parsed = urlsplit(self.path)
            params = parse_qs(parsed.query)
            valid = parsed.path == "/callback" and secrets.compare_digest(
                params.get("state", [""])[0], state
            )
            if valid and not result:
                result.update(params)
            text = (
                b"You may return to codelaboon."
                if valid
                else b"Invalid sign-in callback."
            )
            self.send_response(200 if valid else 400)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(text)

    last_error = None
    for port in (PREFERRED_PORT, 0):
        try:
            server = HTTPServer(("127.0.0.1", port), Callback)
            server.timeout = 1
            return server, server.server_port, result
        except OSError as error:
            last_error = error
    raise ValueError(
        f"Cannot start the Claude sign-in callback server: {last_error}"
    )


def _profile(token: str) -> dict:
    """Fetch the account profile; identity details are advisory."""
    try:
        response = requests.get(
            PROFILE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=15,
        )
        if response.status_code == 200:
            data = response.json()
            return data if isinstance(data, dict) else {}
    except (requests.RequestException, ValueError):
        pass
    return {}


def login(report=None) -> None:
    """Run the browser authorization flow and save the Claude session."""
    report = report or (lambda message: print(message, flush=True))

    with _lock:
        old = read_session()
        if not (directory() / "claude-device.json").exists():
            save_record("claude-device.json", {"id": secrets.token_hex(32)})

    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(32)
    server, port, result = _open_server(state)
    redirect = f"http://localhost:{port}/callback"

    params = {
        "code": "true",
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect,
        "scope": SCOPE,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    url = AUTH_URL + "?" + urlencode(params)
    report(
        "Complete Claude authorization in your browser. "
        "Waiting up to 5 minutes."
    )

    try:
        if not webbrowser.open(url):
            report(url)
        deadline = time.monotonic() + LOGIN_TIMEOUT
        while not result and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()

    if not result:
        raise ValueError("Claude sign-in was cancelled or timed out.")
    if "error" in result:
        detail = result.get("error_description", result["error"])[0]
        raise ValueError(f"Claude sign-in failed: {detail}")

    code = result.get("code", [""])[0]
    returned_state = result.get("state", [""])[0]
    # The Claude callback can carry the state as ``code#state``.
    if "#" in code:
        code, fragment_state = code.split("#", 1)
        returned_state = fragment_state or returned_state
    if not code:
        raise ValueError("Claude sign-in returned no authorization code.")
    if not secrets.compare_digest(returned_state, state):
        raise ValueError("Claude sign-in returned an invalid state.")

    response = requests.post(
        TOKEN_URL,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "axios/1.15.2",
        },
        json={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect,
            "client_id": CLIENT_ID,
            "code_verifier": verifier,
            "state": returned_state,
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise ValueError(
            "Claude code exchange failed. Start sign-in again. "
            f"(HTTP {response.status_code})"
        )
    data = response.json()
    if not isinstance(data, dict) or not data.get("access_token"):
        raise ValueError("Claude code exchange returned no access token.")

    profile = _profile(data["access_token"])
    account = profile.get("account") if isinstance(profile, dict) else {}
    organization = profile.get("organization") if isinstance(profile, dict) else {}
    record = {
        "type": "claude",
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", old.get("refresh_token", "")),
        "expires_at": time.time() + int(data.get("expires_in", 3600)),
        "scope": data.get("scope", SCOPE),
        "token_type": data.get("token_type", "Bearer"),
        "account": account or data.get("account", {}),
        "organization": organization or data.get("organization", {}),
    }
    with _lock:
        save_record("claude-session.json", record)
    report(
        "Claude connected. Refresh models to load your account catalogue."
    )


def access_token() -> str:
    """Return a valid access token, refreshing it when necessary."""
    with _lock:
        session = read_session()
        if not session:
            return ""
        try:
            expires_at = float(session.get("expires_at", 0))
        except (TypeError, ValueError):
            expires_at = 0
        if expires_at < time.time() + 60:
            refresh_token = str(session.get("refresh_token") or "")
            if not refresh_token:
                raise ValueError(
                    "Claude session expired. Run codelaboon login claude again."
                )
            response = requests.post(
                TOKEN_URL,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "axios/1.15.2",
                },
                json={
                    "client_id": CLIENT_ID,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "scope": SCOPE,
                },
                timeout=30,
            )
            if response.status_code != 200:
                raise ValueError(
                    "Claude session expired. Run codelaboon login claude again."
                )
            data = response.json()
            if not isinstance(data, dict) or not data.get("access_token"):
                raise ValueError(
                    "Claude session expired. Run codelaboon login claude again."
                )
            session.update(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", refresh_token),
                expires_at=time.time() + int(data.get("expires_in", 3600)),
            )
            save_record("claude-session.json", session)
        return str(session.get("access_token") or "")
