"""Freebuff account sign-in (device-code login).

This is the same device-code flow the Freebuff CLI uses: request a login code
from the Freebuff web app, finish sign-in in the browser, then poll the status
endpoint until the account's token arrives. The token is then used against the
Codebuff API host for the free-session admission, the model catalog and chat
completions.

The credential is stored in ``freebuff-session.json`` inside the codelaboon
config directory with owner-only permissions. Freebuff is funded by ads and the
free tier's data policy applies: prompts may be processed, logged or retained
by the provider. Use it for throwaway work, not secrets.

A token already present in a Freebuff CLI install (``credentials.json`` under
``~/.config/manicode``), in ``CODEBUFF_API_KEY`` / ``FREEBUFF_API_KEY``, or in
the provider config is honored without a new browser sign-in.
"""

import json
import os
from pathlib import Path
import secrets
import threading
import time
import uuid
import webbrowser
from urllib.parse import urlencode

import requests

# Sign-in lives on the Freebuff web app; the API lives on the Codebuff host.
WEB_URL = "https://freebuff.com"
API_URL = "https://codebuff.com"
LOGIN_CODE_URL = WEB_URL + "/api/auth/cli/code"
LOGIN_STATUS_URL = WEB_URL + "/api/auth/cli/status"
LOGOUT_URL = WEB_URL + "/api/auth/cli/logout"
POLL_INTERVAL = 5.0
# The server issues codes valid for an hour; that is the poll window.
LOGIN_TIMEOUT = 3600.0

_lock = threading.RLock()


def directory() -> Path:
    return Path(
        os.environ.get(
            "CODELABOON_CONFIG_DIR", str(Path.home() / ".config" / "codelaboon")
        )
    )


