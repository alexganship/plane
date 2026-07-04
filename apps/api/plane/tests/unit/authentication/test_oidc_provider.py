# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from django.test import RequestFactory

from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES, AuthenticationException
from plane.authentication.provider.oauth.oidc import OIDCOAuthProvider
from plane.authentication.views.app.oidc import OIDCCallbackEndpoint, OIDCOauthInitiateEndpoint
from plane.authentication.views.space.oidc import OIDCCallbackSpaceEndpoint

OIDC_CLIENT_SECRET = "test-oidc-client-secret-with-32-bytes"


class MockResponse:
    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code
        self.ok = status_code < 400

    def raise_for_status(self):
        if not self.ok:
            raise Exception("request failed")

    def json(self):
        return self.data


def make_request():
    request = RequestFactory().get("/auth/oidc/callback/", HTTP_HOST="plane.test")
    request.session = {"oidc_nonce": "nonce"}
    return request


def make_config(**overrides):
    config = {
        "OIDC_DISCOVERY_URL": "https://auth.example.com/application/o/plane/.well-known/openid-configuration",
        "OIDC_ISSUER_URL": "",
        "OIDC_CLIENT_ID": "plane",
        "OIDC_CLIENT_SECRET": OIDC_CLIENT_SECRET,
        "OIDC_SCOPE": "openid email profile",
        "OIDC_CLIENT_AUTH_METHOD": "client_secret_post",
        "OIDC_ALLOWED_EMAIL_DOMAINS": "",
        "OIDC_REQUIRE_EMAIL_VERIFIED": "0",
        "OIDC_ALLOWED_GROUPS": "",
        "OIDC_GROUPS_CLAIM": "groups",
        "OIDC_ALLOWED_ROLES": "",
        "OIDC_ROLES_CLAIM": "realm_access.roles",
    }
    config.update(overrides)
    return config


def patch_config(monkeypatch, config):
    monkeypatch.setattr(
        "plane.authentication.provider.oauth.oidc.get_configuration_value",
        lambda keys: tuple(config.get(item["key"], item.get("default")) for item in keys),
    )


def patch_oidc_http(monkeypatch, claims, issuer="https://auth.example.com/application/o/plane/", userinfo_claims=None):
    id_token = jwt.encode(
        {
            "iss": issuer,
            "aud": "plane",
            "sub": "user-1",
            "email": "user@example.com",
            "nonce": "nonce",
            "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=5),
            "iat": datetime.now(tz=timezone.utc),
            **claims,
        },
        OIDC_CLIENT_SECRET,
        algorithm="HS256",
    )

    discovery = {
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}authorize",
        "token_endpoint": f"{issuer}token",
        "userinfo_endpoint": f"{issuer}userinfo",
        "jwks_uri": f"{issuer}jwks",
    }

    def mock_get(url, *args, **kwargs):
        if url.endswith(".well-known/openid-configuration"):
            return MockResponse(discovery)
        if url.endswith("userinfo"):
            return MockResponse(userinfo_claims or {})
        return MockResponse({}, status_code=404)

    def mock_post(url, *args, **kwargs):
        return MockResponse({"access_token": "access", "id_token": id_token, "expires_in": 300})

    monkeypatch.setattr("plane.authentication.provider.oauth.oidc.requests.get", mock_get)
    monkeypatch.setattr("plane.authentication.provider.oauth.oidc.requests.post", mock_post)


def test_authentik_style_groups_allow_login_with_unverified_email(monkeypatch):
    config = make_config(OIDC_ALLOWED_GROUPS="plane-users", OIDC_GROUPS_CLAIM="groups")
    patch_config(monkeypatch, config)
    patch_oidc_http(monkeypatch, {"email_verified": False, "groups": ["plane-users"]})

    provider = OIDCOAuthProvider(request=make_request(), code="code")

    provider.set_token_data()
    provider.set_user_data()

    assert provider.user_data["email"] == "user@example.com"
    assert provider.user_data["user"]["provider_id"] == "user-1"


def test_authentik_style_groups_reject_disallowed_user(monkeypatch):
    config = make_config(OIDC_ALLOWED_GROUPS="plane-users", OIDC_GROUPS_CLAIM="groups")
    patch_config(monkeypatch, config)
    patch_oidc_http(monkeypatch, {"groups": ["other-group"]})

    provider = OIDCOAuthProvider(request=make_request(), code="code")
    provider.set_token_data()

    with pytest.raises(AuthenticationException) as exc:
        provider.set_user_data()

    assert exc.value.error_code == AUTHENTICATION_ERROR_CODES["OIDC_USER_NOT_ALLOWED"]


def test_keycloak_realm_roles_allow_login(monkeypatch):
    config = make_config(OIDC_ALLOWED_ROLES="plane-user", OIDC_ROLES_CLAIM="realm_access.roles")
    patch_config(monkeypatch, config)
    patch_oidc_http(monkeypatch, {"realm_access": {"roles": ["plane-user"]}})

    provider = OIDCOAuthProvider(request=make_request(), code="code")

    provider.set_token_data()
    provider.set_user_data()

    assert provider.user_data["email"] == "user@example.com"


