# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from django.test import RequestFactory

from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES, AuthenticationException
from plane.authentication.provider.oauth.oidc import OIDCOAuthProvider

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


def patch_oidc_http(monkeypatch, claims, issuer="https://auth.example.com/application/o/plane/"):
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
            return MockResponse({})
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
