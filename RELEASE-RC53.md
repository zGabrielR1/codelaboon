# RC53 improves engine recovery and Desktop control

- Managed native engine setup activates the copy that passed checksum and startup verification, including when reinstalling the same version. If verification fails, the previous active copy stays selected.
- Runtime maintenance continues checking and repairing other engines after an engine fails. The update receipt records each outcome and the command reports a failure if any repair failed.
- Desktop lists healthy agents even if another agent has a malformed or disappearing session record. Pause and resume report when their target has already closed.
- Desktop starts a fresh Chromium session when you navigate after a disconnect. If a click, fill, or navigation succeeds and the page snapshot fails, Desktop reports the completed action and lets you refresh the snapshot independently.
