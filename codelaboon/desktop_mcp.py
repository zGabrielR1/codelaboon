"""Stdio MCP server for the Codelaboon desktop actions."""

import argparse
import json
import os
import shlex
import sys

from codelaboon import desktop

NAME = "codelaboon-desktop"
ARGS = ["-m", "codelaboon", "desktop", "mcp"]


def enabled(profile):
    return (profile == "coding" and os.environ.get("CODELABOON_DESKTOP_MCP") == "1"
            and os.environ.get("CODELABOON_HEADLESS_TASK") != "1")


def stdio():
    return {"command": sys.executable, "args": ARGS}


def configure_opencode(config, profile):
    if enabled(profile):
        config.setdefault("mcp", {})[NAME] = {"type": "local", "command": [sys.executable, *ARGS]}


def crush_config():
    return shlex.join(["mcp", "add", NAME, "--type", "stdio", "--command", sys.executable,
                       *[f"--args={arg}" for arg in ARGS]])


def main(argv=None):
    parser = argparse.ArgumentParser(prog="codelaboon desktop")
    parser.add_argument("action", choices=("mcp", "config"))
    parser.add_argument("--engine", choices=("claude", "codex", "opencode", "kilo", "omp", "jcode", "crush"),
                        default="claude", help="Configuration format for the config action")
    args = parser.parse_args(argv)
    if args.action == "config":
        if args.engine == "codex":
            print(f'[mcp_servers.{NAME}]\ncommand = {json.dumps(sys.executable)}\nargs = {json.dumps(ARGS)}')
            return
        if args.engine in ("opencode", "kilo"):
            config = {"mcp": {NAME: {"type": "local", "command": [sys.executable, *ARGS]}}}
        elif args.engine == "crush":
            print(crush_config())
            return
        else:
            config = {"mcpServers": {NAME: stdio()}}
        print(json.dumps(config, indent=2, ensure_ascii=False))
        return
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        parser.exit(1, "Install codelaboon[desktop] to enable the desktop MCP server.\n")

    server = FastMCP("Codelaboon Desktop")
    browser = desktop.Browser()
    for tool in (desktop.run_command, desktop.open_workspace_terminal, desktop.list_tasks,
                 desktop.open_task, desktop.control_task):
        server.add_tool(tool)

    @server.tool()
    def browser_navigate(url: str) -> dict:
        """Open a URL in this workspace's visible browser and return its accessibility snapshot."""
        return browser.call("navigate", url=url)

    @server.tool()
    def browser_snapshot() -> dict:
        """Read the current browser page's accessible content."""
        return browser.call("snapshot")

    @server.tool()
    def browser_click(selector: str) -> dict:
        """Click the element identified by a CSS selector or Playwright locator."""
        return browser.call("click", selector=selector)

    @server.tool()
    def browser_fill(selector: str, text: str) -> dict:
        """Fill an input identified by a CSS selector or Playwright locator."""
        return browser.call("fill", selector=selector, text=text)

    @server.tool()
    def browser_close() -> dict:
        """Close this workspace's browser session."""
        return browser.call("close")

    try:
        server.run(transport="stdio")
    finally:
        browser.close()
