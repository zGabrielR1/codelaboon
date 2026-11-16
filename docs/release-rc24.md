# Codelaboon 1.0.0rc24 - Task model controls and project changes

- Change worker/default swarm-agent models from a task's Models & prompts dialog, terminal Settings view or CLI.
- Choose embedded orchestration, a separate cloud planning model, or a separate local planning model with no cloud fallback. Planner and worker models are independent.
- Customize additive worker and planner system instructions, preserving native defaults and task authority. Every attempt records its captured configuration revision; saved updates take effect at the next eligible checkpoint.
- Capture initial model/prompt settings before a new task is published to the queue. Existing tasks use revision-checked atomic updates.
- Inspect current Git status, diff statistics and a bounded patch in Changes; distinguish pre-existing edits from files observed changing during an attempt.
- Planner failure prevents worker dispatch. Planning and execution share the cycle budget, followed by independent verification. All worker/delegate gateway requests use the selected worker model.

Open a task with `codelaboon tasks` or `codelaboon tasks --open`, then choose Models & prompts / Settings or Changes.

```powershell
codelaboon update
codelaboon tasks TASK_ID --worker-model PROVIDER/MODEL
codelaboon tasks TASK_ID --orchestrator local --orchestrator-model local/MODEL
codelaboon tasks TASK_ID --settings
codelaboon tasks TASK_ID --changes
```

Models must be configured and supported by the selected engine/protocol. Local inference must already be running. Model suggestions do not guarantee live quota. Native parallel pools remain Jcode-specific; separate planning is not a new native worker pool for other engines.

Old running workers need a graceful service restart before accepting execution-setting changes; no active task is automatically modified or restarted. Elevated cases remain immutable and require a new reviewed task/case for settings changes.

[Usage and examples](https://github.com/zGabrielR1/codelaboon/blob/main/docs/rc24-task-models-and-changes.md)
