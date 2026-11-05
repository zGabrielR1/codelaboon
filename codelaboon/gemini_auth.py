"""Google account sign-in for Gemini, using Antigravity's OAuth client.

This is the same installed-application OAuth flow Antigravity and Gemini Code
Assist use. It signs in with a normal Google account and onboards the account
to the free Code Assist tier, so it needs no billing account and no API key.

OAuth credentials are stored in ``gemini-session.json`` in the codelaboon
config directory with owner-only permissions and refresh automatically.
Google's terms for the free tier apply: prompts may be processed or retained by
the provider according to that tier's data policy.
"""

import json
import os
from pathlib import Path
import platform
import secrets
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

import requests

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo?alt=json"
OAUTH_FILE = "gemini-oauth.json"
SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/aicode",
    "https://www.googleapis.com/auth/cclog",
    "https://www.googleapis.com/auth/experimentsandconfigs",
]
DAILY_ENDPOINT = "https://daily-cloudcode-pa.googleapis.com"
API_VERSION = "v1internal"
PREFERRED_PORT = 51121
ANTIGRAVITY_VERSION = "2.29.0"
LOGIN_TIMEOUT = 300

_lock = threading.RLock()


def directory() -> Path:
    return Path(
        os.environ.get(
            "CODELABOON_CONFIG_DIR", str(Path.home() / ".config" / "codelaboon")
        )
    )


