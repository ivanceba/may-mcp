"""Synthetic fixtures and network isolation shared by every test layer."""

import json
import os
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from pytest_socket import disable_socket, enable_socket, socket_allow_hosts

from may_mcp.auth import OAuthSettings
from may_mcp.config import Settings


def pytest_addoption(parser):
    parser.addoption(
        "--may-integration", action="store_true", help="Provision a disposable May using Docker."
    )


@pytest.fixture(autouse=True)
def offline_network_guard(request, _function_scoped_runner, monkeypatch):
    # The pinned pytest-asyncio runner must create Windows' loopback self-pipe
    # before blocking sockets; test code still cannot open a network socket.
    for name in (
        "MAY_BASE_URL",
        "MAY_API_KEY",
        "MAY_MCP_ALLOW_WRITES",
        *[name for name in os.environ if name.startswith("MAY_MCP_OAUTH_")],
    ):
        monkeypatch.delenv(name, raising=False)
    if request.node.get_closest_marker("integration"):
        socket_allow_hosts(["127.0.0.1"], allow_unix_socket=True)
    else:
        disable_socket(allow_unix_socket=True)
    try:
        yield
    finally:
        enable_socket()


@pytest.fixture
def settings_factory():
    """Build validated Settings exclusively from synthetic environment input."""

    def factory(**overrides):
        return Settings.from_env(
            {
                "MAY_BASE_URL": "https://may.invalid",
                "MAY_API_KEY": "synthetic-test-key",
                "MAY_MCP_ALLOW_WRITES": "false",
                **overrides,
            }
        )

    return factory


@pytest.fixture
def oauth_settings():
    return OAuthSettings(
        "https://idp.invalid/realms/synthetic",
        "https://mcp.example.invalid/mcp",
        "https://idp.invalid/realms/synthetic/protocol/openid-connect/certs",
        frozenset({"synthetic-user"}),
    )


@pytest.fixture
def signed_tokens(oauth_settings):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="synthetic-key", use="sig", alg="RS256")

    def token(*, omit=(), **changes):
        claims = {
            "iss": oauth_settings.issuer_url,
            "aud": oauth_settings.resource_url,
            "sub": "synthetic-user",
            "azp": "synthetic-client",
            "exp": int(time.time()) + 300,
            "scope": "openid may:access",
            **changes,
        }
        for name in omit:
            claims.pop(name, None)
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "synthetic-key"})

    return token, {"keys": [jwk]}


@pytest.fixture
def synthetic_vehicle():
    """Full May 0.44.2 vehicle serialization with fictitious empty history."""
    return {
        "id": 1,
        "name": "MCP synthetic vehicle",
        "vehicle_type": "car",
        "make": None,
        "model": None,
        "year": None,
        "registration": None,
        "vin": None,
        "fuel_type": "petrol",
        "secondary_fuel_type": None,
        "tank_capacity": None,
        "is_active": True,
        "created_at": "2026-01-01T00:00:00",
        "stats": {
            "total_fuel_cost": 0,
            "total_expense_cost": 0,
            "total_distance": 0,
            "average_consumption": None,
            "last_odometer": 0,
        },
    }


@pytest.fixture
def mock_may_http():
    """Create a real HTTPX mock transport; unexpected requests fail by default."""

    def factory(handler=None):
        def reject(request):
            raise AssertionError("Unexpected request to the synthetic May transport.")

        return httpx.MockTransport(handler or reject)

    return factory
