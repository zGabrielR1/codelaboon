# RC54 improves native task and foreground Desktop recovery

- Native task failures identify the engine and the malformed response field. Invalid final responses and malformed event payloads fail the task, and Codelaboon closes the child output pipe after processing.
- A failed foreground capture invalidates the previous observation and releases the desktop lease. Input with an invalid observation is rejected before opening a desktop backend. Another session can take control, or the same session can capture a fresh frame.
