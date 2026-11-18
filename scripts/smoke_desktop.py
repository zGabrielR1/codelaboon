"""Exercise desktop actions through both HTTP and a real stdio MCP client."""

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import Mock, patch

import requests
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from codelaboon.web import create_server
from codelaboon import work


class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"""<title>Desktop smoke</title><h1>Desktop smoke</h1>
            <label>Note <input id="note"></label><a href="/next">Next page</a>""")


def start(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return f"http://127.0.0.1:{server.server_port}"


def check_web(url, page, task):
    token = requests.get(url + "/api/session", timeout=5).json()["token"]
    headers = {"X-Codelaboon-Token": token}
    assert requests.get(url + "/desktop", timeout=5).ok
    queue = requests.get(url + "/api/tasks", headers=headers, timeout=5).json()
    assert queue["tasks"][0]["id"] == task
    assert requests.post(url + "/api/desktop", json={"action": "terminal"}, timeout=5).status_code == 403

    def call(action, **arguments):
        response = requests.post(url + "/api/desktop", headers=headers,
                                 json={"action": action, **arguments}, timeout=45)
        assert response.ok, response.text
        return response.json()

    assert call("command", argv=[sys.executable, "-c", "print('desktop command')"])["output"].strip() == "desktop command"
    executable = "wt.exe" if os.name == "nt" else "x-terminal-emulator"
    with patch("codelaboon.task_launch.shutil.which", return_value=executable), patch(
        "codelaboon.task_launch.subprocess.Popen"
    ) as launch:
        call("terminal")
        assert launch.call_args.args[0][0] == executable
        assert Path(launch.call_args.kwargs["cwd"]) == Path.cwd()
    assert "Desktop smoke" in call("navigate", url=page)["snapshot"]
    assert "web note" in call("fill", selector="#note", text="web note")["snapshot"]
    assert call("click", selector="a")["url"].endswith("/next")
    assert "Desktop smoke" in call("snapshot")["snapshot"]
    call("close")


async def check_mcp(page, task):
    parameters = StdioServerParameters(
        command=sys.executable, args=["-m", "codelaboon", "desktop", "mcp"],
        env=dict(os.environ), cwd=str(Path(__file__).resolve().parents[1]),
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()
            tools = {tool.name for tool in (await client.list_tools()).tools}
            assert {"run_command", "open_workspace_terminal", "open_task", "control_task",
                    "list_tasks", "browser_navigate"} <= tools

            async def call(name, **arguments):
                result = await client.call_tool(name, arguments=arguments)
                assert not result.isError, result.content
                return result.structuredContent or json.loads(result.content[0].text)

            assert (await call("list_tasks"))["tasks"][0]["id"] == task
            assert (await call("control_task", task=task, action="pause"))["action"] == "pause"
            assert (await call("list_tasks"))["tasks"][0]["state"] == "paused"
            assert (await call("control_task", task=task, action="resume"))["action"] == "resume"
            result = await call("run_command", argv=[sys.executable, "-c", "print('mcp command')"])
            assert result["output"].strip() == "mcp command"
            assert "Desktop smoke" in (await call("browser_navigate", url=page))["snapshot"]
            assert "mcp note" in (await call("browser_fill", selector="#note", text="mcp note"))["snapshot"]
            assert (await call("browser_click", selector="a"))["url"].endswith("/next")
            await call("browser_close")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as config:
        os.environ["CODELABOON_CONFIG_DIR"] = config
        work.initialize(Path(config) / "work.json")
        task = work.add(config, "Desktop smoke task", [[sys.executable, "-c", "pass"]])
        with ThreadingHTTPServer(("127.0.0.1", 0), Page) as site, create_server(0, Mock()) as web:
            page, workspace = start(site), start(web)
            try:
                check_web(workspace, page, task)
                asyncio.run(check_mcp(page, task))
            finally:
                web.shutdown()
                site.shutdown()
    print("Desktop HTTP and MCP smoke passed.")
