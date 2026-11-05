"""Synthetic fixtures and network isolation shared by every test layer."""

import httpx
import pytest
from pytest_socket import disable_socket, enable_socket, socket_allow_hosts


def pytest_addoption(parser):
    parser.addoption(
        "--may-integration", action="store_true", help="Provision a disposable May using Docker."
    )


@pytest.fixture(autouse=True)
def offline_network_guard(request, _function_scoped_runner, monkeypatch):
    # The pinned pytest-asyncio runner must create Windows' loopback self-pipe
    # before blocking sockets; test code still cannot open a network socket.
    for name in ("MAY_BASE_URL", "MAY_API_KEY", "MAY_MCP_ALLOW_WRITES"):
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
    """Synthetic environment input; task #5 will add validated Settings."""

    def factory(**overrides):
        return {
            "MAY_BASE_URL": "https://may.invalid",
            "MAY_API_KEY": "synthetic-test-key",
            "MAY_MCP_ALLOW_WRITES": "false",
            **overrides,
        }

    return factory


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
