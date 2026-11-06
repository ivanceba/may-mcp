# Claude Code

**Claude Code** is the selected Claude variant. It was not installed in the
verification environment on 2026-11-06, so these are setup instructions rather
than a compatibility claim. Claude Desktop, web and API integrations are separate
and remain unverified. See [compatibility](../compatibility.md).

## Local stdio

Install the [locked environment](../../README.md#development-setup). Set the
May URL/key privately in the launching shell and leave writes disabled. Add a
local server from your project directory:

```sh
claude mcp add --transport stdio --scope local may -- uv --directory /absolute/path/to/may-mcp run --frozen may-mcp
```

The server needs `MAY_BASE_URL`, `MAY_API_KEY` and
`MAY_MCP_ALLOW_WRITES=false` in its environment. It does not load `.env` files.
Verify environment forwarding with the installed Claude Code version; do not
put a real key in a CLI argument, project configuration or Git history.
Use an absolute `uv` path if the client cannot resolve it.

Start Claude Code and inspect `/mcp`. Follow the client's project trust and tool
approval flow. Run the [synthetic sequence](../compatibility.md#verification-sequence)
with a disposable May instance before trusting a connection for real data.

## Remote HTTP OAuth

Configure the [authenticated resource server](../authentication.md) and HTTPS
first. The official Claude Code guide documents a public pre-registered client:

```sh
claude mcp add --transport http --scope local --client-id may-claude --callback-port 15062 may-remote https://mcp.example.invalid/mcp
```

Register the exact callback used by the installed version, including host, port
and path. The official guide records a `localhost` versus `127.0.0.1` callback
change between versions, so do not assume they are interchangeable. Authenticate
through `/mcp` and request the configured `may:access` scope. The provider must
issue the correct resource audience and the subject must be enrolled on the MCP
server. Never supply the upstream May API key as an OAuth token.

After changing write mode, restart the server and reconnect the client. Check
14 tools in read-only mode, successful reads, and rejected explicit mutation
calls. A client hiding a tool alone does not prove server-side rejection.

For startup failures check executable paths, environment and stderr without
printing keys. For OAuth failures check verified TLS and exact callback/resource
configuration. Preserve an uncertain write's state by reading before repeating.

Source checked on 2026-11-06:
[official Claude Code MCP guide](https://code.claude.com/docs/en/mcp).
