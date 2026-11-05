"""Actual Keycloak PKCE, token lifecycle and authenticated real May operations."""

import httpx
import httpx2
import jwt
import pytest
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client

from may_mcp.auth import JWTVerifier, OAuthSettings
from may_mcp.config import Settings
from may_mcp.server import create_http_app
from tests.helpers.oauth import ISSUER, RESOURCE, SUBJECT, authorize, exchange, oidc_client

pytestmark = pytest.mark.integration


def oauth_config(metadata):
    return OAuthSettings(
        ISSUER, RESOURCE, metadata["jwks_uri"], frozenset({SUBJECT}), allow_loopback_http=True
    )


def provider_verifier(metadata, tls):
    return JWTVerifier(oauth_config(metadata), transport=httpx.AsyncHTTPTransport(verify=tls))


async def test_real_pkce_and_may_http_crud(oauth_provider, may_test_instance):
    metadata, _, tls, _ = oauth_provider
    assert "S256" in metadata["code_challenge_methods_supported"]
    async with oidc_client(tls) as oidc:
        code, proof = await authorize(oidc)
        response = await exchange(oidc, code, proof)
        assert response.status_code == 200
        access = response.json()["access_token"]
        claims = jwt.decode(access, options={"verify_signature": False})
        assert claims["iss"] == ISSUER
        assert claims["aud"] == RESOURCE
        assert claims["sub"] == SUBJECT
        assert claims.get("azp", claims.get("client_id")) == "synthetic-client"
        assert "may:access" in claims.get("scope", "").split()
        assert jwt.get_unverified_header(access)["alg"] == "RS256"
        # Inspect the real selected provider's public signing-key contract.
        keys_response = await oidc.get(metadata["jwks_uri"])
        assert keys_response.status_code == 200
        selected = next(
            item
            for item in keys_response.json()["keys"]
            if item.get("kid") == jwt.get_unverified_header(access)["kid"]
        )
        public_key = jwt.PyJWK.from_dict(selected, algorithm="RS256")
        assert (
            jwt.decode(access, public_key, algorithms=["RS256"], issuer=ISSUER, audience=RESOURCE)[
                "sub"
            ]
            == SUBJECT
        )
    # Reconnect with the same provider token into separately owned resource apps.
    for writes in (True, False):
        settings = Settings(may_test_instance.base_url, may_test_instance.api_key, writes)
        app = create_http_app(
            settings, oauth_config(metadata), verifier=provider_verifier(metadata, tls)
        )
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app), headers={"Authorization": "Bearer " + access}
            ) as http,
            Client(
                streamable_http_client(RESOURCE, http_client=http), mode="legacy", cache=None
            ) as client,
        ):
            names = {tool.name for tool in (await client.list_tools()).tools}
            assert ("may_create_vehicle" in names) is writes
            read = await client.call_tool(
                "may_get_vehicle", {"vehicle_id": may_test_instance.vehicle_id}
            )
            assert read.is_error is not True
            assert read.structured_content["name"] == "MCP synthetic vehicle"
            if writes:
                created = await client.call_tool(
                    "may_create_vehicle",
                    {"vehicle": {"name": "OAuth disposable vehicle", "vehicle_type": "car"}},
                )
                assert created.is_error is not True
                identifier = created.structured_content["id"]
                try:
                    changed = await client.call_tool(
                        "may_update_vehicle",
                        {"vehicle_id": identifier, "changes": {"name": "OAuth changed"}},
                    )
                    assert changed.is_error is not True
                    saved = await client.call_tool("may_get_vehicle", {"vehicle_id": identifier})
                    assert saved.structured_content["name"] == "OAuth changed"
                finally:
                    deleted = await client.call_tool(
                        "may_delete_vehicle", {"vehicle_id": identifier}
                    )
                    assert deleted.is_error is not True
            else:
                denied = await client.call_tool(
                    "may_delete_vehicle", {"vehicle_id": may_test_instance.vehicle_id}
                )
                assert denied.is_error is True