def read_session():
    """Return the saved Gemini session, or an empty dict."""
    try:
        data = json.loads(
            (directory() / "gemini-session.json").read_text(encoding="utf-8")
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


def read_oauth_client() -> tuple[str, str]:
    """Return the configured Google OAuth client ``(id, secret)``.

    The OAuth client is app identity, not an account credential, so it is
    supplied once by the user: environment variables take precedence, then a
    private ``gemini-oauth.json`` (flat keys or Google's downloaded format).
    """
    client_id = os.environ.get("CODELABOON_GEMINI_CLIENT_ID", "").strip()
    client_secret = os.environ.get(
        "CODELABOON_GEMINI_CLIENT_SECRET", ""
    ).strip()
    if client_id and client_secret:
        return client_id, client_secret
    try:
        data = json.loads(
            (directory() / OAUTH_FILE).read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ValueError, OSError):
        data = {}
    if isinstance(data, dict):
        section = data.get("installed") or data.get("web") or data
        if isinstance(section, dict):
            client_id = client_id or str(section.get("client_id") or "").strip()
            client_secret = client_secret or str(
                section.get("client_secret") or ""
            ).strip()
    return client_id, client_secret


def save_oauth_client(client_id: str, client_secret: str) -> None:
    """Store an OAuth client in the private config directory."""
    client_id = client_id.strip()
    client_secret = client_secret.strip()
    if not client_id or not client_secret:
        raise ValueError("Both the OAuth client ID and client secret are required.")
    save_record(
        OAUTH_FILE,
        {"client_id": client_id, "client_secret": client_secret},
    )


def import_oauth_client(path) -> tuple[str, str]:
    """Import a Google OAuth client JSON file downloaded from the console."""
    data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("OAuth client file must contain a JSON object.")
    section = data.get("installed") or data.get("web") or data
    if not isinstance(section, dict):
        raise ValueError("OAuth client file is missing its client section.")
    client_id = str(section.get("client_id") or "").strip()
    client_secret = str(section.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        raise ValueError(
            "OAuth client file is missing client_id or client_secret."
        )
    save_oauth_client(client_id, client_secret)
    return client_id, client_secret


def client() -> tuple[str, str]:
    """Return the OAuth client, or explain how to configure one."""
    client_id, client_secret = read_oauth_client()
    if not client_id or not client_secret:
        raise ValueError(
            "Gemini account sign-in needs a Google OAuth client. Run "
            "`codelaboon configure gemini` to add one, or set "
            "CODELABOON_GEMINI_CLIENT_ID and CODELABOON_GEMINI_CLIENT_SECRET. "
            "Create a free Desktop OAuth client in Google Cloud Console."
        )
    return client_id, client_secret


def user_agent() -> str:
    """Return the Antigravity-family user agent used by the free tier."""
    system = sys.platform
    if system == "darwin":
        os_type, arch = "darwin", platform.machine() or "arm64"
    elif system.startswith("win"):
        os_type, arch = "windows", "x86_64"
    else:
        os_type, arch = "linux", platform.machine() or "x86_64"
    return (
        f"antigravity/hub/{ANTIGRAVITY_VERSION} "
        f"(aidev_client; os_type={os_type}; arch={arch}; cl=1013060670)"
    )


def _open_server():
    """Start the loopback OAuth callback server."""
    result = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            parsed = urlsplit(self.path)
            params = parse_qs(parsed.query)
            valid = parsed.path == "/oauth-callback"
            if valid and not result:
                result.update(params)
            text = (
                b"<h1>Login successful</h1><p>You can close this window.</p>"
                if valid
                else b"<h1>Login failed</h1><p>Check the CLI output.</p>"
            )
            self.send_response(200 if valid else 400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
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
        f"Cannot start the Gemini sign-in callback server: {last_error}"
    )


def _project_from(payload: dict) -> str:
    """Extract a Cloud Code project id from a response envelope."""
    for key in ("cloudaicompanionProject", "projectId", "project"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            identifier = value.get("id")
            if isinstance(identifier, str) and identifier.strip():
                return identifier.strip()
    return ""


def _load_code_assist(token: str) -> dict:
    response = requests.post(
        f"{DAILY_ENDPOINT}/{API_VERSION}:loadCodeAssist",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": user_agent(),
        },
        json={"metadata": {"ideType": "ANTIGRAVITY"}},
        timeout=30,
    )
    if response.status_code != 200:
        return {}
    data = response.json()
    return data if isinstance(data, dict) else {}


def _default_tier(load: dict) -> str:
    tiers = load.get("allowedTiers")
    if isinstance(tiers, list):
        for tier in tiers:
            if isinstance(tier, dict) and tier.get("isDefault"):
                identifier = tier.get("id")
                if isinstance(identifier, str) and identifier.strip():
                    return identifier.strip()
    current = load.get("currentTier")
    if isinstance(current, dict):
        identifier = current.get("id")
        if isinstance(identifier, str) and identifier.strip():
            return identifier.strip()
    return "free-tier"


def _onboard(token: str, tier: str) -> str:
    body = {
        "tier_id": tier,
        "metadata": {
            "ide_type": "ANTIGRAVITY",
            "ide_version": ANTIGRAVITY_VERSION,
            "ide_name": "antigravity",
        },
    }
    for attempt in range(5):
        response = requests.post(
            f"{DAILY_ENDPOINT}/{API_VERSION}:onboardUser",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "*/*",
                "User-Agent": user_agent() + " google-api-nodejs-client/10.3.0",
                "X-Goog-Api-Client": "gl-node/22.21.1",
            },
            json=body,
            timeout=30,
        )
        if response.status_code != 200:
            raise ValueError(
                "Gemini free-tier onboarding failed "
                f"(HTTP {response.status_code})."
            )
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Gemini free-tier onboarding returned no project.")
        if data.get("done"):
            response_data = data.get("response")
            if isinstance(response_data, dict):
                project = _project_from(response_data)
                if project:
                    return project
            raise ValueError(
                "Gemini free-tier onboarding returned no project id."
            )
        if attempt < 4:
            time.sleep(2)
    raise ValueError("Gemini free-tier onboarding did not complete.")


def fetch_project(token: str) -> str:
    """Resolve (and if needed onboard) the free-tier Cloud Code project."""
    override = (
        os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GOOGLE_CLOUD_PROJECT_ID")
        or ""
    ).strip()
    if override and not override.isdigit():
        return override

    load = _load_code_assist(token)
    project = _project_from(load)
    if project:
        return project
    return _onboard(token, _default_tier(load))


def _userinfo(token: str) -> dict:
    try:
        response = requests.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if response.status_code == 200:
            data = response.json()
            return data if isinstance(data, dict) else {}
    except (requests.RequestException, ValueError):
        pass
    return {}


def login(report=None) -> None:
    """Run Google sign-in, onboard the free tier and save the session."""
    report = report or (lambda message: print(message, flush=True))
    client_id, client_secret = client()

    with _lock:
        old = read_session()

    state = secrets.token_urlsafe(32)
    server, port, result = _open_server()
    redirect = f"http://localhost:{port}/oauth-callback"
    params = {
        "access_type": "offline",
        "client_id": client_id,
        "prompt": "consent",
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        "include_granted_scopes": "true",
    }
    url = AUTH_URL + "?" + urlencode(params)
    report(
        "Complete Google sign-in in your browser. "
        "The free Gemini tier is onboarded automatically. Waiting up to 5 minutes."
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
        raise ValueError("Gemini sign-in was cancelled or timed out.")
    if "error" in result:
        detail = result.get("error_description", result["error"])[0]
        raise ValueError(f"Gemini sign-in failed: {detail}")
    if not secrets.compare_digest(result.get("state", [""])[0], state):
        raise ValueError("Gemini sign-in returned an invalid state.")
    code = result.get("code", [""])[0]
    if not code:
        raise ValueError("Gemini sign-in returned no authorization code.")

    response = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect,
            "grant_type": "authorization_code",
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise ValueError(
            "Gemini code exchange failed. Start sign-in again. "
            f"(HTTP {response.status_code})"
        )
    data = response.json()
    if not isinstance(data, dict) or not data.get("access_token"):
        raise ValueError("Gemini code exchange returned no access token.")
    token = data["access_token"]
    info = _userinfo(token)
    try:
        project = fetch_project(token)
    except (requests.RequestException, ValueError) as error:
        # Keep the tokens: onboarding is retried on first use, so a transient
        # provider failure does not force another browser sign-in.
        project = ""
        report(f"Google sign-in succeeded, but free-tier onboarding is pending: {error}")

    record = {
        "type": "gemini",
        "access_token": token,
        "refresh_token": data.get("refresh_token", old.get("refresh_token", "")),
        "expires_at": time.time() + int(data.get("expires_in", 3600)),
        "token_type": data.get("token_type", "Bearer"),
        "scope": data.get("scope", " ".join(SCOPES)),
        "email": info.get("email", old.get("email", "")),
        "project_id": project,
    }
    with _lock:
        save_record("gemini-session.json", record)
    if project:
        report(
            "Gemini connected with a Google account on the free tier. "
            "Refresh models to load your account catalogue."
        )
    else:
        report(
            "Gemini signed in. Free-tier onboarding will be retried on first use."
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
                    "Gemini session expired. Run codelaboon login gemini again."
                )
            client_id, client_secret = client()
            response = requests.post(
                TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                timeout=30,
            )
            if response.status_code != 200:
                raise ValueError(
                    "Gemini session expired. Run codelaboon login gemini again."
                )
            data = response.json()
            if not isinstance(data, dict) or not data.get("access_token"):
                raise ValueError(
                    "Gemini session expired. Run codelaboon login gemini again."
                )
            session.update(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", refresh_token),
                expires_at=time.time() + int(data.get("expires_in", 3600)),
            )
            save_record("gemini-session.json", session)
        return str(session.get("access_token") or "")


def project_id() -> str:
    """Return the saved free-tier project id, onboarding if it is missing."""
    with _lock:
        session = read_session()
    project = str(session.get("project_id") or "").strip()
    if project:
        return project
    token = access_token()
    if not token:
        return ""
    project = fetch_project(token)
    if project:
        with _lock:
            session = read_session()
            if session:
                session["project_id"] = project
                save_record("gemini-session.json", session)
    return project
