# Galaxium Travels security review checklist

Written by the team lead. Apply every rule to every review. Cite the rule ID for each finding.

## SR-1 Never give back personal data the caller didn't send
Error messages, `details` fields and MCP tool results must not hand back stored personal data
that the caller did not send, such as a registered name or email address. A caller who sends a
wrong value must not learn the right one. This counts for REST responses and MCP tool results
alike, because both return the same `ErrorResponse`.

## SR-2 No secrets in the repository
No passwords, API keys, tokens or connection strings with credentials in code, scripts or config.

## SR-3 A failure must look like a failure
New code that calls the Java hold service must not turn an error into HTTP 200.
The existing proxy endpoints in `server.py` already do this and are known (see AGENTS.md).
Report them once as KNOWN, not as BLOCK.

## SR-4 Known and accepted: this demo app has no real authentication
Sign-in uses only a name and an email, with no password, and the API does not check who is calling.
Endpoints that return data for the ID the caller sends (for example GET /bookings/{user_id}) are
part of this known gap. Report them together in one KNOWN row, not as BLOCK.
An error message that reveals stored data the caller did not send is still SR-1.

## How to report
1. One line: how many findings, and whether the change can ship.
2. A table: Rule | File:line | What leaks or breaks | Verdict (BLOCK / KNOWN / OK).
3. For each BLOCK, one sentence on the smallest fix.
Don't edit files. Don't pad the review with praise.
