from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from codelaboon import desktop_agents, task_api


class DesktopAgentTests(unittest.TestCase):
    def test_agent_controls_another_session_and_removes_presence_on_close(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(desktop_agents, "root", return_value=Path(directory)):
            agent = desktop_agents.Agent("task-1")
            try:
                self.assertEqual(desktop_agents.list_agents()["agents"][0]["task"], "task-1")
                desktop_agents.control_agent(agent.id, "pause")
                with self.assertRaisesRegex(ValueError, "paused"):
                    agent.check()
                desktop_agents.control_agent(agent.id, "resume")
                agent.check()
            finally:
                agent.close()
            self.assertEqual(desktop_agents.list_agents(), {"agents": []})

    def test_web_queue_passes_desktop_opt_in_and_continuous_cycles(self):
        with tempfile.TemporaryDirectory() as project:
            task = {"objective": "Review the app", "project": project, "scope": "App window",
                    "model": "local/vision", "checks": [["check"]], "profile": "coding",
                    "foreground_desktop": True, "cycles": 0}
            with patch("codelaboon.engine_tasks.catalog", return_value=[{"id": "jcode", "installed": True}]), (
                patch("codelaboon.swarm.enqueue", return_value="task-1")
            ) as enqueue, patch("codelaboon.work.start"):
                self.assertEqual(task_api.enqueue(task)["task"], "task-1")
            self.assertTrue(enqueue.call_args.kwargs["foreground_desktop"])
            self.assertEqual(enqueue.call_args.kwargs["cycles"], 0)
