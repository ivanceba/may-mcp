"""Real ASGI authorization boundary before any May network call."""

import httpx
import httpx2
import pytest
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client

from may_mcp.auth import JWTVerifier, OAuthSettings
from may_mcp.client import MayClient
from may_mcp.errors import MayError
from may_mcp.server import create_http_app


async def test_http_requires_oauth_before_mcp_initialization(settings_factory):
    calls = []
    settings = settings_factory()
    may = MayClient(settings, transport=httpx.MockTransport(lambda request: calls.append(request)))
    oauth = OAuthSettings(
        "https://idp.invalid/realms/test",
        "https://mcp.example.invalid/mcp",
        "https://idp.invalid/jwks",
        frozenset({"synthetic-user"}),
    )
    app = create_http_app(settings, oauth, may_client=may)
    try:
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="https://mcp.example.invalid"
            ) as client,
        ):
            response = await client.post(
                "/mcp",
                headers={"Accept": "application/json, text/event-stream"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "synthetic-http-test", "version": "1"},
                    },
                },
            )
        assert response.status_code == 401
        assert "resource_metadata" in response.headers["WWW-Authenticate"]
        assert calls == []
    finally:
        await may.aclose()


@pytest.mark.parametrize("writes", [False, True])
async def test_authenticated_http_tools_and_lifespan(
    settings_factory, oauth_settings, signed_tokens, synthetic_vehicle, writes
):
    token, keys = signed_tokens
    requests = []
    settings = settings_factory(MAY_MCP_ALLOW_WRITES="true" if writes else "false")

    def handler(request):
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer synthetic-test-key"
        return httpx.Response(200, json=synthetic_vehicle)

    may = MayClient(settings, transport=httpx.MockTransport(handler))
    verifier = JWTVerifier(
        oauth_settings,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=keys)),
    )
    app = create_http_app(settings, oauth_settings, may_client=may, verifier=verifier)
    async with app.router.lifespan_context(app):
        # SDK's HTTP transport exercises serialized MCP through the real ASGI app.
        async with (
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app), headers={"Authorization": "Bearer " + token()}
            ) as http,
            Client(
                streamable_http_client(oauth_settings.resource_url, http_client=http),
                mode="legacy",
                cache=None,
            ) as client,
        ):
            tools = await client.list_tools()
            assert ("may_delete_vehicle" in {t.name for t in tools.tools}) is writes
            for _ in range(2):
                result = await client.call_tool("may_get_vehicle", {"vehicle_id": 1})
                assert result.is_error is not True
                assert result.structured_content["name"] == "MCP synthetic vehicle"
            result = await client.call_tool("may_delete_vehicle", {"vehicle_id": 1})
            assert (result.is_error is True) is (not writes)
            assert len(requests) == (3 if writes else 2)
        # A new MCP connection must not encounter a client closed by the previous one.
        assert (await may.request("GET", "/api/v1/vehicles/1"))["id"] == 1
    with pytest.raises(MayError, match="closed"):
        await may.request("GET", "/api/v1/vehicles/1")


@pytest.mark.parametrize(
    "claims,status",
    [
        ({"scope": "openid"}, 403),
        ({"aud": "https://wrong.invalid/mcp"}, 401),
        ({"iss": "https://wrong.invalid"}, 401),
        ({"exp": 1}, 401),
        ({"sub": "another-user"}, 401),
    ],
)
async def test_invalid_http_token_does_not_reach_may(
    settings_factory, oauth_settings, signed_tokens, claims, status
):
    token, keys = signed_tokens
    calls = []
    may = MayClient(
        settings_factory(), transport=httpx.MockTransport(lambda request: calls.append(request))
    )
    verifier = JWTVerifier(
        oauth_settings,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=keys)),
    )
    app = create_http_app(settings_factory(), oauth_settings, may_client=may, verifier=verifier)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app)) as client,
    ):
        response = await client.post(
            oauth_settings.resource_url,
            headers={"Authorization": "Bearer " + token(**claims)},
            json={},
        )
        assert response.status_code == status
        assert calls == []
        assert "resource_metadata" in response.headers["WWW-Authenticate"]


async def test_metadata_discovery_and_invalid_host(settings_factory, oauth_settings):
    app = create_http_app(settings_factory(), oauth_settings)
    path = "/.well-known/oauth-protected-resource/mcp"
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="https://mcp.example.invalid"
        ) as client,
    ):
        response = await client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert data["resource"] == "https://mcp.example.invalid/mcp"
        assert data["authorization_servers"] == ["https://idp.invalid/realms/synthetic"]
        assert data["scopes_supported"] == ["may:access"]
        response = await client.get(path, headers={"Host": "attacker.invalid"})
        assert response.status_code == 400


async def test_bad_signature_and_may_key_reject_before_upstream(
    settings_factory, oauth_settings, signed_tokens
):
    token, keys = signed_tokens
    valid = token()
    parts = valid.split(".")
    parts[2] = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
    calls = []
    may = MayClient(
        settings_factory(), transport=httpx.MockTransport(lambda request: calls.append(request))
    )
    verifier = JWTVerifier(
        oauth_settings,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=keys)),
    )
    app = create_http_app(settings_factory(), oauth_settings, may_client=may, verifier=verifier)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app)) as client,
    ):
        for invalid in (".".join(parts), "synthetic-test-key"):
            response = await client.post(
                oauth_settings.resource_url, headers={"Authorization": "Bearer " + invalid}, json={}
            )
            assert response.status_code == 401
            assert invalid not in response.text
        assert calls == []