async def test_real_pkce_replay_redirect_and_resource_rejections(oauth_provider):
    _, _, tls, _ = oauth_provider
    async with oidc_client(tls) as oidc:
        code, proof = await authorize(oidc)
        bad = await exchange(oidc, code, "incorrect-proof-" + "x" * 48)
        assert bad.status_code == 400
        code, proof = await authorize(oidc)
        assert (await exchange(oidc, code, proof)).status_code == 200
        assert (await exchange(oidc, code, proof)).status_code == 400
        code, proof = await authorize(oidc)
        bad = await exchange(oidc, code, proof, redirect="http://127.0.0.1:15061/not-approved")
        assert bad.status_code == 400
        code, proof = await authorize(oidc)
        bad = await exchange(oidc, code, proof, resource="https://another.invalid/mcp")
        assert bad.status_code == 400
        assert bad.json()["error"] == "invalid_target"


async def test_real_refresh_revocation_and_provider_restart(oauth_provider):
    metadata, restart, tls, _ = oauth_provider
    async with oidc_client(tls) as oidc:
        code, proof = await authorize(oidc)
        issued = (await exchange(oidc, code, proof)).json()
        refreshed = await oidc.post(
            metadata["token_endpoint"],
            data={
                "grant_type": "refresh_token",
                "client_id": "synthetic-client",
                "refresh_token": issued["refresh_token"],
                "resource": RESOURCE,
            },
        )
        assert refreshed.status_code == 200
        renewed = refreshed.json()
        replay = await oidc.post(
            metadata["token_endpoint"],
            data={
                "grant_type": "refresh_token",
                "client_id": "synthetic-client",
                "refresh_token": issued["refresh_token"],
                "resource": RESOURCE,
            },
        )
        assert replay.status_code == 400
        # Start a fresh token family after intentionally exercising reuse detection.
        code, proof = await authorize(oidc)
        renewed = (await exchange(oidc, code, proof)).json()
        restart()
        verifier = provider_verifier(metadata, tls)
        try:
            assert await verifier.verify_token(renewed["access_token"]) is not None
            refreshed = await oidc.post(
                metadata["token_endpoint"],
                data={
                    "grant_type": "refresh_token",
                    "client_id": "synthetic-client",
                    "refresh_token": renewed["refresh_token"],
                    "resource": RESOURCE,
                },
            )
            assert refreshed.status_code == 200
            latest = refreshed.json()
            revoked = await oidc.post(
                metadata["revocation_endpoint"],
                data={
                    "client_id": "synthetic-client",
                    "token": latest["refresh_token"],
                    "token_type_hint": "refresh_token",
                },
            )
            assert revoked.status_code == 200
            denied = await oidc.post(
                metadata["token_endpoint"],
                data={
                    "grant_type": "refresh_token",
                    "client_id": "synthetic-client",
                    "refresh_token": latest["refresh_token"],
                    "resource": RESOURCE,
                },
            )
            assert denied.status_code == 400
            # Self-contained access JWTs retain their short validity after revocation.
            assert await verifier.verify_token(latest["access_token"]) is not None
        finally:
            await verifier.aclose()


async def test_real_short_lived_access_token_expires(oauth_provider):
    import asyncio

    metadata, _, tls, _ = oauth_provider
    async with oidc_client(tls) as oidc:
        code, proof = await authorize(oidc, client_id="synthetic-expiry-client")
        response = await exchange(oidc, code, proof, client_id="synthetic-expiry-client")
        assert response.status_code == 200
        data = response.json()
    assert 0 < data["expires_in"] <= 3
    verifier = provider_verifier(metadata, tls)
    try:
        assert await verifier.verify_token(data["access_token"]) is not None
        await asyncio.sleep(data["expires_in"] + 1)
        assert await verifier.verify_token(data["access_token"]) is None
    finally:
        await verifier.aclose()


def test_ephemeral_tls_key_has_no_group_or_other_access(oauth_provider):
    _, _, _, directory = oauth_provider
    assert directory.stat().st_mode & 0o077 == 0
    assert (directory / "key.pem").stat().st_mode & 0o077 == 0
