"""Guarded asynchronous HTTP boundary for a single configured May instance."""

import re
from collections.abc import Mapping
from typing import Any

import httpx

from may_mcp.config import Settings
from may_mcp.errors import MayError


class MayClient:
    def __init__(
        self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._allow_writes = settings.allow_writes
        self._http = httpx.AsyncClient(
            base_url=f"{settings.base_url}/",
            headers={"Authorization": f"Bearer {settings.api_key}"},
            transport=transport,
            timeout=30.0,
            follow_redirects=False,
            trust_env=False,
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int | float | bool | None] | None = None,
        json: Any = None,
    ) -> dict[str, Any]:
        method = method.upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise MayError("invalid_request", "Unsupported May request method.")
        mutating = method != "GET"
        if mutating and not self._allow_writes:
            raise MayError("read_only", "May writes are disabled by server configuration.")
        if (
            not re.fullmatch(r"/?[A-Za-z0-9_./~-]+", path)
            or path.startswith("//")
            or any(segment in {".", ".."} for segment in path.split("/"))
        ):
            raise MayError("invalid_request", "May requests require a safe relative path.")
        if self._http.is_closed:
            raise MayError("client_closed", "The May client is closed.")
        try:
            response = await self._http.request(method, path.lstrip("/"), params=params, json=json)
        except httpx.TimeoutException:
            raise MayError("timeout", "May request timed out.", outcome_unknown=mutating) from None
        except httpx.RequestError:
            raise MayError(
                "network_error", "May could not be reached.", outcome_unknown=mutating
            ) from None

        if 300 <= response.status_code < 400:
            raise MayError(
                "redirect_rejected", "May redirects are not followed.", outcome_unknown=mutating
            )
        if not response.is_success:
            codes = {
                400: "validation_error",
                401: "authentication_error",
                403: "permission_denied",
                404: "not_found",
                422: "validation_error",
                429: "rate_limited",
            }
            code = codes.get(response.status_code, "upstream_error")
            raise MayError(
                code,
                "May rejected the request.",
                outcome_unknown=mutating and response.status_code >= 500,
            )
        try:
            data = response.json()
        except ValueError:
            raise MayError(
                "invalid_response", "May returned an invalid JSON object.", outcome_unknown=mutating
            ) from None
        if not isinstance(data, dict):
            raise MayError(
                "invalid_response", "May returned an invalid JSON object.", outcome_unknown=mutating
            )
        return data

    async def aclose(self) -> None:
        await self._http.aclose()
