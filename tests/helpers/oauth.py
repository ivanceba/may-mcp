"""Synthetic browser-form login against the disposable real Keycloak only."""

import base64
import hashlib
import re
import secrets
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit

import httpx

ISSUER = "https://127.0.0.1:15060/realms/may-mcp-test"
RESOURCE = "https://mcp.example.invalid/mcp"
SUBJECT = "90000000-0000-4000-8000-000000000001"
REDIRECT = "http://127.0.0.1:15061/callback"


class LoginForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
        self.fields = {}
        self.messages = []
        self._message = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"p", "h1", "h2"}:
            self._message = True
        if tag == "form" and attrs.get("id") == "kc-form-login":
            self.action = attrs["action"]
        if tag == "input" and attrs.get("type") == "hidden" and attrs.get("name"):
            self.fields[attrs["name"]] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag in {"p", "h1", "h2"}:
            self._message = False

    def handle_data(self, data):
        if self._message and data.strip():
            self.messages.append(data.strip())


async def authorize(http, *, client_id="synthetic-client", resource=RESOURCE, redirect=REDIRECT):
    """Perform real code+PKCE login, validating state and exact callback origin/path."""
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    state = secrets.token_urlsafe(24)
    response = await http.get(
        ISSUER + "/protocol/openid-connect/auth",
        params={
            "client_id": client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": "openid may:access",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": resource,
        },
    )
    # Existing synthetic browser session may skip the credential form.
    if response.status_code == 200:
        form = LoginForm()
        form.feed(response.text)
        assert form.action is not None, "Synthetic authorization did not present a login form."
        action = urljoin(ISSUER, form.action)
        assert urlsplit(action).netloc == "127.0.0.1:15060"
        response = await http.post(
            action,
            data={
                **form.fields,
                "username": "synthetic-oauth-user",
                "password": "synthetic-test-only-password",
                "credentialId": "",
            },
        )
    title = re.findall(r"<title>(.*?)</title>", response.text, re.S)
    errors = re.findall(r'<span[^>]*class="[^"]*error[^"]*"[^>]*>([^<]*)', response.text)
    diagnostic = LoginForm()
    diagnostic.feed(response.text)
    cookie_attributes = [(c.name, c.secure, c.domain, c.path) for c in http.cookies.jar]
    assert response.status_code == 302, (
        f"Synthetic authorization status {response.status_code}; title {title}; errors {errors}; messages {diagnostic.messages}; cookie flags {cookie_attributes}."
    )
    location = urlsplit(response.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == redirect
    values = parse_qs(location.query)
    assert values.get("state") == [state]
    assert "code" in values, "Authorization server rejected the requested resource."
    return values["code"][0], verifier


async def exchange(
    http, code, verifier, *, client_id="synthetic-client", resource=RESOURCE, redirect=REDIRECT
):
    return await http.post(
        ISSUER + "/protocol/openid-connect/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": redirect,
            "resource": resource,
        },
    )


def oidc_client(tls):
    return httpx.AsyncClient(verify=tls, trust_env=False, follow_redirects=False, timeout=15)
