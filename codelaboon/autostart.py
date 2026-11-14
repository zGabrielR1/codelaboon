"""User-level background service registration; no administrator install required."""
import os
import getpass
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
from xml.sax.saxutils import escape

from codelaboon.paths import config_dir


def specification(config, system=None):
    system = system or platform.system()
    argv = [sys.executable, "-m", "codelaboon.service", str(Path(config).resolve())]
    if any("\n" in item or "\r" in item for item in argv):
        raise ValueError("Service paths must not contain line breaks")
    source = str(Path(__file__).resolve().parent.parent)
    if system == "Linux":
        def quote(value):
            return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"'
        content = ("[Unit]\nDescription=Codelaboon background agent\nAfter=network-online.target\n"
                   "[Service]\nType=simple\nRestart=on-failure\nRestartSec=10\n"
                   f"WorkingDirectory={source.replace('%', '%%')}\nExecStart={' '.join(map(quote, argv))}\n"
                   "[Install]\nWantedBy=default.target\n")
        return "codelaboon.service", content.encode()
    if system == "Darwin":
        return "local.codelaboon.agent.plist", plistlib.dumps({
            "Label": "local.codelaboon.agent", "ProgramArguments": argv,
            "WorkingDirectory": source, "RunAtLoad": True, "KeepAlive": {"SuccessfulExit": False}})
    if system == "Windows":
        command = escape(argv[0])
        arguments = escape(subprocess.list2cmdline(argv[1:]))
        user = getpass.getuser()
        domain = os.environ.get("USERDOMAIN")
        identity = escape(f"{domain}\\{user}" if domain else user)
        content = (f'<?xml version="1.0" encoding="UTF-8"?>'
                   '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
                   f'<Triggers><LogonTrigger><Enabled>true</Enabled><UserId>{identity}</UserId></LogonTrigger></Triggers>'
                   f'<Principals><Principal id="Owner"><UserId>{identity}</UserId>'
                   '<LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>'
                   '<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>'
                   '<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>'
                   '<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>'
                   '<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>'
                   '<RestartOnFailure><Interval>PT1M</Interval><Count>999</Count></RestartOnFailure></Settings>'
                   f'<Actions Context="Owner"><Exec><Command>{command}</Command><Arguments>{arguments}</Arguments>'
                   f'<WorkingDirectory>{escape(source)}</WorkingDirectory></Exec></Actions></Task>')
        return "codelaboon.xml", content.encode()
    raise ValueError("Autostart supports Linux, macOS, and Windows")


def enable(config):
    system = platform.system()
    name, content = specification(config, system)
    directory = config_dir() / "autostart"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    target.write_bytes(content)
    if system == "Linux":
        if shutil.which("systemd-analyze"):
            subprocess.run(["systemd-analyze", "--user", "verify", str(target)], check=True)
        subprocess.run(["systemctl", "--user", "link", str(target)], check=True)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", name], check=True)
        subprocess.run(["loginctl", "enable-linger", getpass.getuser()], check=True)
    elif system == "Darwin":
        # launchd loads from this persistent per-user location at login.
        destination = Path.home() / "Library/LaunchAgents" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(destination)], check=True)
    else:
        subprocess.run(["schtasks", "/Create", "/TN", "Codelaboon Agent", "/XML", str(target), "/F"], check=True)
        subprocess.run(["schtasks", "/Run", "/TN", "Codelaboon Agent"], check=True)
    return target


def disable():
    system = platform.system()
    if system == "Linux":
        subprocess.run(["systemctl", "--user", "disable", "--now", "codelaboon.service"], check=True)
    elif system == "Darwin":
        target = Path.home() / "Library/LaunchAgents/local.codelaboon.agent.plist"
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(target)], check=True)
        target.unlink(missing_ok=True)
    elif system == "Windows":
        subprocess.run(["schtasks", "/End", "/TN", "Codelaboon Agent"], check=False)
        subprocess.run(["schtasks", "/Delete", "/TN", "Codelaboon Agent", "/F"], check=True)
    else:
        raise ValueError("Unsupported platform")
