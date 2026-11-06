"""Qoder account sign-in (browser device flow).

This is the same device-code flow the official Qoder CLI
(``qodercli``) uses: generate a PKCE pair, open
``https://qoder.com/device/selectAccounts`` in the browser, then poll
the OpenAPI host until the account's device token arrives. The token
(and its refresh token) is stored in ``qoder-session.json`` inside the
codelaboon config directory with owner-only permissions.

A Qoder account includes the free plan, so a free-tier account can sign
in here just like the other account lanes. Note what this module does
and does not do: the login, token refresh, userinfo and plan checks
run against the OpenAPI host with a plain bearer token. Qoder's
inference gateway additionally requires the signed requests only the
official client can mint, so chat itself runs through the installed
``qodercli`` binary (see ``providers/qoder``).

A Personal Access Token from ``https://qoder.com/account/integrations``
is also honored: set ``QODER_PERSONAL_ACCESS_TOKEN`` or paste it as the
``qoder`` provider's ``api_key`` and it is exchanged for a session
token via ``POST /api/v1/jobToken/exchange``.
"""

import base64
import hashlib
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

WEB_URL = "https://qoder.com"
OPENAPI_URL = "https://openapi.qoder.sh"
# The official CLI's public OAuth client id for the production web app
# (extracted from qodercli 1.1.83; the CN build uses a different id and
# is selected with CODELABOON_QODER_CN=1).
CLIENT_ID = "e883ade2-e6e3-4d6d-adf7-f92ceff5fdcb"
CLIENT_ID_CN = "e93fe488-5778-4c35-a6fc-0f54ed7b3139"
POLL_INTERVAL = 1.0
# The official client polls for five minutes.
LOGIN_TIMEOUT = 300.0

_lock = threading.RLock()


def directory() -> Path:
    return Path(
        os.environ.get(
            "CODELABOON_CONFIG_DIR", str(Path.home() / ".config" / "codelaboon")
        )
    )


