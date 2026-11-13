"""Native Qoder Cloud Agents transport (no local CLI or SDK).

Protocol: https://docs.qoder.com/cloud-agents/quickstart
Only explicit PATs are used here; browser device tokens belong to the CLI lane.
"""
import json
import math
import time
from urllib.parse import quote

import requests

BASE_URL = "https://api.qoder.com/api/v1/cloud"


class QoderCloud:
    def __init__(self, pat):
        self.pat = pat

    def _request(self, method, path, timeout=30, **kwargs):
        extra_headers = kwargs.pop("headers", {})
        response = requests.request(
            method, BASE_URL + path,
            headers={"Authorization": f"Bearer {self.pat}", "Content-Type": "application/json", **extra_headers},
            timeout=timeout, **kwargs,
        )
        if not 200 <= response.status_code < 300:
            response.close()
            raise ValueError(
                f"Qoder Cloud HTTP {response.status_code}. Check PAT permissions, "
                "Cloud Agents access and account quota. No CLI fallback was attempted."
            )
        return response

    def _json(self, method, path, **kwargs):
        with self._request(method, path, **kwargs) as response:
            data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Qoder Cloud returned an invalid response")
        return data

    def list_models(self):
        data = self._json("GET", "/models").get("data", [])
        if not isinstance(data, list):
            raise ValueError("Qoder Cloud returned an invalid model catalog")
        return list(dict.fromkeys(row["id"] for row in data if isinstance(row, dict)
                and isinstance(row.get("id"), str) and row["id"].strip()))

    def chat(self, model, prompt, timeout=300):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Qoder Cloud timeout must be a positive finite number")
        deadline = time.monotonic() + timeout

        def remaining():
            value = deadline - time.monotonic()
            if value <= 0:
                raise ValueError("Qoder Cloud timed out; the remote session may still be running.")
            return min(30, value)

        # Reuse an existing environment; avoid provisioning infrastructure implicitly.
        environments = self._json("GET", "/environments", timeout=remaining()).get("data", [])
        if not isinstance(environments, list):
            raise ValueError("Qoder Cloud returned an invalid environment list")
        environment = next((row for row in environments if isinstance(row, dict)
                            and isinstance(row.get("id"), str) and row["id"]), None)
        if environment is None:
            raise ValueError("Create a Qoder Cloud environment in your Qoder account first.")
        agent = self._json("POST", "/agents", timeout=remaining(), json={
            "name": "codelaboon", "model": model, "tools": [],
        })
        if not isinstance(agent.get("id"), str) or not agent["id"]:
            raise ValueError("Qoder Cloud returned no agent ID")
        session = self._json("POST", "/sessions", timeout=remaining(), json={
            "environment_id": environment["id"],
            "agent": agent["id"],
        })
        session_id = session.get("id")
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("Qoder Cloud returned no session ID")
        path = "/sessions/" + quote(session_id, safe="") + "/events"
        sent = self._json("POST", path, timeout=remaining(), json={"events": [{
            "type": "user.message", "content": [{"type": "text", "text": prompt}],
        }]})
        sent_events = sent.get("data", [])
        cursor = (sent_events[-1].get("id") if isinstance(sent_events, list)
                  and sent_events and isinstance(sent_events[-1], dict) else None)
        if not isinstance(cursor, str) or not cursor:
            raise ValueError("Qoder Cloud returned no event cursor; cannot safely read this turn.")
        answers = []
        # The cursor prevents losing a response completed before connecting.
        # SSE replays this new session's events, including a fast completed answer.
        with self._request("GET", path + "/stream", timeout=remaining(), stream=True, headers={"Last-Event-ID": cursor, "Accept": "text/event-stream"}) as response:
            response.encoding = "utf-8"
            data_lines = []
            frame_size = 0
            for line in response.iter_lines(decode_unicode=True, chunk_size=1):
                remaining()
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
                    frame_size += len(line)
                    if frame_size > 1024 * 1024:
                        raise ValueError("Qoder Cloud event exceeded the size limit")
                elif not line and data_lines:
                    try:
                        event = json.loads("\n".join(data_lines))
                    except ValueError as error:
                        raise ValueError("Qoder Cloud returned an invalid stream event") from error
                    data_lines = []
                    frame_size = 0
                    if not isinstance(event, dict):
                        raise ValueError("Qoder Cloud returned an invalid stream event")
                    kind = event.get("type", "")
                    if kind == "agent.message":
                        content = event.get("content")
                        if not isinstance(content, list):
                            raise ValueError("Qoder Cloud returned invalid message content")
                        answers.extend(block["text"] for block in content
                                       if isinstance(block, dict) and block.get("type") == "text"
                                       and isinstance(block.get("text"), str))
                    elif kind == "session.status_idle":
                        stop_reason = event.get("stop_reason")
                        reason = stop_reason.get("type") if isinstance(stop_reason, dict) else None
                        if reason != "end_turn" or not answers:
                            raise ValueError(f"Qoder Cloud turn did not complete successfully ({reason}).")
                        return "\n".join(answers)
                    elif kind == "session.error":
                        error = event.get("error")
                        retry = error.get("retry_status") if isinstance(error, dict) else None
                        if not isinstance(retry, dict) or retry.get("type") != "retrying":
                            raise ValueError("Qoder Cloud failed to complete the turn.")
                    elif kind in ("session.status_error", "agent.error", "session.status_terminated"):
                        raise ValueError("Qoder Cloud failed to complete the turn.")
        raise ValueError("Qoder Cloud stream ended before the turn completed.")
