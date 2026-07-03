# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import os
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse

import jwt
import pytz
import requests
from jwt import PyJWKClient
from requests.auth import HTTPBasicAuth

# Module imports
from plane.authentication.adapter.error import (
    AUTHENTICATION_ERROR_CODES,
    AuthenticationException,
)
from plane.authentication.adapter.oauth import OauthAdapter
from plane.license.utils.instance_value import get_configuration_value


class OIDCOAuthProvider(OauthAdapter):
    provider = "oidc"
    default_scope = "openid email profile"

    def __init__(self, request, code=None, state=None, nonce=None, callback=None):
        (
            OIDC_DISCOVERY_URL,
            OIDC_ISSUER_URL,
            OIDC_CLIENT_ID,
            OIDC_CLIENT_SECRET,
            OIDC_SCOPE,
            OIDC_CLIENT_AUTH_METHOD,
            OIDC_ALLOWED_EMAIL_DOMAINS,
            OIDC_REQUIRE_EMAIL_VERIFIED,
            OIDC_ALLOWED_GROUPS,
            OIDC_GROUPS_CLAIM,
            OIDC_ALLOWED_ROLES,
            OIDC_ROLES_CLAIM,
        ) = get_configuration_value(
            [
                {"key": "OIDC_DISCOVERY_URL", "default": os.environ.get("OIDC_DISCOVERY_URL")},
                {"key": "OIDC_ISSUER_URL", "default": os.environ.get("OIDC_ISSUER_URL")},
                {"key": "OIDC_CLIENT_ID", "default": os.environ.get("OIDC_CLIENT_ID")},
                {"key": "OIDC_CLIENT_SECRET", "default": os.environ.get("OIDC_CLIENT_SECRET")},
                {"key": "OIDC_SCOPE", "default": os.environ.get("OIDC_SCOPE", self.default_scope)},
                {
                    "key": "OIDC_CLIENT_AUTH_METHOD",
                    "default": os.environ.get("OIDC_CLIENT_AUTH_METHOD", "client_secret_post"),
                },
                {
                    "key": "OIDC_ALLOWED_EMAIL_DOMAINS",
                    "default": os.environ.get("OIDC_ALLOWED_EMAIL_DOMAINS", ""),
                },
                {
                    "key": "OIDC_REQUIRE_EMAIL_VERIFIED",
                    "default": os.environ.get("OIDC_REQUIRE_EMAIL_VERIFIED", "0"),
                },
                {"key": "OIDC_ALLOWED_GROUPS", "default": os.environ.get("OIDC_ALLOWED_GROUPS", "")},
                {"key": "OIDC_GROUPS_CLAIM", "default": os.environ.get("OIDC_GROUPS_CLAIM", "groups")},
                {"key": "OIDC_ALLOWED_ROLES", "default": os.environ.get("OIDC_ALLOWED_ROLES", "")},
                {"key": "OIDC_ROLES_CLAIM", "default": os.environ.get("OIDC_ROLES_CLAIM", "realm_access.roles")},
            ]
        )

        if not (OIDC_DISCOVERY_URL and OIDC_CLIENT_ID and OIDC_CLIENT_SECRET):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"],
                error_message="OIDC_NOT_CONFIGURED",
            )

        self.discovery_url = self._validate_url(OIDC_DISCOVERY_URL)
        self.discovery = self._get_discovery_document()
        self.issuer = OIDC_ISSUER_URL or self.discovery.get("issuer")
        self.jwks_uri = self.discovery.get("jwks_uri")
        self.allowed_email_domains = self._parse_config_list(OIDC_ALLOWED_EMAIL_DOMAINS)
        self.require_email_verified = OIDC_REQUIRE_EMAIL_VERIFIED == "1"
        self.allowed_groups = self._parse_config_list(OIDC_ALLOWED_GROUPS)
        self.groups_claim = OIDC_GROUPS_CLAIM or "groups"
        self.allowed_roles = self._parse_config_list(OIDC_ALLOWED_ROLES)
        self.roles_claim = OIDC_ROLES_CLAIM or "realm_access.roles"
        self.client_auth_method = OIDC_CLIENT_AUTH_METHOD or "client_secret_post"
        self.nonce = nonce or request.session.get("oidc_nonce")
        self.id_token_claims = {}

        self.token_url = self.discovery.get("token_endpoint")
        self.userinfo_url = self.discovery.get("userinfo_endpoint")
        authorization_endpoint = self.discovery.get("authorization_endpoint")

        if not (self.issuer and self.token_url and authorization_endpoint):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"],
                error_message="OIDC_NOT_CONFIGURED",
            )

        client_id = OIDC_CLIENT_ID
        client_secret = OIDC_CLIENT_SECRET
        scope = OIDC_SCOPE or self.default_scope
        redirect_uri = f"""{"https" if request.is_secure() else "http"}://{request.get_host()}/auth/oidc/callback/"""
        url_params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope,
            "state": state,
        }
        if self.nonce:
            url_params["nonce"] = self.nonce

        auth_url = f"{authorization_endpoint}?{urlencode(url_params)}"

        super().__init__(
            request,
            self.provider,
            client_id,
            scope,
            redirect_uri,
            auth_url,
            self.token_url,
            self.userinfo_url,
            client_secret,
            code,
            callback=callback,
        )

    def _validate_url(self, url):
        parsed = urlparse(str(url))
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"],
                error_message="OIDC_NOT_CONFIGURED",
            )
        return str(url).strip()

    def _provider_error(self):
        return AuthenticationException(
            error_code=AUTHENTICATION_ERROR_CODES["OIDC_OAUTH_PROVIDER_ERROR"],
            error_message="OIDC_OAUTH_PROVIDER_ERROR",
        )

    def _not_allowed_error(self):
        return AuthenticationException(
            error_code=AUTHENTICATION_ERROR_CODES["OIDC_USER_NOT_ALLOWED"],
            error_message="OIDC_USER_NOT_ALLOWED",
        )

    def _get_discovery_document(self):
        try:
            response = requests.get(self.discovery_url, headers={"Accept": "application/json"}, timeout=10)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise self._provider_error()
            return data
        except (ValueError, requests.RequestException):
            self.logger.warning("Error getting OIDC discovery document")
            raise self._provider_error()

    def _parse_config_list(self, value):
        if not value:
            return []
        items = []
        for chunk in str(value).replace("\n", ",").split(","):
            item = chunk.strip()
            if item:
                items.append(item)
        return items

    def _get_claim_value(self, claims, path):
        value = claims
        for part in str(path).split("."):
            if not isinstance(value, dict) or part not in value:
                return None
            value = value.get(part)
        return value

    def _normalize_claim_values(self, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value, value.lstrip("/")]
        if isinstance(value, list):
            values = []
            for item in value:
                values.extend(self._normalize_claim_values(item))
            return values
        return [str(value)]

    def _decode_id_token(self, id_token):
        try:
            unverified_header = jwt.get_unverified_header(id_token)
            algorithm = unverified_header.get("alg")
            if not algorithm or algorithm == "none":
                raise self._provider_error()

            if algorithm.startswith("HS"):
                signing_key = self.client_secret
            else:
                if not self.jwks_uri:
                    raise self._provider_error()
                jwk_client = PyJWKClient(self.jwks_uri)
                signing_key = jwk_client.get_signing_key_from_jwt(id_token).key

            return jwt.decode(
                id_token,
                signing_key,
                algorithms=[algorithm],
                audience=self.client_id,
                issuer=self.issuer,
            )
        except jwt.PyJWTError:
            self.logger.warning("Error validating OIDC id token")
            raise self._provider_error()

    def _validate_nonce(self, claims):
        expected_nonce = self.request.session.get("oidc_nonce")
        if expected_nonce and claims.get("nonce") != expected_nonce:
            raise self._provider_error()

    def _get_token_auth(self, data):
        if self.client_auth_method == "client_secret_basic":
            data.pop("client_secret", None)
            return HTTPBasicAuth(self.client_id, self.client_secret)
        return None

    def set_token_data(self):
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": self.code,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }
        auth = self._get_token_auth(data=data)
        try:
            response = requests.post(
                self.get_token_url(),
                data=data,
                headers={"Accept": "application/json"},
                auth=auth,
                timeout=10,
            )
            response.raise_for_status()
            token_response = response.json()
        except (ValueError, requests.RequestException):
            self.logger.warning("Error getting OIDC user token")
            raise self._provider_error()

        id_token = token_response.get("id_token")
        if not id_token:
            raise self._provider_error()

        self.id_token_claims = self._decode_id_token(id_token=id_token)
        self._validate_nonce(claims=self.id_token_claims)

        super().set_token_data(
            {
                "access_token": token_response.get("access_token"),
                "refresh_token": token_response.get("refresh_token", None),
                "access_token_expired_at": (
                    datetime.now(tz=pytz.utc) + timedelta(seconds=token_response.get("expires_in"))
                    if token_response.get("expires_in")
                    else None
                ),
                "refresh_token_expired_at": (
                    datetime.now(tz=pytz.utc) + timedelta(seconds=token_response.get("refresh_expires_in"))
                    if token_response.get("refresh_expires_in")
                    else None
                ),
                "id_token": id_token,
            }
        )

    def get_user_response(self):
        if not self.userinfo_url:
            return {}
        try:
            headers = {
                "Authorization": f"Bearer {self.token_data.get('access_token')}",
                "Accept": "application/json",
            }
            response = requests.get(self.userinfo_url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except (ValueError, requests.RequestException):
            self.logger.warning("Error getting OIDC user response")
            raise self._provider_error()

    def _validate_authorization(self, claims):
        email = claims.get("email")
        if not email:
            raise self._provider_error()

        if self.require_email_verified and claims.get("email_verified") is not True:
            raise self._not_allowed_error()

        if self.allowed_email_domains:
            domain = str(email).lower().split("@")[-1]
            allowed_domains = [item.lower().lstrip("@") for item in self.allowed_email_domains]
            if domain not in allowed_domains:
                raise self._not_allowed_error()

        if self.allowed_groups:
            groups = set(self._normalize_claim_values(self._get_claim_value(claims, self.groups_claim)))
            allowed_groups = set(self.allowed_groups)
            if groups.isdisjoint(allowed_groups):
                raise self._not_allowed_error()

        if self.allowed_roles:
            roles = set(self._normalize_claim_values(self._get_claim_value(claims, self.roles_claim)))
            allowed_roles = set(self.allowed_roles)
            if roles.isdisjoint(allowed_roles):
                raise self._not_allowed_error()

    def set_user_data(self):
        user_info_response = self.get_user_response()
        claims = {**self.id_token_claims, **user_info_response}
        self._validate_authorization(claims=claims)

        name = claims.get("name") or claims.get("preferred_username") or claims.get("email")

        super().set_user_data(
            {
                "email": claims.get("email"),
                "user": {
                    "provider_id": str(claims.get("sub")),
                    "email": claims.get("email"),
                    "avatar": claims.get("picture", ""),
                    "first_name": claims.get("given_name") or name or "",
                    "last_name": claims.get("family_name") or "",
                    "display_name": name,
                    "is_password_autoset": True,
                },
            }
        )
