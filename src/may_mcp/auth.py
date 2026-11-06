"""External OAuth resource-server configuration and token verification."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import httpx
import jwt

if TYPE_CHECKING:
    from mcp.server.auth.provider import AccessToken


@dataclass(frozen=True)
class OAuthSettings:
    issuer_url: str
    resource_url: str
    jwks_url: str
    allowed_subjects: frozenset[str] = field(repr=False)
    required_scope: str = "may:access"
    allow_loopback_http: bool = False

    def __post_init__(self) -> None:
        if type(self.allow_loopback_http) is not bool:
            raise ValueError("OAuth loopback HTTP setting must be a boolean.")
        for name in ("issuer_url", "resource_url", "jwks_url"):
            value = getattr(self, name)
            try:
                url = urlsplit(value)
                valid = (
                    bool(url.hostname)
                    and (
                        url.scheme == "https"
                        or (
                            self.allow_loopback_http
                            and url.scheme == "http"
                            and url.hostname in {"127.0.0.1", "::1"}
                        )
                    )
                    and url.username is None
                    and url.password is None
                    and (url.port is None or url.port > 0)
                    and not any(char.isspace() or ord(char) < 33 for char in value)
                    and not any(char in value for char in "\\%?#")
                    and not any(segment in {".", ".."} for segment in url.path.split("/"))
                    and "//" not in url.path
                )
                if name == "resource_url":
                    valid = valid and bool(url.path.strip("/")) and not url.path.endswith("/")
                if not valid:
                    raise ValueError
                parsed = httpx.URL(value)
                if name == "resource_url":
                    object.__setattr__(self, name, str(parsed))
            except (ValueError, TypeError, httpx.InvalidURL):
                raise ValueError(
                    f"OAuth {name} must be a fixed HTTPS URL without credentials."
                ) from None
        if (
            not isinstance(self.allowed_subjects, frozenset)
            or not self.allowed_subjects
            or any(
                not isinstance(s, str) or not s or any(c.isspace() for c in s)
                for s in self.allowed_subjects
            )
        ):
            raise ValueError("OAuth allowed subjects must be an explicit nonempty set.")
        if not self.required_scope or any(
            not 33 <= ord(c) <= 126 or c in '\\"' for c in self.required_scope
        ):
            raise ValueError("OAuth required scope must be one printable scope name.")

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> OAuthSettings:
        prefix = "MAY_MCP_OAUTH_"
        loopback = env.get(prefix + "ALLOW_LOOPBACK_HTTP", "false")
        if loopback not in {"true", "false"}:
            raise ValueError("OAuth loopback HTTP setting must be exactly true or false.")
        return cls(
            issuer_url=env.get(prefix + "ISSUER", ""),
            resource_url=env.get(prefix + "RESOURCE", ""),
            jwks_url=env.get(prefix + "JWKS_URL", ""),
            allowed_subjects=frozenset(env.get(prefix + "ALLOWED_SUBJECTS", "").split()),
            required_scope=env.get(prefix + "SCOPE", "may:access"),
            allow_loopback_http=loopback == "true",
        )


class JWTVerifier:
    def __init__(
        self, settings: OAuthSettings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.settings = settings
        self._http = httpx.AsyncClient(
            transport=transport, trust_env=False, follow_redirects=False, timeout=5.0
        )
        self._keys: dict[str, jwt.PyJWK] = {}
        self._refresh_after = 0.0
        self._lock = asyncio.Lock()

    async def _get_key(self, kid: str) -> jwt.PyJWK | None:
        async with self._lock:
            if time.monotonic() >= self._refresh_after:
                # A fixed refresh window bounds both stale keys and unknown-kid traffic.
                self._keys = {}
                self._refresh_after = time.monotonic() + 60
                async with self._http.stream("GET", self.settings.jwks_url) as response:
                    response.raise_for_status()
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > 131072:
                            raise ValueError("JWKS size limit exceeded.")
                document = json.loads(data)
                keys = document.get("keys") if isinstance(document, dict) else None
                if not isinstance(keys, list) or len(keys) > 100:
                    raise ValueError("Invalid JWKS.")
                parsed: dict[str, jwt.PyJWK] = {}
                for item in keys:
                    if not isinstance(item, dict):
                        raise ValueError("Invalid JWKS key.")
                    if (
                        item.get("kty") != "RSA"
                        or item.get("use", "sig") != "sig"
                        or item.get("alg", "RS256") != "RS256"
                    ):
                        continue
                    key = jwt.PyJWK.from_dict(item, algorithm="RS256")
                    key_id = item.get("kid")
                    if not isinstance(key_id, str) or not key_id or key_id in parsed:
                        raise ValueError("Invalid JWKS key identifier.")
                    if getattr(key.key, "key_size", 0) < 2048:
                        raise ValueError("Invalid JWKS signing key.")
                    parsed[key_id] = key
                self._keys = parsed
            return self._keys.get(kid)

    async def verify_token(self, token: str) -> AccessToken | None:
        if len(token) > 16384:
            return None
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if (
                header.get("alg") != "RS256"
                or not isinstance(kid, str)
                or not kid
                or len(kid) > 256
                or header.get("crit")
            ):
                return None
            key = await self._get_key(kid)
            if key is None:
                return None
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.settings.issuer_url,
                audience=self.settings.resource_url,
                options={"require": ["iss", "aud", "exp", "sub"]},
            )
            subject = claims.get("sub")
            client_id = claims.get("azp", claims.get("client_id"))
            scope = claims.get("scope", "")
            if "scope" not in claims:
                # Authelia emits an scp array; never combine competing scope claims.
                scp = claims.get("scp", [])
                if not isinstance(scp, list) or any(
                    not isinstance(value, str)
                    or not value
                    or any(not 33 <= ord(c) <= 126 or c in '\\"' for c in value)
                    for value in scp
                ):
                    return None
                scope = " ".join(scp)
            expiry = claims["exp"]
            if (
                not isinstance(subject, str)
                or subject not in self.settings.allowed_subjects
                or not isinstance(client_id, str)
                or not client_id
                or not isinstance(scope, str)
                or type(expiry) is not int
            ):
                return None
            from mcp.server.auth.provider import AccessToken

            return AccessToken(
                token=token,
                client_id=client_id,
                scopes=scope.split(),
                expires_at=expiry,
                resource=self.settings.resource_url,
                subject=subject,
                claims={"iss": self.settings.issuer_url},
            )
        except (jwt.PyJWTError, httpx.HTTPError, ValueError, TypeError, KeyError):
            return None

    async def aclose(self) -> None:
        await self._http.aclose()
