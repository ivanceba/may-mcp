# May HTTP boundary

`Settings.from_env(mapping)` validates one fixed May instance and its API key.
The caller supplies a mapping such as `os.environ`; the library does not read
`.env` files or discover a server automatically. See [.env.example](../../.env.example)
for variable names. The [stdio server](../stdio.md) uses this configuration.

- `MAY_BASE_URL`: HTTP(S) instance URL, optionally with a plain mount prefix such
  as `https://may.example.invalid/may`. Credentials, queries, fragments, percent
  escapes, whitespace, and traversal segments are rejected. A trailing slash is
  normalized. HTTP is allowed for local/self-hosted deployments.
- `MAY_API_KEY`: nonempty printable ASCII token without whitespace. Keep the
  actual value out of committed files. Settings representations omit the key.
- `MAY_MCP_ALLOW_WRITES`: defaults to `false`. Only exact `true` or `false` are
  accepted, including when changing modes. Restart the client/server to apply a
  configuration change.

The immutable Settings constructor enforces the same safety validation, including
requiring a real boolean for `allow_writes` when called directly in Python.

`MayClient(settings, transport=None)` owns an async HTTPX client. Always close it
with `await client.aclose()` in `finally`; repeated closure is safe. The optional
transport supports synthetic HTTP tests. Otherwise normal HTTPS verification is
enabled, the timeout is 30 seconds, and environment proxies are not used.

`await client.request(method, path, params=None, json=None)` returns a JSON object.
Supported methods are GET, POST, PUT, PATCH and DELETE; lowercase is normalized.
Only GET is accepted in the default read-only configuration. Mutations are
rejected before transport access. Use explicit relative paths such as
`/api/v1/vehicles`; the configured mount prefix is preserved. Absolute URLs,
network-relative paths, queries/fragments in paths, escapes, backslashes and
traversal are rejected. Pass query values through `params`. Payload null, zero
and false values are transmitted as supplied.

Requests use the May key in the Authorization Bearer header. Redirects are never
followed, including same-origin redirects. No request is retried automatically.

`MayError` exposes a safe message through `str(error)`, a stable `code`, and
`outcome_unknown`. Response bodies and underlying HTTP exceptions are not echoed
in the message or logs by this client. Codes distinguish invalid requests,
read-only rejection, closed clients, authentication, permission, missing records,
validation, rate limits, upstream failures, redirects, invalid JSON, timeouts and
network failures. May 0.44.2 reports API validation conditions with 400; 422 is
also mapped to validation errors for compatibility.

For a mutation, timeout/network failure, server error, redirect or malformed
successful response has an uncertain outcome: the operation may already have
been saved. The error sets `outcome_unknown=True` and instructs the caller to
verify before repeating. This is conservative; it does not mean a write occurred.
Read failures and explicit 4xx rejections have `outcome_unknown=False`.

This HTTP guard is one layer. When mutating tools are introduced, read-only MCP
discovery must also omit them. Enabling writes never grants extra May account
permissions. The pinned disposable May integration verifies authenticated reads,
invalid credentials, and unchanged data after a blocked write. See the
[testing guide](testing.md) for setup and synthetic-data boundaries.
