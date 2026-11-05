"""Build/context isolation, real container transports, health and signal lifecycle."""

import asyncio
import json
import os
import shutil
import subprocess
import tarfile
import time
from contextlib import contextmanager
from pathlib import Path

import httpx2
import pytest
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from tests.helpers.oauth import ISSUER, RESOURCE, SUBJECT, authorize, exchange, oidc_client

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
IMAGE = "may-mcp-package-test"
NAME = "may-mcp-package-test"


def docker(*args, env=None, check=True, timeout=180):
    result = subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=timeout, env=env
    )
    if check and result.returncode:
        # Docker output/inspect may contain runtime test credentials: never echo it.
        pytest.fail(f"Disposable package command failed ({args[0]}, exit {result.returncode}).")
    return result


@pytest.fixture(scope="session")
def package_image(pytestconfig):
    if not pytestconfig.getoption("--may-integration") or not shutil.which("docker"):
        pytest.fail("Container tests require --may-integration and Docker on PATH.")
    docker("build", "--tag", IMAGE, str(ROOT), timeout=600)
    yield IMAGE
    docker("image", "rm", IMAGE)


def wait_health(status, *, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = json.loads(docker("inspect", "--format", "{{json .State}}", NAME).stdout)
        if not state["Running"]:
            pytest.fail("Disposable package process exited before readiness.")
        if state.get("Health", {}).get("Status") == status:
            return
        time.sleep(0.2)
    pytest.fail(f"Disposable package did not become {status}.")


@pytest.fixture
def http_container(package_image, may_test_instance, oauth_provider):
    _, _, _, directory = oauth_provider

    @contextmanager
    def start(writes):
        if docker("container", "inspect", NAME, check=False).returncode == 0:
            pytest.fail("Package test container already exists; inspect it before retry.")
        values = {
            "MAY_BASE_URL": "http://may:5050",
            "MAY_API_KEY": may_test_instance.api_key,
            "MAY_MCP_ALLOW_WRITES": "true" if writes else "false",
            "MAY_MCP_OAUTH_ISSUER": ISSUER,
            "MAY_MCP_OAUTH_RESOURCE": RESOURCE,
            "MAY_MCP_OAUTH_JWKS_URL": "https://keycloak:8443/realms/may-mcp-test/protocol/openid-connect/certs",
            "MAY_MCP_OAUTH_ALLOWED_SUBJECTS": SUBJECT,
        }
        args = [
            "run",
            "--detach",
            "--name",
            NAME,
            "--network",
            "may-mcp-test_default",
            "--publish",
            "127.0.0.1:15070:8000",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=16m",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--health-interval",
            "1s",
            "--health-start-period",
            "0s",
            "--health-retries",
            "2",
            "--mount",
            f"type=bind,src={directory / 'cert.pem'},dst=/app/.venv/lib/python3.12/site-packages/certifi/cacert.pem,readonly",
        ]
        for key in values:
            args += ["--env", key]
        try:
            docker(*args, package_image, env={**os.environ, **values})
            docker("network", "connect", "may-mcp-oauth-test_default", NAME)
            wait_health("healthy")
            yield
        finally:
            docker("kill", "--signal", "CONT", NAME, check=False)
            docker("stop", "--time", "15", NAME, check=False)
            docker("rm", "--force", NAME, check=False)

    return start


def test_real_build_context_excludes_private_inputs(package_image, tmp_path):
    context = tmp_path / "context"
    context.mkdir()
    for filename in (
        "Dockerfile",
        ".dockerignore",
        "pyproject.toml",
        "uv.lock",
        "README.md",
        "LICENSE",
    ):
        shutil.copy2(ROOT / filename, context / filename)
    shutil.copytree(ROOT / "src", context / "src", ignore=shutil.ignore_patterns("__pycache__"))
    denied = [
        ".env",
        "data/private.db",
        "docs/superpowers/plan.md",
        ".venv/private.txt",
        ".git/private",
        "src/may_mcp/private.key",
        "src/may_mcp/__pycache__/private.pyc",
    ]
    for filename in denied:
        target = context / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("synthetic-context-canary", encoding="utf-8")
    image = IMAGE + "-context"
    name = NAME + "-context"
    if docker("container", "inspect", name, check=False).returncode == 0:
        pytest.fail("Context test container already exists; inspect before retry.")
    try:
        docker("build", "--target", "build-context", "--tag", image, str(context), timeout=600)
        docker("create", "--name", name, image, "/not-executed")
        archive = tmp_path / "context.tar"
        docker("export", "--output", str(archive), name)
        with tarfile.open(archive) as files:
            names = {member.name for member in files}
        assert "src/may_mcp/healthcheck.py" in names
        for filename in denied:
            assert filename not in names
    finally:
        docker("rm", "--force", name, check=False)
        docker("image", "rm", image, check=False)


def test_runtime_is_nonroot_and_has_no_development_dependencies(package_image):
    docker(
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--entrypoint",
        "python",
        package_image,
        "-c",
        "import os, importlib.util, may_mcp; assert os.getuid() == 10001; assert os.getgid() == 10001; assert importlib.util.find_spec('pytest') is None; assert importlib.util.find_spec('ruff') is None; assert may_mcp.__file__.startswith('/app/.venv/'); assert not os.path.exists('/app/src')",
    )


@pytest.mark.parametrize("writes", [True, False])
async def test_real_http_container_restart_health_and_shutdown(
    http_container, oauth_provider, may_test_instance, writes
):
    _, _, tls, _ = oauth_provider
    async with oidc_client(tls) as oidc:
        code, proof = await authorize(oidc)
        issued = await exchange(oidc, code, proof)
        assert issued.status_code == 200
        access = issued.json()["access_token"]
    with http_container(writes):
        for restart in (False, True):
            if restart:
                docker("restart", "--time", "15", NAME)
                wait_health("healthy")
            async with (
                httpx2.AsyncClient(
                    trust_env=False,
                    headers={"Host": "mcp.example.invalid", "Authorization": "Bearer " + access},
                ) as http,
                Client(
                    streamable_http_client("http://127.0.0.1:15070/mcp", http_client=http),
                    mode="legacy",
                    cache=None,
                ) as client,
            ):
                names = {tool.name for tool in (await client.list_tools()).tools}
                assert ("may_create_vehicle" in names) is writes
                read = await client.call_tool(
                    "may_get_vehicle", {"vehicle_id": may_test_instance.vehicle_id}
                )
                assert read.is_error is not True
                assert read.structured_content["name"] == "MCP synthetic vehicle"
                if writes:
                    created = await client.call_tool(
                        "may_create_vehicle",
                        {"vehicle": {"name": "Container synthetic vehicle", "vehicle_type": "car"}},
                    )
                    assert created.is_error is not True
                    identifier = created.structured_content["id"]
                    try:
                        changed = await client.call_tool(
                            "may_update_vehicle",
                            {"vehicle_id": identifier, "changes": {"name": "Container changed"}},
                        )
                        assert changed.is_error is not True
                    finally:
                        assert (
                            await client.call_tool("may_delete_vehicle", {"vehicle_id": identifier})
                        ).is_error is not True
                else:
                    assert (
                        await client.call_tool(
                            "may_delete_vehicle", {"vehicle_id": may_test_instance.vehicle_id}
                        )
                    ).is_error is True
        if not writes:
            docker("kill", "--signal", "STOP", NAME)
            try:
                wait_health("unhealthy", timeout=30)
            finally:
                docker("kill", "--signal", "CONT", NAME)
            wait_health("healthy")
        docker("stop", "--time", "15", NAME)
        state = json.loads(docker("inspect", "--format", "{{json .State}}", NAME).stdout)
        assert state["Running"] is False
        assert state["OOMKilled"] is False
        assert state["ExitCode"] in {0, 143}  # Uvicorn re-raises SIGTERM after ASGI shutdown.


async def test_stdio_container_discovers_and_reads(package_image, may_test_instance):
    name = NAME + "-stdio"
    if docker("container", "inspect", name, check=False).returncode == 0:
        pytest.fail("Stdio package container already exists; inspect before retry.")
    environment = {
        **os.environ,
        "MAY_BASE_URL": "http://may:5050",
        "MAY_API_KEY": may_test_instance.api_key,
        "MAY_MCP_ALLOW_WRITES": "false",
    }
    parameters = StdioServerParameters(
        command="docker",
        args=[
            "run",
            "--rm",
            "--interactive",
            "--name",
            name,
            "--network",
            "may-mcp-test_default",
            "--no-healthcheck",
            "--env",
            "MAY_BASE_URL",
            "--env",
            "MAY_API_KEY",
            "--env",
            "MAY_MCP_ALLOW_WRITES",
            package_image,
            "--transport",
            "stdio",
        ],
        env=environment,
    )
    try:
        async with asyncio.timeout(40), Client(parameters, mode="legacy", cache=None) as client:
            assert "may_get_vehicle" in {tool.name for tool in (await client.list_tools()).tools}
            read = await client.call_tool(
                "may_get_vehicle", {"vehicle_id": may_test_instance.vehicle_id}
            )
            assert read.is_error is not True
            assert read.structured_content["name"] == "MCP synthetic vehicle"
    finally:
        docker("rm", "--force", name, check=False)


def test_compose_example_renders_without_exposing_values(package_image):
    values = {
        "MAY_BASE_URL": "https://may.example.invalid",
        "MAY_API_KEY": "synthetic-runtime-only-key",
        "MAY_MCP_OAUTH_ISSUER": "https://idp.example.invalid/realm",
        "MAY_MCP_OAUTH_RESOURCE": RESOURCE,
        "MAY_MCP_OAUTH_JWKS_URL": "https://idp.example.invalid/certs",
        "MAY_MCP_OAUTH_ALLOWED_SUBJECTS": "synthetic-user",
    }
    result = docker(
        "compose",
        "-f",
        str(ROOT / "compose.example.yml"),
        "config",
        "--format",
        "json",
        env={**os.environ, **values},
    )
    service = json.loads(result.stdout)["services"]["may-mcp"]
    assert service["read_only"] is True
    assert service["environment"]["MAY_MCP_ALLOW_WRITES"] == "false"
    assert service["cap_drop"] == ["ALL"]
