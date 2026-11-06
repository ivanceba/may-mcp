# Client compatibility

Status recorded on **2026-11-06**, against May **0.44.2** and the locked package
at main commit `9d3747b`. Local tests do not establish public deployment.
The release remains incomplete: [#13](https://github.com/ivanceba/may-mcp/issues/13)
has unresolved API/scope decisions and
[#16](https://github.com/ivanceba/may-mcp/issues/16) requires all three named clients.

## Observed results

- **Codex CLI 0.153.4, Windows, stdio:** verified using the installed native
  app-server MCP client and direct JSON-RPC, with a new isolated `CODEX_HOME`
  for each mode. Discovery returned 29 tools with writes enabled. Calls read the
  synthetic baseline vehicle, created a vehicle, read it, updated its name,
  read the saved change and deleted it. The final list contained only the
  baseline vehicle. A fresh read-only process discovered 14 tools, omitted
  `may_create_vehicle`, rejected an explicit creation request and still allowed
  the subsequent list call. May ran in the disposable test Docker project and
  was removed afterward. No model turn was run: model selection, conversational
  approval behavior, IDE integration and HTTP OAuth remain unverified.
- **ChatGPT, remote Streamable HTTP/OAuth:** unverified. No account/workspace
  connection, client version/build or operation evidence is available.
- **Claude Code, stdio or HTTP/OAuth:** unverified. No installed executable was
  found in the Windows/WSL verification environment; no version or operation
  evidence is available. Claude Desktop, web and API are also unverified.
- **Official Python MCP SDK, stdio and Streamable HTTP/OAuth:** automated
  integration coverage verifies synthetic reads/CRUD, read-only rejection and
  external Keycloak persistence. These are protocol/provider tests, separate
  from the named application results above. See [testing](development/testing.md).

Setup guides: [Codex](clients/codex.md), [ChatGPT](clients/chatgpt.md),
[Claude Code](clients/claude.md). Examples use fictitious values and do not
change an existing deployment or client account.

## Verification sequence

Use only an isolated May instance containing synthetic records. Record the date,
exact client version/build, OS, transport, provider/client registration and tested
package revision. Keep credentials and authorization codes out of the record.

1. Start with `MAY_MCP_ALLOW_WRITES=false`. Discover 14 tools; list and read a
   synthetic vehicle using its returned ID.
2. Restart the server with `true` and reconnect. Discover 29 tools. Create a
   disposable vehicle, read it, update its name, read the persisted change,
   delete it and confirm it is absent from the list. Retain the baseline record.
3. Restart with `false` and reconnect again. Confirm all 15 mutation tools are
   absent. Attempt an explicit mutation call and confirm rejection with no new
   record. Confirm a subsequent read succeeds. If the client cannot make an
   explicit hidden-tool call, record that check as unverified for that client.
4. For HTTP, also record successful OAuth sign-in, scope/audience binding and
   reconnection. Record actual client confirmation and error behavior separately
   from direct RPC or SDK results. Tear down only the disposable services.

Do not retry mutations automatically. Resolve an uncertain outcome by reading
saved state first. Refresh discovery after every server write-mode change;
existing sessions/processes retain startup settings.

## Fresh-checkout gate

A release verification must install from a clean checkout containing tracked
files only, follow the public setup guides and run all required quality, offline,
real-May, OAuth and container checks. Inspect public/staged files for secrets,
personal records and broken links. Ignored local planning files are never a
prerequisite. Record actual commands/results in the PR and update this document
only when new evidence exists. Production deployment needs its own evidence.
