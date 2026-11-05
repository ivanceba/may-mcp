# Container deployment

The image packages the MCP resource server. An independently managed OAuth
provider and May instance are required. No production service is deployed by
building or testing this repository. Named application interoperability remains
a separate [delivery task](https://github.com/ivanceba/may-mcp/issues/16).

## Image and runtime

[Dockerfile](../Dockerfile) pins official Python 3.12.13 and uv 0.11.8 images by
digest. The builder validates the committed lockfile and installs a non-editable
package without development dependencies. The final stage contains the runtime
virtual environment, not the builder's source tree, uv cache or test tools.
It runs as UID/GID `10001:10001` and serves HTTP on port 8000 by default.

The [build allowlist](../.dockerignore) admits only package/build inputs. It
excludes environment files, local data, Git metadata, caches, tests, agent state
and ignored planning artifacts. Do not add credentials to Python source or build
arguments. Keys/tokens are runtime configuration and are never build inputs.

```sh
docker build -t may-mcp:local .
```

Build/test images and BuildKit caches are local artifacts; this does not publish
an image registry release. Upgrade base/dependency pins through reviewed changes
and rerun the integration suite.

## Configure HTTP behind HTTPS

Follow [authentication](authentication.md) to configure the external provider,
exact consumer callbacks, resource audience, scopes and approved subjects. Set
the names from [the environment example](../.env.example) in your process manager
or a protected runtime-only file such as `.env.runtime`. Keep that file private
(owner-only permissions on Linux) and out of Git. Docker administrators can
inspect runtime environment values; do not print full container inspection or
interpolated Compose configuration into logs.

[compose.example.yml](../compose.example.yml) starts only the MCP service:

```sh
docker compose --env-file .env.runtime -f compose.example.yml config --quiet
docker compose --env-file .env.runtime -f compose.example.yml up -d --build
docker compose --env-file .env.runtime -f compose.example.yml ps
```

The example binds to host loopback `127.0.0.1:8000`, uses a read-only root
filesystem, a bounded temporary filesystem, drops capabilities and disallows
privilege escalation. Its default write mode is `false`. Run a trusted HTTPS
reverse proxy in front of this backend and preserve the configured public Host
header. For a containerized proxy, attach it to the same private Docker network
and address service `may-mcp:8000`; do not expose cleartext port 8000 publicly.
The public MCP resource URL remains HTTPS. Proxy headers cannot override the
configured issuer, resource, allowed Host or Origin.

The probe and example assume the documented internal port 8000. If you override
the server's listening port, update the healthcheck along with it. Do not add
OAuth credentials to a probe command. Public metadata access alone does not
prove successful upstream May authentication or a working consumer connection.

## Health and shutdown

The image's healthcheck requests the SDK's public protected-resource metadata on
fixed loopback port 8000, with Host derived from the public resource URI. It
requires HTTP 200 and matching resource metadata. It reads no May API key or
consumer token, follows no redirects, ignores proxy environment variables and
times out after two seconds. Missing/invalid public resource configuration or an
unresponsive listener makes the probe fail silently.

The production image probes every 15 seconds, allows a 10-second startup period,
and marks unhealthy after three failures. The integration suite overrides only
the timing to observe healthy → unresponsive → unhealthy → recovered.
Docker health status alone does not restart an unhealthy container; the example's
restart policy applies to exited processes. Select monitoring/orchestration
behavior explicitly if automatic unhealthy-service replacement is needed.

SIGTERM uses Uvicorn's standard graceful shutdown and the app lifespan closes its
owned May/JWKS clients. Uvicorn then re-raises the signal, so Docker exit `143`
is an expected terminated process, not evidence of SIGKILL. The example grants
20 seconds for shutdown; tests reject forced-kill/OOM exits. Restarting recreates
MCP sessions; clients must reconnect and rediscover the tool catalogue.

## Persistence and write-mode changes

The MCP container is stateless: it needs no persistent data/auth volume. May data
and permission rules remain in the independently managed May deployment. OAuth
users, signing keys, client registrations, refresh state and sessions belong to
the external provider and its supported database.

The reference production provider uses Keycloak with PostgreSQL. Give that
separate identity project its own named database volume, for example
`may-mcp-identity-postgres-data`, and configure/test its backups and restore
procedure. This is an example reference name; the MCP Compose file neither
creates nor removes an identity database volume. Retain that external storage
when restarting/recreating MCP. Never repoint tests at an existing May/IdP
database or remove another deployment's volumes. The disposable H2 test volume
is not a production persistence choice.

Changing environment configuration requires recreating the container:

```sh
docker compose --env-file .env.runtime -f compose.example.yml up -d --force-recreate
```

Set `MAY_MCP_ALLOW_WRITES` to exactly `true` or `false`, then reconnect clients.
Plain `restart` retains the existing container environment. Neither mode changes
nor restarts grant additional upstream May permissions. Every enrolled consumer
still shares the configured May identity; per-consumer May accounts are not implied.

## Stdio from the image

To use the image as a local stdio server, inherit the upstream settings from a
protected caller environment and disable the HTTP-only healthcheck. Keep stdin
open and avoid a TTY:

```sh
docker run --rm -i --no-healthcheck \
  --env MAY_BASE_URL --env MAY_API_KEY --env MAY_MCP_ALLOW_WRITES \
  may-mcp:local --transport stdio
```

The caller's May URL must be reachable from the container. The default local
host loopback does not refer to the host from inside Docker. No OAuth settings
are required for stdio; do not place an upstream key directly in a command line.

## Verification and cleanup

Follow [the testing guide](development/testing.md) to build the image, inspect
the real filtered build context, run HTTP/OAuth and stdio against synthetic May,
verify modes after restart, and exercise health and shutdown. These checks use
reserved disposable container names prefixed `may-mcp-package-test` and port
`127.0.0.1:15070`; do not run suites concurrently against those names.
The fixtures refuse existing test containers and remove what they create.
Base images/BuildKit caches may remain. No public domain, TLS proxy, registry
release, production volumes or real client settings are changed by these tests.
