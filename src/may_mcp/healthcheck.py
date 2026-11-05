"""Credential-free readiness probe for the container's fixed HTTP listener."""

import asyncio
import os
import sys

import httpx


async def check_health(
    resource_url: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> bool:
    try:
        resource = httpx.URL(resource_url)
        if (
            resource.scheme not in {"http", "https"}
            or not resource.host
            or resource.username
            or resource.password
            or not resource.path.strip("/")
            or resource.query
            or resource.fragment
        ):
            return False
        path = "/.well-known/oauth-protected-resource" + resource.path
        async with httpx.AsyncClient(
            transport=transport, trust_env=False, follow_redirects=False, timeout=2.0
        ) as client:
            response = await client.get(
                "http://127.0.0.1:8000" + path,
                headers={"Host": resource.netloc.decode("ascii")},
            )
        if response.status_code != 200:
            return False
        metadata = response.json()
        return isinstance(metadata, dict) and metadata.get("resource") == str(resource)
    except (httpx.HTTPError, httpx.InvalidURL, ValueError, UnicodeError):
        return False


def main() -> None:
    # Only the public resource URI is read; neither upstream keys nor tokens.
    healthy = asyncio.run(check_health(os.environ.get("MAY_MCP_OAUTH_RESOURCE", "")))
    sys.exit(0 if healthy else 1)


if __name__ == "__main__":
    main()
