---
name: security-fix
description: Use when fixing a finding from the Security Reviewer mode, or any security or privacy issue in the galaxium-travels backend. Writes a failing test first, makes the smallest fix, runs the backend suite, and reports in the team's format.
---

# Security fix: how this team fixes a finding

Follow these steps in order. Don't skip the failing test.
Before you start, make a to-do list with these five steps, using the step names below.
Tick each step off when it is done.

## Step 1: Restate the finding
One line: rule ID (for example SR-1), file and line, and what leaks or breaks.

## Step 2: Prove it with a failing test
Add a test in `booking_system_backend/tests/test_services.py` that fails because of the finding.
For a data leak, assert that the stored value (for example the registered name) does NOT appear
in the error `details`. Run only that test and show that it fails:

```bash
cd booking_system_backend && .venv/bin/python -m pytest -q tests/test_services.py -k <test_name>
```

## Step 3: Make the smallest fix
- Change only what the finding needs.
- Keep every `error_code` value exactly as it is. The REST layer, the MCP tools and the e2e suite depend on them.
- Keep the message helpful to an honest caller, without the stored data. Example: "The name does not match our records for this user ID."

## Step 4: Run the evidence
Run the new test, then the whole backend suite:

```bash
cd booking_system_backend && .venv/bin/python -m pytest -q
```

## Step 5: Report in the team format
A table: Finding | Test added | Fix | Suite result (for example "100 passed").
Then one line: "Ready for review. Not committed."
Don't commit. A person reviews and commits.
