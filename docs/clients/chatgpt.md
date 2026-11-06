# ChatGPT remote connection

**Unverified:** no ChatGPT account/workspace connection or tool execution has
been recorded for this package. SDK HTTP/OAuth tests do not establish ChatGPT
compatibility. See [compatibility](../compatibility.md).

## Prerequisites

Configure the [OAuth resource server](../authentication.md), a reachable HTTPS
endpoint such as `https://mcp.example.invalid/mcp`, and the external provider's
durable storage. Keep the May key on the resource server. Enroll only the
intended provider subjects; all of them access the same configured May identity.

Use a separate disposable May instance and synthetic records for acceptance
testing. Confirm your ChatGPT account/workspace allows custom MCP connections.
Select the registration mode supported by both the client UI and provider;
the reference tests exercise pre-registered clients, not CIMD or DCR. Register
the exact callback supplied by ChatGPT and use PKCE S256, the resource audience
and `may:access` scope.

## Connect and verify

1. Open ChatGPT's custom MCP connection flow. In the current official guide this
   is under Plugins, plus, Add custom MCP server; account UI and policies vary.
2. Enter the server URL and choose OAuth. Configure the matching provider client
   registration, then complete the provider's sign-in and consent flow.
   Create and install the resulting plugin, then select it with `@` in a new
   conversation before requesting tool execution.
3. Inspect the discovered tools. Start read-only: expect 14 tools and successful
   `may_list_vehicles` / `may_get_vehicle` calls on synthetic data.
4. For the disposable instance only, restart the MCP server with writes enabled,
   reconnect and run the [verification sequence](../compatibility.md#verification-sequence).
   Review the client's confirmation before each mutation.
5. Restart with writes disabled and create a fresh connection/catalogue. Verify
   mutations are absent and explicitly requested mutations fail. Record the
   actual selected tools, arguments, results and confirmation behavior.

The official guide also offers Secure MCP Tunnel for private servers. That route
has not been configured or tested here and does not establish OAuth compatibility
with this package. Do not expose a cleartext development port to the internet.

## Troubleshooting

Check public metadata and the anonymous 401 challenge before diagnosing login.
Then check provider discovery, trusted HTTPS, callback matching, token audience,
scope and enrolled subject. Reverse proxies must preserve the configured public
Host. A successful health probe alone does not prove an authenticated connection.

Client permission and confirmation do not override the server's write setting
or May ownership rules. After a timed-out mutation, read the resulting state
before repeating it. Keep tokens, keys and real records out of shared evidence.

Sources checked on 2026-11-06:
[connection guide](https://developers.openai.com/plugins/deploy/connect-chatgpt),
[OAuth guide](https://developers.openai.com/plugins/build/auth).
