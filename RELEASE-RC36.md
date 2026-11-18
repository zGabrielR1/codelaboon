# RC36 adds Linux app regression verification

Codelaboon can build a native app from a pinned Git revision, launch it on a
private Linux display, and reproduce a failure using a saved accessibility
flow. After the repair, the worker builds and launches the app again and runs
the same flow before accepting the result.

- **App verification** in the task view shows the live step and display. You
  can take over and click in the preview. Returning control relaunches the app
  and starts verification from a clean state.
- The handoff includes a patch, check results, and before-and-after
  screenshots. Repairs survive retries in a detached Git worktree. Regression
  jobs can switch to configured fallback models after provider throttling.
- Continuous coding swarms can also opt into foreground desktop tools.
  Native desktop access depends on platform support and user permissions.

## Install and try it

```sh
python -m pip install 'codelaboon[native-desktop] @ https://github.com/zGabrielR1/codelaboon/releases/download/v1.0.0-rc.36/codelaboon-1.0.0rc36-py3-none-any.whl'
codelaboon regression 'Fix the result shown by the app' --gui-spec flow.json
codelaboon regression --report TASK_ID
```

Linux GUI verification requires Xvfb, xauth, dbus-run-session, Pillow with XCB
support, and system PyGObject with AT-SPI. Launch the app process directly and
use accessible control names in the flow. Restart an existing supervisor
after upgrading.

See [the GUI flow example and desktop setup](README.md#build-launch-and-verify-a-linux-app).
