"""Reject unsafe remote configuration and cryptographically invalid consumers."""

import base64
from dataclasses import replace
from types import SimpleNamespace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from may_mcp.auth import JWTVerifier, OAuthSettings


async def test_deeply_nested_untrusted_token_is_rejected_without_fetch(oauth_settings):
    header = base64.urlsafe_b64encode(
        b'{"alg":"RS256","kid":' + b"[" * 1200 + b"]" * 1200 + b"}"
    ).rstrip(b"=")
    token = header.decode() + ".e30.invalid"
    calls = []
    verifier = JWTVerifier(
        oauth_settings, transport=httpx.MockTransport(lambda request: calls.append(request))
    )
    try:
        assert await verifier.verify_token(token) is None
        assert calls == []
    finally:
        await verifier.aclose()


def test_explicit_loopback_exception_and_env_configuration():
    env = {
        "MAY_MCP_OAUTH_ISSUER": "http://127.0.0.1:15060/realms/test",
        "MAY_MCP_OAUTH_RESOURCE": "https://mcp.example.invalid/mcp",
        "MAY_MCP_OAUTH_JWKS_URL": "http://127.0.0.1:15060/certs",
        "MAY_MCP_OAUTH_ALLOWED_SUBJECTS": "synthetic-user other-user",
        "MAY_MCP_OAUTH_ALLOW_LOOPBACK_HTTP": "true",
    }
    settings = OAuthSettings.from_env(env)
    assert settings.allowed_subjects == frozenset({"synthetic-user", "other-user"})
    assert "synthetic-user" not in repr(settings)
    with pytest.raises(ValueError):
        OAuthSettings.from_env({**env, "MAY_MCP_OAUTH_ALLOW_LOOPBACK_HTTP": "false"})
    with pytest.raises(ValueError):
        replace(settings, issuer_url="http://idp.invalid/realm")
    with pytest.raises(ValueError):
        OAuthSettings.from_env({**env, "MAY_MCP_OAUTH_ALLOW_LOOPBACK_HTTP": "TRUE"})


async def test_jwks_rotation_unknown_kid_throttling_and_stale_keys(
    oauth_settings, signed_tokens, monkeypatch
):
    token, keys = signed_tokens
    now = 100
    calls = []
    monkeypatch.setattr("may_mcp.auth.time", SimpleNamespace(monotonic=lambda: now))

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=keys if len(calls) == 1 else {"keys": []})

    verifier = JWTVerifier(oauth_settings, transport=httpx.MockTransport(handler))
    unknown = jwt.encode(
        {"exp": 9999999999},
        rsa.generate_private_key(public_exponent=65537, key_size=2048),
        algorithm="RS256",
        headers={"kid": "unknown-key"},
    )
    try:
        assert await verifier.verify_token(token()) is not None
        for _ in range(3):
            assert await verifier.verify_token(unknown) is None
        assert len(calls) == 1
        now = 161
        assert await verifier.verify_token(token()) is None
        assert len(calls) == 2
    finally:
        await verifier.aclose()


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(302, headers={"location": "https://attacker.invalid/certs"}),
        httpx.Response(503, text="provider-internal-secret"),
        httpx.Response(200, json={"keys": "invalid"}),
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, content=b"x" * 131073),
        httpx.Response(200, json={"keys": [None]}),
    ],
)
async def test_invalid_or_unavailable_jwks_fails_closed_without_secret_logs(
    oauth_settings, signed_tokens, response, caplog
):
    token, _ = signed_tokens
    calls = []

    def handler(request):
        calls.append(request)
        return response

    verifier = JWTVerifier(oauth_settings, transport=httpx.MockTransport(handler))
    try:
        assert await verifier.verify_token(token()) is None
        assert len(calls) == 1
        assert "provider-internal-secret" not in caplog.text
    finally:
        await verifier.aclose()


@pytest.mark.parametrize(
    "changes",
    [
        {"issuer_url": "http://idp.invalid/realm"},
        {"resource_url": "http://mcp.example.invalid/mcp"},
        {"jwks_url": "http://idp.invalid/certs"},
        {"issuer_url": "https://secret@idp.invalid/realm"},
        {"resource_url": "https://mcp.example.invalid"},
        {"resource_url": "https://mcp.example.invalid/mcp?private=value"},
        {"jwks_url": "https://idp.invalid/a/../certs"},
        {"resource_url": "https://mcp.example.invalid/%2fsecret"},
        {"resource_url": "https://mcp.example.invalid/mcp#fragment"},
        {"allow_loopback_http": "true"},
        {"allowed_subjects": frozenset()},
        {"allowed_subjects": frozenset({""})},
        {"required_scope": "two scopes"},
        {"required_scope": ""},
    ],
)
def test_invalid_oauth_configuration_fails_closed(oauth_settings, changes):
    with pytest.raises(ValueError):
        replace(oauth_settings, **changes)


