"""Protocol and routing checks for Qoder without a local binary."""
import json
import os
import unittest
from unittest.mock import MagicMock, patch
from providers.qoder.cloud import QoderCloud
from providers.qoder.qoder_provider import QoderProvider


class QoderCloudTests(unittest.TestCase):
    def test_pat_without_cli_routes_directly(self):
        with patch.dict(os.environ, {}, clear=True), patch("providers.qoder.qoder_provider._binary", return_value=None), patch.object(QoderCloud, "chat", return_value="answer") as chat:
            self.assertEqual(QoderProvider("pat").chat("auto", [{"role": "user", "content": "hi"}]), "answer")
        self.assertEqual(chat.call_args.args[:2], ("auto", "User: hi"))

    def _run_turn(self, events):
        cloud = QoderCloud("pat")
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_lines.return_value = iter(line for event in events
            for line in ("data: " + json.dumps(event), ""))
        with patch.object(cloud, "_json", side_effect=[{"data": [{"id": "env_1"}]}, {"id": "agent_1"}, {"id": "sess_1"}, {"data": [{"id": "evt_user"}]}]) as request, patch.object(cloud, "_request", return_value=response) as stream:
            answer = cloud.chat("auto", "hi")
        self.assertEqual(request.call_args_list[1].kwargs["json"]["tools"], [])
        self.assertEqual(request.call_args_list[2].kwargs["json"]["agent"], "agent_1")
        self.assertEqual(stream.call_args.kwargs["headers"]["Last-Event-ID"], "evt_user")
        return answer

    def test_sse_ignores_reasoning_and_waits_for_success(self):
        self.assertEqual(self._run_turn([
            {"type": "agent.thinking"},
            {"type": "agent.message", "content": [{"type": "text", "text": "hello"}]},
            {"type": "session.status_idle", "stop_reason": {"type": "end_turn"}},
        ]), "hello")

    def test_truncated_stream_is_failure(self):
        with self.assertRaisesRegex(ValueError, "before the turn completed"):
            self._run_turn([{"type": "agent.message", "content": [{"type": "text", "text": "partial"}]}])

    def test_no_environment_does_not_create_infrastructure(self):
        cloud = QoderCloud("pat")
        with patch.object(cloud, "_json", return_value={"data": []}) as request:
            with self.assertRaisesRegex(ValueError, "environment"):
                cloud.chat("auto", "hi")
        self.assertEqual(request.call_count, 1)

    def test_malformed_stream_payload_fails_cleanly(self):
        with self.assertRaisesRegex(ValueError, "invalid stream event"):
            self._run_turn([[]])

    def test_malformed_content_fails_cleanly(self):
        with self.assertRaisesRegex(ValueError, "invalid message content"):
            self._run_turn([{"type": "agent.message", "content": None}])

    def test_invalid_timeout_does_not_contact_provider(self):
        for timeout in (0, -1, float("inf"), float("nan")):
            with self.subTest(timeout=timeout), patch("requests.request") as request:
                with self.assertRaisesRegex(ValueError, "positive finite"):
                    QoderCloud("pat").chat("auto", "hi", timeout)
                request.assert_not_called()

    def test_recoverable_error_waits_for_final_answer(self):
        self.assertEqual(self._run_turn([
            {"type": "session.error", "error": {"retry_status": {"type": "retrying"}}},
            {"type": "session.status_rescheduled"},
            {"type": "agent.message", "content": [{"type": "text", "text": "recovered"}]},
            {"type": "session.status_idle", "stop_reason": {"type": "end_turn"}},
        ]), "recovered")

    def test_terminal_error_does_not_return_partial_answer(self):
        with self.assertRaisesRegex(ValueError, "failed to complete"):
            self._run_turn([
                {"type": "agent.message", "content": [{"type": "text", "text": "partial"}]},
                {"type": "session.error", "error": {"retry_status": {"type": "terminal"}}},
            ])
