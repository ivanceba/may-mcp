# Remote authentication

The server supports stdio (the default) and explicitly selected, authenticated
Streamable HTTP. HTTP uses an external OAuth authorization server. Provider and
persistence were selected before implementation. Actual ChatGPT, Codex and Claude
connections are tracked separately; SDK protocol tests do not establish those results.

## Selected components and boundaries

- Reference authorization server: **Keycloak 26.8.2**, official image pinned to
  `sha256:3879c623248408de29a5303178b5816c77e8dfef3890c361f8c0bbeaa979ba3b`.
  The [official MCP guide](https://www.keycloak.org/securing-apps/mcp-authz-server)
  describes PKCE, audience/resource binding and client registration.
- Resource server: locked official MCP Python SDK 2.3 interfaces, using
  `TokenVerifier`, protected-resource metadata and Streamable HTTP middleware.
  JWT signature verification uses maintained PyJWT/cryptography, not custom crypto.
- OAuth configuration is separate from the upstream May URL/key/write settings.
  Tokens are for the MCP resource; the May API key never becomes a consumer token
  and is never forwarded to the identity provider.
- Initial data model remains one configured May identity. Every allowed OAuth
  subject receives that identity's access, constrained by global write mode and
  upstream May permissions. This is not per-consumer May isolation.

Production persistence belongs to the external Keycloak deployment and its
supported database (PostgreSQL is the reference production choice). The MCP
resource server is stateless and stores no OAuth registrations, passwords or
refresh tokens. Disposable OAuth tests use a dedicated project-owned Keycloak
H2 data volume, removed after tests, to verify restart behavior. This test database
is not a production database choice. No existing deployment is changed.

The reference test profile uses pre-registered clients, exact loopback test
redirects and PKCE S256. Production clients need exact approved HTTPS callbacks,
or explicitly registered loopback callbacks for local clients. No wildcard
callback policy is introduced. Provider registration choices are external to
the resource server.

Keycloak's `resource-indicators` feature is experimental in this pinned version.
The disposable profile enables it to verify real RFC 8707 target handling;
this is an explicit provider limitation, not a claim of universal OAuth-client
interoperability. Keycloak also documents a scope/audience-mapper profile when
that feature is disabled. Only the tested profile will be claimed as verified.

Access JWTs must be short-lived and are validated for signature, issuer, resource
audience, expiry/not-before, required scope and an explicit allowed-subject list.
Refresh and revocation remain provider operations; a revoked refresh token cannot
mint another access token, while an already-issued self-contained JWT remains
valid until its expiry unless provider signing keys are removed. MCP restarts
require client reconnection but do not erase external provider state.

## Official client requirements checked on 2026-11-05

- [ChatGPT authentication](https://developers.openai.com/plugins/build/auth):
  protected-resource discovery, authorization metadata, PKCE S256 and token
  signature/issuer/resource/expiry/scope checks. Callback and registration mode
  must match the exact connection shown by the client.
- [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp): Streamable HTTP OAuth
  and pre-registered client support are documented. Client-specific configuration
  and actual operation remain an interoperability task.
- [Claude Code MCP](https://code.claude.com/docs/en/mcp): remote OAuth and
  pre-configured client/callback options are documented. Claude Code is the
  selected initial Claude variant; Claude Desktop/web/API are distinct surfaces
  and remain unverified until tested separately.

## Configure and start

Install from the locked environment described in the [README](../README.md).
Set the upstream `MAY_BASE_URL`, `MAY_API_KEY` and optionally
`MAY_MCP_ALLOW_WRITES=true`. The default remains read-only.
Set these separate OAuth environment variables (fictitious examples):

```sh
MAY_MCP_OAUTH_ISSUER=https://sso.example.invalid/realms/may
MAY_MCP_OAUTH_RESOURCE=https://mcp.example.invalid/mcp
MAY_MCP_OAUTH_JWKS_URL=https://sso.example.invalid/realms/may/protocol/openid-connect/certs
MAY_MCP_OAUTH_ALLOWED_SUBJECTS=approved-provider-subject-id
MAY_MCP_OAUTH_SCOPE=may:access
```

Export variables using your shell or process manager, then run:

```sh
uv run --frozen may-mcp --transport http --host 127.0.0.1 --port 8000
```

No `.env` file is loaded automatically. See [the example names](../.env.example).
Allowed subjects are explicit, whitespace-separated provider `sub` identifiers,
not usernames or emails. Enrolling a subject grants access to the configured May
identity, including enabled writes. Changing enrollment/configuration requires a
resource-server restart. OAuth authorization does not create separate May accounts.

All configured OAuth URLs require HTTPS and reject credentials, query strings,
fragments and ambiguous path segments. The resource URL must have a nonempty path
without a trailing slash. `MAY_MCP_OAUTH_ALLOW_LOOPBACK_HTTP=true` is an explicit
test exception for numeric loopback HTTP URLs only, never public/LAN hosts.
The real Keycloak integration tests use HTTPS with a freshly generated test
certificate verified through an isolated trust context, not that exception.

Terminate public HTTPS at your trusted reverse proxy and preserve the public
`Host` header. Bind the backend to loopback or a private container network.
The app uses its fixed configured URLs, ignores forwarded headers, checks Host
and MCP Origin, and does not enable wildcard credentialed CORS. The public OAuth
metadata is served at `/.well-known/oauth-protected-resource/mcp` for the example
resource. Anonymous MCP requests receive 401 with its `resource_metadata` link;
valid tokens missing the configured scope receive 403. No upstream May request
is sent until MCP authorization succeeds.

## Reference provider configuration

In an independently managed Keycloak realm:

1. Configure production HTTPS and durable provider storage. Do not deploy the
   `start-dev`/H2 test profile as a production identity service.
2. Enable the explicitly experimental `resource-indicators` feature if using
   this tested resource-indicator profile. Represent the MCP resource as a
   Keycloak client with `resource_url` equal to the exact public MCP resource URI.
3. Register each consumer with its exact callback URI and PKCE S256. An audience
   mapper on that consumer targets the resource client. Make the `may:access`
   scope available to the consumer and request it during authorization.
   Ensure access tokens include `sub`: retain Keycloak's `basic` client scope or
   configure its [Subject mapper](https://www.keycloak.org/admin-api/protocol-mappers)
   explicitly as in the synthetic realm. Tokens without a subject are rejected.
4. Configure the provider's RS256 signing keys, short access-token lifespan and
   refresh-token rotation/revocation policy. Copy its canonical issuer and
   `jwks_uri` from its OIDC discovery document into the MCP configuration.
5. Enroll the approved subject IDs in the MCP allowlist. Use the consumer's
   actual registration options; the resource server performs no dynamic client
   registration or authorization-code exchange itself.

The committed [synthetic realm](../tests/fixtures/oauth-realm.json) demonstrates
the reference audience/scope/PKCE wiring with fictitious accounts and exact test
callbacks. It is not a production realm template or a named-client configuration.

## Token handling and lifecycle

The resource accepts RS256 JWT access tokens only. It verifies signature, exact
issuer, resource audience, expiry, not-before when present, subject enrollment
and the required scope, using maintained PyJWT/cryptography and SDK middleware.
Client identity and issuer/subject are passed into the SDK's principal model.
A raw May API key cannot authenticate to MCP. Conversely, the configured May key
is the only upstream Bearer credential; consumer OAuth tokens are never forwarded
to May and May keys are never sent to the identity provider.

The fixed JWKS URL is the only key-fetch endpoint; token-provided key URLs are
not followed. Fetches have a five-second timeout, no redirects/proxy inheritance,
a 128 KiB body limit and at most 100 keys. Keys cache for 60 seconds, including a
failure backoff and unknown-key throttling. Removed keys can remain usable during
that window; a newly introduced key can require up to 60 seconds before acceptance.
Expired cache entries fail closed when refresh fails. Plan signing-key rotation
with an overlap longer than this interval; never expect immediate key revocation.

The disposable integration suite exercises authorization code with S256, incorrect
proof, code reuse, incorrect callback/resource, refresh-token rotation/reuse,
refresh revocation, access-token expiry, persisted provider restart and new
resource-app instances. A revoked refresh token cannot refresh; already-issued
access JWTs remain valid until expiry subject to signing-key cache behavior.
MCP restarts require reconnection and retain no OAuth database. Standard app
shutdown closes the owned May and JWKS HTTP clients once. HTTP access logging is
disabled; configuration/authentication errors do not include credential values.

Run [the documented OAuth tests](development/testing.md#oauth-checks) to verify
the selected profile. Public deployment and individual consumer registration,
discovery, CRUD and reconnection remain separate verification requirements.
