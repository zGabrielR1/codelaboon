# RC57 recovers tasks with missing plans

- The scheduler requests a fresh plan when the saved plan is missing, unreadable, or blank. Build workers receive the replacement plan, and the task keeps its existing progress and verification requirements.
