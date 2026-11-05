"""Lifecycle of one explicitly opted-in disposable May instance."""

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest


@dataclass(frozen=True)
class MayTestInstance:
    base_url: str
    api_key: str = field(repr=False)
    other_api_key: str = field(repr=False)
    vehicle_id: int
    other_vehicle_id: int


@pytest.fixture(scope="session")
def may_test_instance(pytestconfig):
    if not pytestconfig.getoption("--may-integration"):
        pytest.fail("Real May was not provisioned: rerun with --may-integration (Docker required).")

    root = Path(__file__).resolve().parents[2]
    compose_file = str(root / "compose.test.yml")
    if shutil.which("docker"):
        command = ["docker"]
    else:
        pytest.fail("Docker Compose must be on PATH; for WSL Docker, run pytest inside WSL.")
    command += ["compose", "--project-name", "may-mcp-test", "-f", compose_file]

    def run(*args, source=None, timeout=180):
        result = subprocess.run(
            [*command, *args], input=source, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode:
            # Captured output may contain generated test credentials; never echo it.
            pytest.fail(f"Disposable May command failed ({args[0]}, exit {result.returncode}).")
        return result.stdout

    if run("ps", "--all", "--quiet").strip():
        pytest.fail("Test project already exists; inspect it before explicit cleanup and retry.")

    try:
        run("up", "-d", "--wait", "--wait-timeout", "120", timeout=600)
        run(
            "exec",
            "-T",
            "--user",
            "may",
            "may",
            "python",
            "-",
            source=(root / "scripts/provision_test_may.py").read_text(encoding="utf-8"),
        )
        data = json.loads(
            run("exec", "-T", "--user", "may", "may", "cat", "/app/data/mcp-test.json")
        )
        yield MayTestInstance(base_url="http://127.0.0.1:15050", **data)
    finally:
        run("down", "--volumes", "--remove-orphans")
