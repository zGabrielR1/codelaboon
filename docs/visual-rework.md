# Taste framework visual rework

Direction: Data terminal, seed 661241449. Existing system typography retained explicitly (--keep type), so the local app requires no remote font request. No style redraws.

Screen question: which model am I using, and what do I want to work on next?
Face: original whale/code mark and mint selection line. Signature: persistent provider/model pair immediately above the writing canvas.

Inventory: six existing providers; account-specific model names; saved conversations; active/archive history; browser-local drafts; ChatGPT login; code messages; private loopback workspace. All displayed counts derive from the actual conversation array.

Changes: 52px navigation rail, 248px library, neutral dark canvas, left-aligned home, starter rows, consistent 11px minimum text, mobile actions menu, and aligned terminal colors/spacing. No gradients or external assets.

Verification: taste source lint 0 FAIL / 0 WARN. Framework inspector failed with CDP timeout Page.enable; no successful inspector result is claimed. Browser fallback verified 1440/768/390 layouts, no horizontal overflow, tablet library toggling, mobile actions menu, starter prompts, fixture chat and fenced code. Inspected dark desktop and mobile screenshots. 60 offline tests pass.

Critique: writing and model selection remain primary; content and composer share a bounded reading width. Empty history retains its purpose with a message. Phone navigation folds without hiding conversation actions. No charts or fabricated metrics. Lint exceptions: none.
