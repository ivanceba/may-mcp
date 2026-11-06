# Codex

The verified surface is **Codex CLI 0.153.4 on Windows, stdio**, using its
app-server MCP client directly. See [compatibility](../compatibility.md) for the
observed operations and limits. IDE integration, model tool selection and remote
OAuth have not been verified with this package.

## Local stdio

Install the [locked environment](../../README.md#development-setup). Set
`MAY_BASE_URL`, `MAY_API_KEY` and `MAY_MCP_ALLOW_WRITES=false` in the environment
that starts Codex. The server does not load `.env` files. Keep the key out of
shell history and committed configuration.

Add this entry to your private Codex `config.toml`, replacing the clone path:

```toml
[mcp_servers.may]
command = "uv"
args = ["--directory", "/absolute/path/to/may-mcp", "run", "--frozen", "may-mcp"]
env_vars = ["MAY_BASE_URL", "MAY_API_KEY", "MAY_MCP_ALLOW_WRITES"]
```

On Windows, use a forward-slash absolute path such as `C:/Projects/may-mcp`.
The `uv` executable must be on the client's PATH; an absolute executable path
also works. For an isolated check, set `CODEX_HOME` to a new private directory
before starting Codex and put `config.toml` there. This keeps the check separate
from existing client configuration and credentials.

Restart the client and inspect `/mcp`. The default server catalogue contains
14 read tools. Ask it to call `may_list_vehicles`, then `may_get_vehicle` using
an ID returned by the list. Client approval policies still apply.

Only on a disposable May instance, restart with `MAY_MCP_ALLOW_WRITES=true` to
expose 29 tools and run the [synthetic verification sequence](../compatibility.md#verification-sequence).
Restart with `false` afterward and reconnect; an existing process retains its
startup configuration. Confirm that mutations disappear and explicit calls fail.

## Remote HTTP OAuth: instructions, not a verified result

First configure the [resource server and provider](../authentication.md) behind
[HTTPS](../deployment.md). Use a dedicated public OAuth client with PKCE S256.
With a real URL and pre-registered client ID, the installed CLI supports:

```sh
codex mcp add may-remote --url https://mcp.example.invalid/mcp --oauth-client-id may-codex
codex mcp login may-remote --scopes may:access
```

Register the exact callback printed by your client. Use a fixed callback listener
port when the provider requires exact port matching. The MCP resource URI,
audience, requested scope and allowed provider subject must match the server.
The May API key belongs only on the resource server, never in the OAuth login.

These commands were checked in 0.153.4 help; an OAuth connection was not run.
That version does not list the newer `--oauth-client-secret` flag. Check installed
help before following examples for another version. See the
[official Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp)
for callback and registration settings.

## Troubleshooting

- Startup failure: check the absolute clone/executable path and environment in the
  process launching Codex. Run `uv sync --locked` from the clone first.
- Missing mutations: check write mode on the server, then restart and rediscover.
- OAuth failure: inspect metadata, TLS trust, exact callbacks, issuer, audience,
  scope and subject enrollment. Do not disable certificate or token validation.
- A timeout during a write can leave an uncertain outcome. Read the affected
  record before deciding whether to repeat the operation; writes are not retried.