def test_keycloak_client_roles_allow_login(monkeypatch):
    config = make_config(OIDC_ALLOWED_ROLES="plane-user", OIDC_ROLES_CLAIM="resource_access.plane.roles")
    patch_config(monkeypatch, config)
    patch_oidc_http(monkeypatch, {"resource_access": {"plane": {"roles": ["plane-user"]}}})

    provider = OIDCOAuthProvider(request=make_request(), code="code")

    provider.set_token_data()
    provider.set_user_data()

    assert provider.user_data["email"] == "user@example.com"


def test_userinfo_sub_must_match_id_token_sub(monkeypatch):
    config = make_config()
    patch_config(monkeypatch, config)
    patch_oidc_http(monkeypatch, {}, userinfo_claims={"sub": "different-user"})

    provider = OIDCOAuthProvider(request=make_request(), code="code")
    provider.set_token_data()

    with pytest.raises(AuthenticationException) as exc:
        provider.set_user_data()

    assert exc.value.error_code == AUTHENTICATION_ERROR_CODES["OIDC_OAUTH_PROVIDER_ERROR"]


def test_nonce_is_required_for_token_validation(monkeypatch):
    config = make_config()
    patch_config(monkeypatch, config)
    patch_oidc_http(monkeypatch, {})
    request = make_request()
    request.session = {}

    provider = OIDCOAuthProvider(request=request, code="code")

    with pytest.raises(AuthenticationException) as exc:
        provider.set_token_data()

    assert exc.value.error_code == AUTHENTICATION_ERROR_CODES["OIDC_OAUTH_PROVIDER_ERROR"]


def test_space_callback_url_is_used_for_space_flow(monkeypatch):
    config = make_config()
    patch_config(monkeypatch, config)
    patch_oidc_http(monkeypatch, {})
    request = make_request()

    provider = OIDCOAuthProvider(request=request, state="state", nonce="nonce", is_space=True)

    assert provider.redirect_uri == "http://plane.test/auth/spaces/oidc/callback/"
    assert "redirect_uri=http%3A%2F%2Fplane.test%2Fauth%2Fspaces%2Foidc%2Fcallback%2F" in provider.auth_url


def test_callback_rejects_missing_session_state_and_nonce():
    request = RequestFactory().get("/auth/oidc/callback/?code=code&state=")
    request.session = {}

    response = OIDCCallbackEndpoint.as_view()(request)

    assert response.status_code == 302
    assert f"error_code={AUTHENTICATION_ERROR_CODES['OIDC_OAUTH_PROVIDER_ERROR']}" in response["Location"]


def test_app_callback_does_not_clear_other_oauth_session_state():
    request = RequestFactory().get("/auth/oidc/callback/?code=code&state=wrong")
    request.session = {
        "state": "github-state",
        "next_path": "/workspace",
        "oidc_state": "oidc-state",
        "oidc_nonce": "nonce",
        "oidc_next_path": "/oidc-path",
    }

    response = OIDCCallbackEndpoint.as_view()(request)

    assert response.status_code == 302
    assert request.session["state"] == "github-state"
    assert request.session["next_path"] == "/workspace"
    assert "oidc_state" not in request.session
    assert "oidc_nonce" not in request.session
    assert "oidc_next_path" not in request.session


def test_space_callback_does_not_clear_other_oauth_session_state():
    request = RequestFactory().get("/auth/spaces/oidc/callback/?code=code&state=wrong")
    request.session = {
        "state": "gitlab-state",
        "next_path": "/workspace/project",
        "oidc_state": "oidc-state",
        "oidc_nonce": "nonce",
        "oidc_next_path": "/space-path",
    }

    response = OIDCCallbackSpaceEndpoint.as_view()(request)

    assert response.status_code == 302
    assert request.session["state"] == "gitlab-state"
    assert request.session["next_path"] == "/workspace/project"
    assert "oidc_state" not in request.session
    assert "oidc_nonce" not in request.session
    assert "oidc_next_path" not in request.session


def test_callback_uses_oidc_state_not_generic_oauth_state():
    request = RequestFactory().get("/auth/oidc/callback/?code=code&state=github-state")
    request.session = {
        "state": "github-state",
        "oidc_state": "oidc-state",
        "oidc_nonce": "nonce",
    }

    response = OIDCCallbackEndpoint.as_view()(request)

    assert response.status_code == 302
    assert f"error_code={AUTHENTICATION_ERROR_CODES['OIDC_OAUTH_PROVIDER_ERROR']}" in response["Location"]
    assert request.session["state"] == "github-state"


def test_initiate_rejects_when_oidc_is_disabled(monkeypatch):
    class FakeInstance:
        is_setup_done = True

    monkeypatch.setattr("plane.authentication.views.app.oidc.Instance.objects.first", lambda: FakeInstance())
    monkeypatch.setattr("plane.authentication.views.app.oidc.get_configuration_value", lambda keys: ("0",))
    request = RequestFactory().get("/auth/oidc/")
    request.session = {}

    response = OIDCOauthInitiateEndpoint.as_view()(request)

    assert response.status_code == 302
    assert f"error_code={AUTHENTICATION_ERROR_CODES['OIDC_NOT_CONFIGURED']}" in response["Location"]