def read_session():
    """Return the saved Freebuff session, or an empty dict."""
    try:
        data = json.loads(
            (directory() / "freebuff-session.json").read_text(encoding="utf-8")
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
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def clear_session() -> None:
    """Remove the saved Freebuff session."""
    (directory() / "freebuff-session.json").unlink(missing_ok=True)


def fingerprint_id() -> str:
    """Return this install's persistent login fingerprint id.

    Unlike the Freebuff CLI's hardware fingerprint, codelaboon mints one
    random id per install and reuses it. The server binds a login code to the
    id, so it only needs to be stable between the code request and the poll.
    """
    with _lock:
        try:
            data = json.loads(
                (directory() / "freebuff-fingerprint.json").read_text(
                    encoding="utf-8"
                )
            )
            value = str(data.get("id") or "").strip()
            if value:
                return value
        except (FileNotFoundError, ValueError, OSError):
            pass
        value = "codebuff-cli-" + secrets.token_urlsafe(6)[:8]
        save_record("freebuff-fingerprint.json", {"id": value})
        return value


def _manicode_credentials_path() -> Path:
    configured = os.environ.get("FREEBUFF_CONFIG_DIR", "").strip()
    if configured:
        return Path(configured) / "credentials.json"
    return Path.home() / ".config" / "manicode" / "credentials.json"


def _read_manicode_token() -> str:
    """Return a token from an installed Freebuff CLI, if present.

    The file holds ``{"default": {"authToken": ...}}``. When the token lives
    in the OS keychain instead (``tokenStore: "keychain"``) it is not
    readable here and this returns an empty string.
    """
    try:
        data = json.loads(_manicode_credentials_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return ""
    if not isinstance(data, dict):
        return ""
    default = data.get("default")
    if not isinstance(default, dict):
        return ""
    token = str(default.get("authToken") or "").strip()
    return token


def token() -> str:
    """Return the best available Freebuff token, or an empty string.

    Precedence: the codelaboon session, then the environment, then an
    installed Freebuff CLI's credentials file.
    """
    session = read_session()
    value = str(session.get("authToken") or session.get("access_token") or "")
    if value.strip():
        return value.strip()
    for name in ("CODEBUFF_API_KEY", "FREEBUFF_API_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return _read_manicode_token()


def access_token() -> str:
    """Return the Freebuff token, or explain how to sign in."""
    value = token()
    if not value:
        raise ValueError(
            "Freebuff is not signed in. Run `codelaboon login freebuff` "
            "to sign in with a Freebuff account."
        )
    return value


def _request_login_code(fingerprint: str) -> dict:
    response = requests.post(
        LOGIN_CODE_URL,
        json={"fingerprintId": fingerprint},
        timeout=30,
    )
    if response.status_code != 200:
        raise ValueError(
            "Freebuff sign-in could not start. "
            f"(HTTP {response.status_code})"
        )
    data = response.json()
    if not isinstance(data, dict) or not data.get("loginUrl"):
        raise ValueError("Freebuff sign-in returned no login URL.")
    return data


def _poll_login(fingerprint: str, fingerprint_hash: str, expires_at, report):
    """Poll the status endpoint until sign-in completes."""
    params = {
        "fingerprintId": fingerprint,
        "fingerprintHash": fingerprint_hash,
        "expiresAt": str(expires_at),
    }
    deadline = time.monotonic() + LOGIN_TIMEOUT
    while time.monotonic() < deadline:
        response = requests.get(LOGIN_STATUS_URL, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            user = data.get("user") if isinstance(data, dict) else None
            if isinstance(user, dict) and user.get("authToken"):
                return user
        elif response.status_code != 401:
            report(
                "Waiting for Freebuff sign-in... "
                f"(HTTP {response.status_code})"
            )
        time.sleep(POLL_INTERVAL)
    raise ValueError("Freebuff sign-in was cancelled or timed out.")


def login(report=None) -> None:
    """Run the device-code sign-in and save the Freebuff session."""
    report = report or (lambda message: print(message, flush=True))

    with _lock:
        fingerprint = fingerprint_id()

    code = _request_login_code(fingerprint)
    login_url = str(code["loginUrl"])
    # Attribution for the login funnel; ignored by sign-in itself.
    flow_id = str(uuid.uuid4())
    parsed = login_url.split("?", 1)
    if len(parsed) == 2:
        login_url = parsed[0] + "?" + parsed[1] + "&cli_flow=" + flow_id

    report("Open this URL in your browser to sign in to Freebuff:")
    report(login_url)
    try:
        if not webbrowser.open(login_url):
            report("A browser could not be opened. Use the URL above.")
    except Exception:
        report("A browser could not be opened. Use the URL above.")
    report("Waiting for Freebuff sign-in...")

    user = _poll_login(
        fingerprint,
        str(code.get("fingerprintHash") or ""),
        code.get("expiresAt"),
        report,
    )

    record = {
        "type": "freebuff",
        "authToken": str(user.get("authToken") or ""),
        "userId": str(user.get("id") or ""),
        "name": str(user.get("name") or ""),
        "email": str(user.get("email") or ""),
        "credits": user.get("credits"),
        "fingerprintId": fingerprint,
        "fingerprintHash": str(code.get("fingerprintHash") or ""),
    }
    with _lock:
        save_record("freebuff-session.json", record)
    name = record["name"] or record["email"]
    report(
        f"Freebuff connected{f' as {name}' if name else ''}. "
        "Refresh models to load your account catalogue."
    )


def logout() -> None:
    """Sign out of Freebuff locally, best-effort on the server."""
    with _lock:
        session = read_session()
        if session:
            try:
                requests.post(
                    LOGOUT_URL,
                    json={
                        "userId": str(session.get("userId") or session.get("id") or ""),
                        "fingerprintId": str(
                            session.get("fingerprintId") or ""
                        ),
                        "fingerprintHash": str(
                            session.get("fingerprintHash") or ""
                        ),
                    },
                    timeout=15,
                )
            except requests.RequestException:
                pass
            clear_session()
