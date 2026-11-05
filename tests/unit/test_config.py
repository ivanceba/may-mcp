"""Settings reject unsafe configuration without including supplied secrets."""

import pytest

from may_mcp.config import Settings


def environment(**overrides):
    return {"MAY_BASE_URL": "https://may.invalid", "MAY_API_KEY": "synthetic-secret", **overrides}


def test_defaults_to_read_only():
    settings = Settings.from_env(environment())
    assert settings.allow_writes is False
    assert settings.base_url == "https://may.invalid"
    assert settings.api_key == "synthetic-secret"
    assert "synthetic-secret" not in repr(settings)


@pytest.mark.parametrize(("value", "expected"), [("true", True), ("false", False)])
def test_write_mode_is_exact(value, expected):
    assert Settings.from_env(environment(MAY_MCP_ALLOW_WRITES=value)).allow_writes is expected


@pytest.mark.parametrize("value", ["", "True", "FALSE", "1", "yes", " true", "false "])
def test_invalid_write_mode_is_rejected(value):
    with pytest.raises(ValueError) as error:
        Settings.from_env(environment(MAY_MCP_ALLOW_WRITES=value))
    assert "synthetic-secret" not in str(error.value)


@pytest.mark.parametrize("field", ["MAY_BASE_URL", "MAY_API_KEY"])
def test_required_fields(field):
    env = environment()
    del env[field]
    with pytest.raises(ValueError):
        Settings.from_env(env)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "file:///private",
        "may.invalid",
        "https://",
        "https://user:synthetic-secret@may.invalid",
        "https://@may.invalid",
        "https://may.invalid?token=synthetic-secret",
        "https://may.invalid/#synthetic-secret",
        "https://may.invalid:bad",
        "https://may.invalid:0",
        "https://may.invalid/../elsewhere",
        "https://may.invalid/%2e%2e",
        "https://may.invalid/\\elsewhere",
        "https://may.invalid\n",
    ],
)
def test_unsafe_base_url_is_rejected_without_echoing_input(url):
    with pytest.raises(ValueError) as error:
        Settings.from_env(environment(MAY_BASE_URL=url))
    assert "synthetic-secret" not in str(error.value)


@pytest.mark.parametrize("key", ["", " ", "synthetic-secret\n", "secret key", "secrét"])
def test_invalid_api_key_is_rejected(key):
    with pytest.raises(ValueError) as error:
        Settings.from_env(environment(MAY_API_KEY=key))
    assert "synthetic-secret" not in str(error.value)


def test_mount_prefix_is_preserved():
    assert Settings.from_env(environment(MAY_BASE_URL="https://may.invalid/may/")).base_url == (
        "https://may.invalid/may"
    )


def test_direct_construction_has_same_validation():
    with pytest.raises(ValueError):
        Settings(base_url="https://user:synthetic-secret@may.invalid", api_key="synthetic-secret")
    with pytest.raises(ValueError):
        Settings(base_url="https://may.invalid", api_key="synthetic-secret", allow_writes="false")