async def test_signed_token_binds_resource_subject_and_principal(oauth_settings, signed_tokens):
    token, keys = signed_tokens
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=keys)

    verifier = JWTVerifier(oauth_settings, transport=httpx.MockTransport(handler))
    try:
        result = await verifier.verify_token(token())
        assert result is not None
        assert result.resource == "https://mcp.example.invalid/mcp"
        assert result.subject == "synthetic-user"
        assert result.client_id == "synthetic-client"
        assert result.scopes == ["openid", "may:access"]
        assert result.claims == {"iss": "https://idp.invalid/realms/synthetic"}
        assert await verifier.verify_token(token()) is not None
        assert len(requests) == 1
        assert requests[0].url == oauth_settings.jwks_url
        assert "authorization" not in requests[0].headers
    finally:
        await verifier.aclose()


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://attacker.invalid"},
        {"aud": "https://another.invalid/mcp"},
        {"exp": 1},
        {"exp": None},
        {"exp": True},
        {"nbf": 9999999999},
        {"sub": "unapproved-user"},
        {"sub": None},
        {"azp": None},
        {"scope": ["may:access"]},
    ],
)
async def test_invalid_claims_are_not_authenticated(oauth_settings, signed_tokens, changes):
    token, keys = signed_tokens
    verifier = JWTVerifier(
        oauth_settings,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=keys)),
    )
    try:
        assert await verifier.verify_token(token(**changes)) is None
    finally:
        await verifier.aclose()


async def test_authelia_scope_array_authenticates_signed_principal(oauth_settings, signed_tokens):
    token, keys = signed_tokens
    verifier = JWTVerifier(
        oauth_settings,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=keys)),
    )
    try:
        result = await verifier.verify_token(
            token(
                omit=("scope", "azp"),
                scp=["openid", "may:access"],
                client_id="synthetic-authelia-client",
            )
        )
        assert result is not None
        assert result.scopes == ["openid", "may:access"]
        assert result.client_id == "synthetic-authelia-client"
        assert result.subject == "synthetic-user"
        assert result.resource == "https://mcp.example.invalid/mcp"
    finally:
        await verifier.aclose()


@pytest.mark.parametrize("scp", [None, "may:access", 1, [None], [1], [""], ["two scopes"]])
async def test_malformed_authelia_scopes_are_rejected(oauth_settings, signed_tokens, scp):
    token, keys = signed_tokens
    verifier = JWTVerifier(
        oauth_settings,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=keys)),
    )
    try:
        assert await verifier.verify_token(token(omit=("scope",), scp=scp)) is None
    finally:
        await verifier.aclose()


@pytest.mark.parametrize("scope", [None, ["may:access"], "openid", "openid may:access"])
async def test_standard_scope_is_authoritative(oauth_settings, signed_tokens, scope):
    token, keys = signed_tokens
    verifier = JWTVerifier(
        oauth_settings,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=keys)),
    )
    try:
        result = await verifier.verify_token(token(scope=scope, scp=["may:access"]))
        if isinstance(scope, str):
            assert result is not None
            assert result.scopes == scope.split()
        else:
            assert result is None
    finally:
        await verifier.aclose()


async def test_signature_and_algorithm_cannot_be_substituted(oauth_settings, signed_tokens):
    token, keys = signed_tokens
    verifier = JWTVerifier(
        oauth_settings,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=keys)),
    )
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    claims = jwt.decode(token(), options={"verify_signature": False})
    invalid = [
        "synthetic-test-key",
        jwt.encode(claims, wrong_key, algorithm="RS256", headers={"kid": "synthetic-key"}),
        jwt.encode(
            claims,
            "synthetic-shared-key-32-characters",
            algorithm="HS256",
            headers={"kid": "synthetic-key"},
        ),
        jwt.encode(claims, None, algorithm="none", headers={"kid": "synthetic-key"}),
    ]
    try:
        for value in invalid:
            assert await verifier.verify_token(value) is None
    finally:
        await verifier.aclose()
