# RC49 keeps the router idle for unavailable projects

The background service and supervisor resolve inbox task project paths relative to the worker configuration directory. If a task's project directory is unavailable, the task stays visible and controllable without starting the local router. Restoring the directory lets the task become runnable again.

RC49 also includes the changes developed in RC46 through RC48 since the previous published candidate.

- Web Chat opens on Free (Auto). Connections handles sign-in and API keys, and Desktop groups terminal, browser, and desktop controls.
- The task supervisor and controls share inbox validation. Malformed records are skipped and the supervisor logs why it rejected them.
- The terminal task view handles rows being removed during refresh, and the README starts with setup and launch instructions.
