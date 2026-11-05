"""Readiness uses only public metadata on loopback, never caller credentials."""

import httpx
import pytest

from may_mcp.healthcheck import check_health


async def test_health_probe_checks_public_resource_on_fixed_loopback(monkeypatch):
    monkeypatch.setenv("MAY_API_KEY", "synthetic-private-key")
    monkeypatch.setenv("HTTP_PROXY", "http://attacker.invalid")
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url == "http://127.0.0.1:8000/.well-known/oauth-protected-resource/mcp"
        assert request.headers["Host"] == "mcp.example.invalid"
        assert "Authorization" not in request.headers
        assert "synthetic-private-key" not in str(request.headers)
        return httpx.Response(200, json={"resource": "https://mcp.example.invalid/mcp"})

    assert (
        await check_health(
            "https://MCP.EXAMPLE.INVALID:443/mcp", transport=httpx.MockTransport(handler)
        )
        is True
    )
    assert len(calls) == 1


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503),
        httpx.Response(302, headers={"Location": "https://attacker.invalid"}),
        httpx.Response(200, json={"resource": "https://another.invalid/mcp"}),
        httpx.Response(200, text="not-json"),
    ],
)
async def test_unhealthy_or_wrong_metadata_is_rejected(response):
    assert (
        await check_health(
            "https://mcp.example.invalid/mcp",
            transport=httpx.MockTransport(lambda request: response),
        )
        is False
    )


async def test_health_timeout_is_failure_not_a_traceback():
    def handler(request):
        raise httpx.ReadTimeout("synthetic-private-upstream-message")

    assert (
        await check_health(
            "https://mcp.example.invalid/mcp", transport=httpx.MockTransport(handler)
        )
        is False
    )


async def test_malformed_public_url_fails_silently_without_network():
    def reject(request):
        raise AssertionError("Invalid public configuration must not make a request.")

    assert (
        await check_health(
            "https://mcp.invalid:private-value/mcp", transport=httpx.MockTransport(reject)
        )
        is False
    )
