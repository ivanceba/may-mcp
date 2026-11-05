"""Checks that the test boundary catches accidental real network access."""

import socket

import pytest
from pytest_socket import SocketBlockedError


def test_offline_network_is_denied():
    # A missing harness guard would permit this socket before any connection.
    with (
        pytest.warns(UserWarning, match="socket.socket"),
        pytest.raises(SocketBlockedError),
        socket.socket(socket.AF_INET, socket.SOCK_STREAM),
    ):
        pass


async def test_offline_async_network_is_denied():
    with (
        pytest.warns(UserWarning, match="socket.socket"),
        pytest.raises(SocketBlockedError),
        socket.socket(socket.AF_INET, socket.SOCK_STREAM),
    ):
        pass


@pytest.mark.parametrize(
    ("resolver", "args"),
    [("getaddrinfo", ("may.invalid", 80)), ("gethostbyname", ("may.invalid",))],
)
def test_offline_dns_is_denied(resolver, args):
    with pytest.warns(UserWarning, match=resolver), pytest.raises(SocketBlockedError):
        getattr(socket, resolver)(*args)
