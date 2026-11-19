"""Local desktop-agent presence and cooperative controls."""
import json
import os
from pathlib import Path
import uuid

from codelaboon.paths import data_dir


def root():
    return data_dir() / "desktop-agents"


def acquire(stream):
    if os.name == "nt":
        import msvcrt
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


class Agent:
    def __init__(self, task=None):
        self.id = uuid.uuid4().hex
        self.directory = root() / self.id
        self.directory.mkdir(parents=True, mode=0o700)
        self.lock = (self.directory / "live.lock").open("a+b")
        acquire(self.lock)
        (self.directory / "agent.json").write_text(
            json.dumps({"id": self.id, "task": task, "project": str(Path.cwd())}), encoding="utf-8"
        )

    def check(self):
        if (self.directory / "PAUSE").exists():
            raise ValueError("This desktop agent is paused. Resume it from Tasks or another agent.")

    def close(self):
        (self.directory / "agent.json").unlink(missing_ok=True)
        self.lock.close()
        for name in ("live.lock", "PAUSE"):
            (self.directory / name).unlink(missing_ok=True)
        try:
            self.directory.rmdir()
        except OSError:
            pass


def list_agents():
    """List active desktop MCP sessions and their pause state."""
    agents = []
    for path in sorted(root().glob("*/agent.json")):
        try:
            with (path.parent / "live.lock").open("r+b") as lock:
                try:
                    acquire(lock)
                except OSError:
                    row = json.loads(path.read_text(encoding="utf-8"))
                    agents.append({**row, "paused": (path.parent / "PAUSE").exists()})
        except (FileNotFoundError, ValueError):
            continue
    return {"agents": agents}


def control_agent(agent, action):
    """Request pause or resume between desktop tool calls."""
    if action not in ("pause", "resume"):
        raise ValueError("Choose pause or resume.")
    if not any(row["id"] == agent for row in list_agents()["agents"]):
        raise ValueError("Desktop agent is no longer active.")
    marker = root() / agent / "PAUSE"
    if action == "pause":
        marker.touch()
    else:
        marker.unlink(missing_ok=True)
    return {"agent": agent, "action": action}
