"""Lifecycle of one explicitly opted-in disposable May instance."""

import ipaddress
import json
import os
import shutil
import ssl
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa


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


@pytest.fixture(scope="session")
def oauth_provider(pytestconfig, request):
    if not pytestconfig.getoption("--may-integration"):
        pytest.fail("Disposable OAuth requires --may-integration and Docker.")
    if not shutil.which("docker"):
        pytest.fail("Run inside WSL when Docker is available there.")
    root = Path(__file__).resolve().parents[2]
    command = [
        "docker",
        "compose",
        "--project-name",
        "may-mcp-oauth-test",
        "-f",
        str(root / "compose.oauth-test.yml"),
    ]
    temporary = tempfile.TemporaryDirectory(prefix="may-mcp-oauth-test-")
    request.addfinalizer(temporary.cleanup)
    directory = Path(temporary.name)
    directory.chmod(0o755)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "Synthetic OAuth test")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(minutes=1))
        .not_valid_after(datetime.now(UTC) + timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(key, hashes.SHA256())
    )
    (directory / "cert.pem").write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    (directory / "key.pem").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    # A fresh synthetic test key, readable across host/container UIDs only for this mount.
    (directory / "key.pem").chmod(0o644)
    tls = ssl.create_default_context(cafile=str(directory / "cert.pem"))
    environment = {**os.environ, "MAY_MCP_TEST_TLS_DIR": str(directory)}

    def run(*args, timeout=180):
        result = subprocess.run(
            [*command, *args], capture_output=True, text=True, timeout=timeout, env=environment
        )
        if result.returncode:
            pytest.fail(f"Disposable OAuth command failed ({args[0]}, exit {result.returncode}).")
        return result.stdout

    volumes = subprocess.run(
        [
            "docker",
            "volume",
            "ls",
            "-q",
            "--filter",
            "label=com.docker.compose.project=may-mcp-oauth-test",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    if run("ps", "--all", "--quiet").strip() or volumes.stdout.strip():
        pytest.fail("OAuth test project/state already exists; inspect before cleanup and retry.")

    def ready():
        deadline = time.monotonic() + 120
        with httpx.Client(trust_env=False, timeout=2, verify=tls) as client:
            while time.monotonic() < deadline:
                try:
                    response = client.get(
                        "https://127.0.0.1:15060/realms/may-mcp-test/.well-known/openid-configuration"
                    )
                    if (
                        response.status_code == 200
                        and response.json().get("issuer")
                        == "https://127.0.0.1:15060/realms/may-mcp-test"
                    ):
                        return response.json()
                except (httpx.HTTPError, ValueError):
                    pass
                time.sleep(0.5)
        pytest.fail("Disposable OAuth provider did not publish expected discovery metadata.")

    try:
        run("up", "-d", timeout=600)
        metadata = ready()

        def restart():
            run("restart", "keycloak")
            return ready()

        yield metadata, restart, tls
    finally:
        run("down", "--volumes", "--remove-orphans")
