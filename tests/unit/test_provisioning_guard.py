"""The provisioner must refuse normal environments before importing May."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("flag", "database"),
    [("0", "sqlite:////app/data/may.db"), ("1", "sqlite:////somewhere/production.db")],
)
def test_provisioner_refuses_non_test_environment(flag, database):
    script = Path(__file__).resolve().parents[2] / "scripts/provision_test_may.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        env={**os.environ, "MAY_MCP_TEST_INSTANCE": flag, "DATABASE_URL": database},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "Provisioning requires the isolated May test container." in result.stderr
    assert result.stdout == ""
