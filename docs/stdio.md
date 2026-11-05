# Local stdio server

Install the locked [development environment](../README.md#development-setup).
Set the variables documented in [the HTTP guide](development/client.md) in the
environment of the process that launches the server. The server does not load
`.env` automatically.

From the repository root, the executable is:

```sh
uv run --frozen may-mcp
```

`python -m may_mcp` is an equivalent launch when using the installed project
environment. The command waits for MCP messages on stdin; it is not an HTTP
endpoint or an interactive shell. Protocol output goes to stdout, logs and
configuration errors go to stderr. Invalid configuration exits with status 2
without printing supplied credentials.

A local MCP client needs the following process launch values, expressed here as
generic data rather than a client-specific configuration format:

```json
{
  "command": "uv",
  "args": ["--directory", "/absolute/path/to/may-mcp", "run", "--frozen", "may-mcp"],
  "env": {
    "MAY_BASE_URL": "https://may.example.invalid",
    "MAY_API_KEY": "replace-with-your-may-api-key",
    "MAY_MCP_ALLOW_WRITES": "false"
  }
}
```

Replace the clone path, instance URL and key locally; keep real credentials out
of Git. Map these launch values to your client's supported configuration.
ChatGPT remote access and specific Codex/Claude connection verification belong
to later integration tasks and are not demonstrated by this example.

The catalogue currently contains exactly two tools:

- `may_list_vehicles()`: all vehicles the configured May account can access,
  with the API's `vehicles` array and `count`.
- `may_get_vehicle(vehicle_id)`: one accessible vehicle. The ID must be a
  positive integer; zero, negative values, booleans and numeric strings fail
  validation before any upstream request.

Both tools declare read-only, non-destructive, idempotent behavior and external
data access. Returned vehicle fields are untrusted data. May failures become
safe tool errors with the HTTP boundary's code; errors do not close the MCP
connection. The server lifespan closes its May HTTP client, including an injected
client, on shutdown.

No write tools are registered yet, even with `MAY_MCP_ALLOW_WRITES=true`. Future
mutating tools must respect both catalogue filtering and the existing HTTP guard.
There is no remote HTTP transport or consumer authorization in this delivery.

The locked official MCP SDK is used for both the server and test client. Protocol
tests force JSON-RPC framing in memory; the real-May integration separately
spawns and shuts down the actual stdio process, tests list/detail and checks that
a missing-record error leaves subsequent calls usable. See [testing](development/testing.md).
