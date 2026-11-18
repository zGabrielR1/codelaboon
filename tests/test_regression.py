import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from codelaboon import regression, watch, work


class RegressionWorkflowTests(unittest.TestCase):
    def test_keeps_worktree_and_rotates_model_after_throttling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "repository"
            project.mkdir()
            regression.git(project, "init")
            (project / "result.txt").write_text("broken")
            regression.git(project, "add", "result.txt")
            regression.git(project, "-c", "user.email=fixture@example.com",
                           "-c", "user.name=Fixture", "commit", "-m", "baseline")
            config = work.initialize(root / "work.json")
            command = f'{sys.executable} -c "import sys; sys.exit(1)"'
            with patch("codelaboon.work.start"), contextlib.redirect_stdout(io.StringIO()):
                regression.main(["Repair the fixture", "--project", str(project), "--config", str(config),
                                 "--reproduce", command, "--check", "check-fixture",
                                 "--fallback-model", "local/fixture"])
            _, _, runtime = work.configuration(config)
            job = json.loads(next((runtime / "inbox").glob("*.json")).read_text())
            worktree = Path(job["project"])
            self.assertEqual(len(job["regression"]["supporting"]), 2)
            models = []

            def execute(argv, cwd, output, timeout, **kwargs):
                self.assertEqual(cwd, worktree)
                if "-c" in argv and not models:
                    output.write_text("Functional fixture failure")
                    return 1
                if "--model" in argv:
                    models.append(argv[argv.index("--model") + 1])
                    if len(models) == 1:
                        (cwd / "result.txt").write_text("fixed")
                        output.write_text("HTTP 429 rate limit")
                        return 1
                self.assertEqual((cwd / "result.txt").read_text(), "fixed")
                output.write_text("Verified")
                return 0

            with patch("codelaboon.watch.execute", side_effect=execute) as executed:
                watch.run(config, once=True)
                state_path = runtime / "state.json"
                state = json.loads(state_path.read_text())
                state["next_run"].clear()
                state["cooldowns"].clear()
                watch.save(state_path, state)
                watch.run(config, once=True)
                self.assertEqual(executed.call_count, 5)
            self.assertEqual(models, ["free", "local/fixture"])
            self.assertEqual((project / "result.txt").read_text(), "broken")
            state = json.loads(state_path.read_text())
            final = Path(state["last_attempts"][job["id"]])
            self.assertIn("+fixed", (final / "repair.patch").read_text())
            self.assertEqual(json.loads((final / "handoff.json").read_text())["verification"], "passed")
            self.assertIn(job["id"], state["done"])
