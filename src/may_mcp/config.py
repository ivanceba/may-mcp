"""Validated, immutable configuration for one May instance."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str = field(repr=False)
    allow_writes: bool = False

    def __post_init__(self) -> None:
        if type(self.allow_writes) is not bool:
            raise ValueError("allow_writes must be a boolean.")
        if not self.api_key or any(not 33 <= ord(char) <= 126 for char in self.api_key):
            raise ValueError("MAY_API_KEY must be a nonempty printable ASCII token.")
        try:
            url = urlsplit(self.base_url)
            valid = (
                url.scheme in {"http", "https"}
                and bool(url.hostname)
                and url.username is None
                and url.password is None
                and (url.port is None or url.port > 0)
                and not url.query
                and not url.fragment
                and not any(char.isspace() or ord(char) < 32 for char in self.base_url)
                and not any(char in self.base_url for char in "\\%?#")
                and not any(segment in {".", ".."} for segment in url.path.split("/"))
                and "//" not in url.path
            )
            normalized = str(httpx.URL(self.base_url)).rstrip("/") if valid else ""
        except (ValueError, httpx.InvalidURL):
            normalized = ""
        if not normalized:
            raise ValueError("MAY_BASE_URL must be an HTTP(S) instance URL without credentials.")
        object.__setattr__(self, "base_url", normalized)

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        mode = env.get("MAY_MCP_ALLOW_WRITES", "false")
        if mode not in {"true", "false"}:
            raise ValueError("MAY_MCP_ALLOW_WRITES must be exactly true or false.")
        return cls(
            base_url=env.get("MAY_BASE_URL", ""),
            api_key=env.get("MAY_API_KEY", ""),
            allow_writes=mode == "true",
        )
