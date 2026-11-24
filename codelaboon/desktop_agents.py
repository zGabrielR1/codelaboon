"""Local desktop-agent presence and cooperative controls."""
import errno
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


def task_state(directory):
    if directory is None:
        return None
    if (directory / "STOP").exists() or (directory / "DELETED.json").exists():
        return "stopped"
    if (directory / "PAUSE").exists():
        return "paused"
    return None


class Agent:
    def __init__(self, task=None, task_control=None):
        self.task_control = task_control
        self.id = uuid.uuid4().hex
        self.directory = root() / self.id
        self.directory.mkdir(parents=True, mode=0o700)
        self.lock = (self.directory / "live.lock").open("a+b")
        pending = self.directory / "agent.tmp"
        try:
            acquire(self.lock)
            pending.write_text(
                json.dumps({"id": self.id, "task": task, "project": str(Path.cwd()),
                            "task_control": str(task_control) if task_control else None}), encoding="utf-8"
            )
            pending.replace(self.directory / "agent.json")
        except OSError:
            self.close()
            raise

    def check(self):
        state = task_state(self.task_control)
        if state:
            raise ValueError(f"The linked task is {state}. Desktop tools are unavailable.")
        if (self.directory / "PAUSE").exists():
            raise ValueError("This desktop agent is paused. Resume it from Tasks or another agent.")

    def close(self):
        try:
            (self.directory / "agent.json").unlink(missing_ok=True)
        finally:
            self.lock.close()
        for name in ("live.lock", "PAUSE", "agent.tmp"):
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
                except OSError as error:
                    if error.errno not in (errno.EACCES, errno.EAGAIN):
                        continue
                else:
                    continue
                row = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(row, dict) or row.get("id") != path.parent.name:
                    continue
                directory = row.pop("task_control", None)
                if directory is not None and not isinstance(directory, str):
                    continue
                agents.append({**row, "paused": (path.parent / "PAUSE").exists(),
                               "task_state": task_state(Path(directory)) if directory else None})
        except (OSError, ValueError):
            continue
    return {"agents": agents}


def control_agent(agent, action):
    """Request pause or resume between desktop tool calls."""
    if action not in ("pause", "resume"):
        raise ValueError("Choose pause or resume.")
    if not any(row["id"] == agent for row in list_agents()["agents"]):
        raise ValueError("Desktop agent is no longer active.")
    marker = root() / agent / "PAUSE"
    try:
        if action == "pause":
            marker.touch()
        else:
            marker.unlink(missing_ok=True)
    except FileNotFoundError:
        raise ValueError("Desktop agent is no longer active.") from None
    if not (marker.parent / "agent.json").exists():
        marker.unlink(missing_ok=True)
        raise ValueError("Desktop agent is no longer active.")
    return {"agent": agent, "action": action}
