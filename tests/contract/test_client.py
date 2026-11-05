"""Guard the actual HTTP boundary, including credentials and uncertain writes."""

import json
import logging

import httpx
import pytest

from may_mcp.client import MayClient
from may_mcp.errors import MayError


@pytest.fixture
async def client_factory(settings_factory):
    clients = []

    def create(handler, *, writes=False, base_url="https://may.invalid"):
        settings = settings_factory(
            MAY_BASE_URL=base_url,
            MAY_API_KEY="synthetic-secret",
            MAY_MCP_ALLOW_WRITES="true" if writes else "false",
        )
        client = MayClient(settings, transport=httpx.MockTransport(handler))
        clients.append(client)
        return client

    yield create
    for client in clients:
        await client.aclose()


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "post", "pAtCh"])
async def test_read_only_blocks_before_transport(client_factory, method):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"unexpected": True})

    client = client_factory(handler)
    with pytest.raises(MayError) as error:
        await client.request(method, "/api/v1/vehicles", json={"name": "Synthetic"})
    assert error.value.code == "read_only"
    assert error.value.outcome_unknown is False
    assert requests == []


async def test_read_authentication_prefix_and_query(client_factory, caplog):
    caplog.set_level(logging.DEBUG)

    def handler(request):
        assert request.method == "GET"
        assert str(request.url) == "https://may.invalid/may/api/v1/vehicles?limit=2&offset=0"
        assert request.headers["Authorization"] == "Bearer synthetic-secret"
        return httpx.Response(200, json={"vehicles": [], "count": 0})

    client = client_factory(handler, base_url="https://may.invalid/may/")
    assert await client.request("get", "/api/v1/vehicles", params={"limit": 2, "offset": 0}) == {
        "vehicles": [],
        "count": 0,
    }
    assert "synthetic-secret" not in caplog.text


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_enabled_writes_are_sent_once_with_original_json(client_factory, method):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == method
        assert json.loads(request.content) == {"value": None, "amount": 0, "active": False}
        return httpx.Response(200, json={"success": True})

    client = client_factory(handler, writes=True)
    assert await client.request(
        method, "/api/v1/vehicles/1", json={"value": None, "amount": 0, "active": False}
    ) == {"success": True}
    assert len(requests) == 1


@pytest.mark.parametrize(
    "path",
    [
        "https://evil.invalid/api/v1/vehicles",
        "https://may.invalid/api/v1/vehicles",
        "//evil.invalid/api/v1/vehicles",
        "///evil.invalid/api/v1/vehicles",
        "\\evil.invalid",
        "/api/../private",
        "/api/%2e%2e/private",
        "/api/%252e%252e/private",
        "/api/v1/vehicles?key=synthetic-secret",
        "/api/v1/vehicles#fragment",
        "/api/./v1/vehicles",
        "/api/v1/vehicles\n",
        "",
    ],
)
async def test_unsafe_path_never_sends_credentials(client_factory, path):
    requests = []
    client = client_factory(lambda request: requests.append(request), writes=True)
    with pytest.raises(MayError) as error:
        await client.request("GET", path)
    assert error.value.code == "invalid_request"
    assert "synthetic-secret" not in str(error.value)
    assert requests == []


@pytest.mark.parametrize("method", ["TRACE", "CONNECT", "PROPFIND", " GET", "GET\n"])
async def test_unsupported_method_is_rejected_before_transport(client_factory, method):
    requests = []
    client = client_factory(lambda request: requests.append(request), writes=True)
    with pytest.raises(MayError) as error:
        await client.request(method, "/api/v1/vehicles")
    assert error.value.code == "invalid_request"
    assert requests == []


@pytest.mark.parametrize("location", ["https://evil.invalid/private", "/different"])
async def test_redirects_are_never_followed(client_factory, location):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"Location": location})

    client = client_factory(handler)
    with pytest.raises(MayError) as error:
        await client.request("GET", "/api/v1/vehicles")
    assert error.value.code == "redirect_rejected"
    assert len(requests) == 1
    assert requests[0].url.host == "may.invalid"


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (400, "validation_error"),
        (401, "authentication_error"),
        (403, "permission_denied"),
        (404, "not_found"),
        (422, "validation_error"),
        (429, "rate_limited"),
        (500, "upstream_error"),
    ],
)
async def test_status_errors_are_distinct_and_sanitized(client_factory, status, code, caplog):
    caplog.set_level(logging.DEBUG)
    client = client_factory(
        lambda request: httpx.Response(status, text="private-record synthetic-secret")
    )
    with pytest.raises(MayError) as error:
        await client.request("GET", "/api/v1/vehicles")
    assert error.value.code == code
    assert error.value.outcome_unknown is False
    for secret in ("private-record", "synthetic-secret"):
        assert secret not in str(error.value)
        assert secret not in repr(error.value)
        assert secret not in caplog.text


@pytest.mark.parametrize("body", [b"private-record synthetic-secret", b"[]", b"null", b"42"])
async def test_invalid_response_is_sanitized(client_factory, body):
    client = client_factory(lambda request: httpx.Response(200, content=body))
    with pytest.raises(MayError) as error:
        await client.request("GET", "/api/v1/vehicles")
    assert error.value.code == "invalid_response"
    assert "private-record" not in str(error.value)
    assert "synthetic-secret" not in str(error.value)


@pytest.mark.parametrize(("method", "unknown"), [("GET", False), ("POST", True)])
async def test_timeout_is_not_retried_and_reports_uncertain_writes(client_factory, method, unknown):
    requests = []

    def handler(request):
        requests.append(request)
        raise httpx.ReadTimeout("private-record synthetic-secret", request=request)

    client = client_factory(handler, writes=True)
    with pytest.raises(MayError) as error:
        await client.request(method, "/api/v1/vehicles")
    assert error.value.code == "timeout"
    assert error.value.outcome_unknown is unknown
    assert len(requests) == 1
    assert "synthetic-secret" not in str(error.value)
    assert error.value.__suppress_context__ is True


async def test_network_failure_is_sanitized(client_factory):
    def handler(request):
        raise httpx.ConnectError("private-record synthetic-secret", request=request)

    client = client_factory(handler)
    with pytest.raises(MayError) as error:
        await client.request("GET", "/api/v1/vehicles")
    assert error.value.code == "network_error"
    assert "synthetic-secret" not in str(error.value)


async def test_closed_client_fails_safely(client_factory):
    client = client_factory(lambda request: httpx.Response(200, json={}))
    await client.aclose()
    await client.aclose()
    with pytest.raises(MayError) as error:
        await client.request("GET", "/api/v1/vehicles")
    assert error.value.code == "client_closed"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={}),
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, json=[]),
        httpx.Response(302, headers={"Location": "/elsewhere"}),
    ],
)
async def test_failed_mutation_response_does_not_claim_write_was_not_saved(
    client_factory, response
):
    requests = []

    def handler(request):
        requests.append(request)
        return response

    client = client_factory(handler, writes=True)
    with pytest.raises(MayError) as error:
        await client.request("POST", "/api/v1/vehicles", json={"name": "Synthetic"})
    assert error.value.outcome_unknown is True
    assert "verify" in str(error.value).lower()
    assert len(requests) == 1
