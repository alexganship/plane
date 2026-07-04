# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import os
import uuid

# Django imports
from django.http import HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

# Module imports
from plane.authentication.adapter.error import (
    AUTHENTICATION_ERROR_CODES,
    AuthenticationException,
)
from plane.authentication.provider.oauth.oidc import OIDCOAuthProvider
from plane.authentication.utils.host import base_host
from plane.authentication.utils.login import user_login
from plane.license.models import Instance
from plane.license.utils.instance_value import get_configuration_value
from plane.utils.path_validator import get_allowed_hosts, get_safe_redirect_url, validate_next_path


def _clear_oidc_session(request):
    request.session.pop("oidc_state", None)
    request.session.pop("oidc_nonce", None)
    request.session.pop("oidc_next_path", None)


def _is_oidc_enabled():
    (is_oidc_enabled,) = get_configuration_value(
        [{"key": "IS_OIDC_ENABLED", "default": os.environ.get("IS_OIDC_ENABLED", "0")}]
    )
    return is_oidc_enabled == "1"


class OIDCOauthInitiateSpaceEndpoint(View):
    def get(self, request):
        request.session["host"] = base_host(request=request, is_space=True)
        next_path = request.GET.get("next_path")
        if next_path:
            request.session["oidc_next_path"] = str(next_path)

        instance = Instance.objects.first()
        if instance is None or not instance.is_setup_done:
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["INSTANCE_NOT_CONFIGURED"],
                error_message="INSTANCE_NOT_CONFIGURED",
            )
            params = exc.get_error_dict()
            url = get_safe_redirect_url(
                base_url=base_host(request=request, is_space=True), next_path=next_path, params=params
            )
            return HttpResponseRedirect(url)

        if not _is_oidc_enabled():
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"],
                error_message="OIDC_NOT_CONFIGURED",
            )
            params = exc.get_error_dict()
            url = get_safe_redirect_url(
                base_url=base_host(request=request, is_space=True), next_path=next_path, params=params
            )
            return HttpResponseRedirect(url)

        try:
            state = uuid.uuid4().hex
            nonce = uuid.uuid4().hex
            provider = OIDCOAuthProvider(request=request, state=state, nonce=nonce, is_space=True)
            request.session["oidc_state"] = state
            request.session["oidc_nonce"] = nonce
            return HttpResponseRedirect(provider.get_auth_url())
        except AuthenticationException as e:
            params = e.get_error_dict()
            url = get_safe_redirect_url(
                base_url=base_host(request=request, is_space=True), next_path=next_path, params=params
            )
            return HttpResponseRedirect(url)


class OIDCCallbackSpaceEndpoint(View):
    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")
        host = request.session.get("host")
        next_path = request.session.get("oidc_next_path")
        session_state = request.session.get("oidc_state")
        session_nonce = request.session.get("oidc_nonce")

        if not session_state or not session_nonce or not state or state != session_state:
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_OAUTH_PROVIDER_ERROR"],
                error_message="OIDC_OAUTH_PROVIDER_ERROR",
            )
            params = exc.get_error_dict()
            url = get_safe_redirect_url(
                base_url=base_host(request=request, is_space=True), next_path=next_path, params=params
            )
            _clear_oidc_session(request=request)
            return HttpResponseRedirect(url)

        if not code:
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_OAUTH_PROVIDER_ERROR"],
                error_message="OIDC_OAUTH_PROVIDER_ERROR",
            )
            params = exc.get_error_dict()
            url = get_safe_redirect_url(
                base_url=base_host(request=request, is_space=True), next_path=next_path, params=params
            )
            _clear_oidc_session(request=request)
            return HttpResponseRedirect(url)

        try:
            provider = OIDCOAuthProvider(request=request, code=code, is_space=True)
            user = provider.authenticate()
            user_login(request=request, user=user, is_space=True)
            next_path = validate_next_path(next_path=next_path)
            url = f"{host.rstrip('/')}{next_path}" if host else base_host(request=request, is_space=True)
            if url_has_allowed_host_and_scheme(url, allowed_hosts=get_allowed_hosts()):
                _clear_oidc_session(request=request)
                return HttpResponseRedirect(url)
            _clear_oidc_session(request=request)
            return HttpResponseRedirect(base_host(request=request, is_space=True))
        except AuthenticationException as e:
            params = e.get_error_dict()
            url = get_safe_redirect_url(
                base_url=base_host(request=request, is_space=True), next_path=next_path, params=params
            )
            _clear_oidc_session(request=request)
            return HttpResponseRedirect(url)
