"""Invalid startup configuration must never emit protocol noise or secrets."""

import os
import subprocess
import sys

import pytest


def test_invalid_startup_exits_safely_on_stderr():
    result = subprocess.run(
        [sys.executable, "-m", "may_mcp"],
        env={
            **os.environ,
            "MAY_BASE_URL": "https://may.invalid",
            "MAY_API_KEY": "synthetic-secret",
            "MAY_MCP_ALLOW_WRITES": "synthetic-secret",
        },
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert "configuration" in result.stderr.lower()
    assert "synthetic-secret" not in result.stderr


@pytest.mark.parametrize(
    "setting,value",
    [
        ("MAY_MCP_OAUTH_ISSUER", "http://private-secret.invalid"),
        ("MAY_MCP_OAUTH_ALLOWED_SUBJECTS", ""),
    ],
)
def test_http_startup_rejects_unsafe_oauth_on_stderr(setting, value):
    result = subprocess.run(
        [sys.executable, "-m", "may_mcp", "--transport", "http"],
        env={
            **os.environ,
            "MAY_BASE_URL": "https://may.invalid",
            "MAY_API_KEY": "synthetic-secret",
            "MAY_MCP_ALLOW_WRITES": "false",
            "MAY_MCP_OAUTH_ISSUER": "https://idp.invalid/realm",
            "MAY_MCP_OAUTH_RESOURCE": "https://mcp.example.invalid/mcp",
            "MAY_MCP_OAUTH_JWKS_URL": "https://idp.invalid/certs",
            "MAY_MCP_OAUTH_ALLOWED_SUBJECTS": "synthetic-user",
            setting: value,
        },
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert "configuration" in result.stderr.lower()
    assert "secret" not in result.stderr
