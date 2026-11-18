import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from codelaboon import gui_regression, task_api


class GuiRegressionTests(unittest.TestCase):
    def test_flow_requires_a_final_assertion(self):
        spec = {"build": ["make"], "launch": ["./app"],
                "steps": [{"action": "click", "name": "Run"}]}
        with self.assertRaisesRegex(ValueError, "assertion"):
            gui_regression.validate(spec)
        spec["steps"].append({"action": "expect", "name": "Passed"})
        self.assertEqual(gui_regression.validate(spec), spec)

    def test_takeover_requires_the_paused_session_and_current_frame(self):
        with tempfile.TemporaryDirectory() as root:
            runtime = Path(root)
            attempt = runtime / "attempt"
            session = attempt / "gui-before"
            session.mkdir(parents=True)
            (attempt / "result.json").write_text(json.dumps(
                {"task": "demo", "started": 1, "status": "running"}))
            live = session / "live.json"
            live.write_text(json.dumps({"phase": "verifying", "frame": "current"}))
            with patch.object(task_api, "selected", return_value=(None, runtime, {"regression": {"gui": True}})):
                task_api.gui_desktop("demo", {"action": "takeover"})
                self.assertTrue((session / "hold").exists())
                live.write_text(json.dumps({"phase": "paused", "frame": "current"}))
                with self.assertRaisesRegex(ValueError, "latest"):
                    task_api.gui_desktop("demo", {"action": "click", "frame": "old", "x": 4, "y": 5})
                task_api.gui_desktop("demo", {"action": "click", "frame": "current", "x": 4, "y": 5})
                self.assertEqual(json.loads((session / "input.json").read_text())["x"], 4)
                task_api.gui_desktop("demo", {"action": "resume"})
                self.assertFalse((session / "hold").exists())