def read_session():
    """Return the saved Qoder session, or an empty dict."""
    try:
        data = json.loads(
            (directory() / "qoder-session.json").read_text(encoding="utf-8")
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
    """Remove the saved Qoder session."""
    (directory() / "qoder-session.json").unlink(missing_ok=True)


def machine_id() -> str:
    """Return this install's persistent Qoder machine id.

    The official client derives it from the device; codelaboon mints
    one random id per install and reuses it. The server only binds the
    browser sign-in (and token refresh) to the id, so it just needs to
    be stable across the login and later refreshes.
    """
    with _lock:
        try:
            data = json.loads(
                (directory() / "qoder-machine.json").read_text(encoding="utf-8")
            )
            value = str(data.get("id") or "").strip()
            if value:
                return value
        except (FileNotFoundError, ValueError, OSError):
            pass
        value = str(uuid.uuid4())
        save_record("qoder-machine.json", {"id": value})
        return value


def client_id() -> str:
    """Return the Qoder web app's public OAuth client id."""
    configured = os.environ.get("CODELABOON_QODER_CLIENT_ID", "").strip()
    if configured:
        return configured
    if os.environ.get("CODELABOON_QODER_CN", "").strip() in ("1", "true", "yes"):
        return CLIENT_ID_CN
    return CLIENT_ID


def personal_access_token() -> str:
    """Return a Qoder Personal Access Token from the environment, if set."""
    return os.environ.get("QODER_PERSONAL_ACCESS_TOKEN", "").strip()


def _pkce():
    """Return a ``(verifier, challenge)`` PKCE pair (S256, RFC 7636)."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    verifier = "".join(secrets.choice(alphabet) for _ in range(64))
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _expiry(data: dict, now: float):
    """Return the epoch expiry named by a token response, or None."""
    expires_at = data.get("expires_at") or data.get("expiresAt")
    if isinstance(expires_at, str) and expires_at:
        try:
            from datetime import datetime, timezone

            parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return int(parsed.timestamp())
        except ValueError:
            return None
    if isinstance(expires_at, (int, float)) and expires_at:
        value = int(expires_at)
        return value // 1000 if value > 1e12 else value
    expires_in = data.get("expires_in")
    if isinstance(expires_in, (int, float)) and expires_in:
        return int(now) + int(expires_in)
    return None


def _store_token(data: dict, kind: str) -> dict:
    """Normalize a token response into a session record and save it."""
    now = time.time()
    record = {
        "type": "qoder",
        "auth_kind": kind,
        "access_token": str(
            data.get("token") or data.get("device_token") or data.get("access_token") or ""
        ),
        "refresh_token": str(data.get("refresh_token") or data.get("refreshToken") or ""),
        "expires_at": _expiry(data, now),
        "machine_id": machine_id(),
    }
    for key in ("user_id", "user_name"):
        if data.get(key):
            record[key] = str(data[key])
    if not record["access_token"]:
        raise ValueError("Qoder sign-in returned no token.")
    with _lock:
        save_record("qoder-session.json", record)
    return record


def token() -> str:
    """Return the saved Qoder session token, or an empty string."""
    session = read_session()
    return str(session.get("access_token") or "").strip()


def _expired(session: dict) -> bool:
    expires_at = session.get("expires_at")
    if not isinstance(expires_at, (int, float)):
        return False
    return expires_at <= time.time() + 60


def refresh() -> str:
    """Exchange the refresh token for a fresh device token."""
    session = read_session()
    refresh_token = str(session.get("refresh_token") or "").strip()
    if not refresh_token:
        raise ValueError(
            "Qoder session has no refresh token. "
            "Run `codelaboon login qoder` to sign in again."
        )
    response = requests.post(
        OPENAPI_URL + "/api/v1/deviceToken/refresh",
        json={"refresh_token": refresh_token, "machine_id": machine_id()},
        timeout=30,
    )
    if response.status_code != 200:
        raise ValueError(
            "Qoder sign-in expired. Run `codelaboon login qoder` to sign in again."
        )
    try:
        data = response.json()
    except ValueError as error:
        raise ValueError("Qoder returned an invalid refresh response.") from error
    if not isinstance(data, dict):
        raise ValueError("Qoder returned an invalid refresh response.")
    record = _store_token(data, str(session.get("auth_kind") or "browser"))
    # Keep the account identity across refreshes.
    for key in ("user_id", "user_name"):
        if session.get(key):
            record[key] = session[key]
    with _lock:
        save_record("qoder-session.json", record)
    return record["access_token"]


def access_token() -> str:
    """Return a live Qoder token, refreshing it when needed."""
    session = read_session()
    value = str(session.get("access_token") or "").strip()
    if value and not _expired(session):
        return value
    if value and session.get("refresh_token"):
        return refresh()
    if value:
        return value
    raise ValueError(
        "Qoder is not signed in. Run `codelaboon login qoder` "
        "to sign in with a Qoder account."
    )


def exchange_personal_token(pat: str) -> dict:
    """Exchange a Personal Access Token for a session token."""
    response = requests.post(
        OPENAPI_URL + "/api/v1/jobToken/exchange",
        json={"personal_token": pat.strip(), "machine_id": machine_id()},
        timeout=30,
    )
    if response.status_code != 200:
        raise ValueError(
            "Qoder rejected this Personal Access Token. "
            "Check it at https://qoder.com/account/integrations."
        )
    try:
        data = response.json()
    except ValueError as error:
        raise ValueError("Qoder returned an invalid token response.") from error
    if not isinstance(data, dict):
        raise ValueError("Qoder returned an invalid token response.")
    return _store_token(data, "pat")


def _poll_login(nonce: str, verifier: str, report) -> dict:
    """Poll the device-token endpoint until the browser sign-in lands."""
    params = {"nonce": nonce, "verifier": verifier, "challenge_method": "S256"}
    deadline = time.monotonic() + LOGIN_TIMEOUT
    while time.monotonic() < deadline:
        response = requests.get(
            OPENAPI_URL + "/api/v1/deviceToken/poll",
            params=params,
            headers={"Accept": "application/json"},
            timeout=30,
        )
        if response.status_code == 200:
            try:
                data = response.json()
            except ValueError:
                data = None
            if isinstance(data, dict) and isinstance(data.get("token"), str) and data["token"]:
                return data
        elif response.status_code != 404:
            report(f"Waiting for Qoder sign-in... (HTTP {response.status_code})")
        time.sleep(POLL_INTERVAL)
    raise ValueError("Qoder sign-in was cancelled or timed out.")


def login(report=None) -> None:
    """Run the browser device sign-in and save the Qoder session."""
    report = report or (lambda message: print(message, flush=True))

    verifier, challenge = _pkce()
    nonce = str(uuid.uuid4())
    params = urlencode(
        {
            "challenge": challenge,
            "challenge_method": "S256",
            "nonce": nonce,
            "machine_id": machine_id(),
            "client_id": client_id(),
        }
    )
    auth_url = f"{WEB_URL}/device/selectAccounts?{params}"

    report("Open this URL in your browser to sign in to Qoder:")
    report(auth_url)
    try:
        if not webbrowser.open(auth_url):
            report("A browser could not be opened. Use the URL above.")
    except Exception:
        report("A browser could not be opened. Use the URL above.")
    report("Waiting for Qoder sign-in...")

    data = _poll_login(nonce, verifier, report)
    record = _store_token(data, "browser")
    name = record.get("user_name")
    report(
        f"Qoder connected{f' as {name}' if name else ''}. "
        "Refresh models to load your account catalogue."
    )


def userinfo(token_value: str = "") -> dict:
    """Return the signed-in account's profile from the OpenAPI host."""
    value = token_value or access_token()
    response = requests.get(
        OPENAPI_URL + "/api/v1/userinfo",
        headers={"Authorization": f"Bearer {value}", "Accept": "application/json"},
        timeout=30,
    )
    if response.status_code != 200:
        raise ValueError(
            f"Qoder rejected this token. (HTTP {response.status_code})"
        )
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Qoder returned an invalid profile response.")
    return data


def plan(token_value: str = "") -> dict:
    """Return the signed-in account's plan and quota from the OpenAPI host."""
    value = token_value or access_token()
    response = requests.get(
        OPENAPI_URL + "/api/v2/user/plan",
        headers={"Authorization": f"Bearer {value}", "Accept": "application/json"},
        timeout=30,
    )
    if response.status_code != 200:
        raise ValueError(
            f"Qoder could not load the plan. (HTTP {response.status_code})"
        )
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Qoder returned an invalid plan response.")
    return data


def logout() -> None:
    """Sign out of Qoder locally (the device token has no server logout)."""
    with _lock:
        clear_session()
