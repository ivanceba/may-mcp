"""Invalid startup configuration must never emit protocol noise or secrets."""

import os
import subprocess
import sys


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
