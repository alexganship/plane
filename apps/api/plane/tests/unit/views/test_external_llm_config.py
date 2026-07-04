# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from plane.app.views.external import base
from plane.utils.instance_config_variables.core import llm_config_variables


@pytest.mark.unit
class TestExternalLLMConfig:
    def test_llm_base_url_instance_config_key(self):
        config_by_key = {config["key"]: config for config in llm_config_variables}

        assert config_by_key["LLM_OPENAI_COMPATIBLE_API_KEY"] == {
            "key": "LLM_OPENAI_COMPATIBLE_API_KEY",
            "value": os.environ.get("LLM_OPENAI_COMPATIBLE_API_KEY"),
            "category": "AI",
            "is_encrypted": True,
        }
        assert config_by_key["LLM_BASE_URL"] == {
            "key": "LLM_BASE_URL",
            "value": os.environ.get("LLM_BASE_URL", ""),
            "category": "AI",
            "is_encrypted": False,
        }

    @patch("plane.app.views.external.base.log_exception")
    @patch("plane.app.views.external.base.get_configuration_value")
    def test_openai_requires_known_model_and_does_not_use_base_url(
        self, mock_get_configuration_value, mock_log_exception
    ):
        mock_get_configuration_value.return_value = (
            "sk-test",
            "",
            "openai",
            "gpt-4o-mini",
            "http://localhost:11434/v1",
        )

        llm_config = base.get_llm_config()

        assert llm_config.error is None
        assert llm_config.api_key == "sk-test"
        assert llm_config.model == "gpt-4o-mini"
        assert llm_config.provider == "openai"
        assert llm_config.base_url is None
        mock_log_exception.assert_not_called()

    @patch("plane.app.views.external.base.log_exception")
    @patch("plane.app.views.external.base.get_configuration_value")
    def test_openai_rejects_missing_api_key(
        self, mock_get_configuration_value, mock_log_exception
    ):
        mock_get_configuration_value.return_value = ("", "", "openai", "gpt-4o-mini", "")

        llm_config = base.get_llm_config()

        assert llm_config.error == "LLM_API_KEY is required for openai provider"
        assert llm_config.api_key is None
        mock_log_exception.assert_called_once()

    @patch("plane.app.views.external.base.log_exception")
    @patch("plane.app.views.external.base.get_configuration_value")
    def test_openai_uses_default_model_when_model_is_blank(
        self, mock_get_configuration_value, mock_log_exception
    ):
        mock_get_configuration_value.return_value = ("sk-test", "", "openai", "", "")

        llm_config = base.get_llm_config()

        assert llm_config.error is None
        assert llm_config.api_key == "sk-test"
        assert llm_config.model == "gpt-4o-mini"
        assert llm_config.provider == "openai"
        mock_log_exception.assert_not_called()

    @patch("plane.app.views.external.base.log_exception")
    @patch("plane.app.views.external.base.get_configuration_value")
    def test_openai_compatible_accepts_blank_api_key_and_arbitrary_model(
        self, mock_get_configuration_value, mock_log_exception
    ):
        mock_get_configuration_value.return_value = (
            "",
            "",
            "openai_compatible",
            "llama3.1:8b",
            "http://localhost:11434/v1",
        )

        llm_config = base.get_llm_config()

        assert llm_config.error is None
        assert llm_config.api_key == base.OPENAI_COMPATIBLE_PLACEHOLDER_API_KEY
        assert llm_config.model == "llama3.1:8b"
        assert llm_config.provider == "openai_compatible"
        assert llm_config.base_url == "http://localhost:11434/v1"
        mock_log_exception.assert_not_called()

    @patch("plane.app.views.external.base.log_exception")
    @patch("plane.app.views.external.base.get_configuration_value")
    def test_openai_compatible_does_not_reuse_openai_api_key(
        self, mock_get_configuration_value, mock_log_exception
    ):
        mock_get_configuration_value.return_value = (
            "sk-official-openai",
            "",
            "openai_compatible",
            "llama3.1:8b",
            "http://localhost:11434/v1",
        )

        llm_config = base.get_llm_config()

        assert llm_config.error is None
        assert llm_config.api_key == base.OPENAI_COMPATIBLE_PLACEHOLDER_API_KEY
        mock_log_exception.assert_not_called()

    @patch("plane.app.views.external.base.log_exception")
    @patch("plane.app.views.external.base.get_configuration_value")
    def test_openai_compatible_uses_compatible_api_key(
        self, mock_get_configuration_value, mock_log_exception
    ):
        mock_get_configuration_value.return_value = (
            "sk-official-openai",
            "sk-compatible",
            "openai_compatible",
            "llama3.1:8b",
            "http://localhost:11434/v1",
        )

        llm_config = base.get_llm_config()

        assert llm_config.error is None
        assert llm_config.api_key == "sk-compatible"
        mock_log_exception.assert_not_called()

    @patch("plane.app.views.external.base.log_exception")
    @patch("plane.app.views.external.base.get_configuration_value")
    def test_openai_compatible_requires_base_url(
        self, mock_get_configuration_value, mock_log_exception
    ):
        mock_get_configuration_value.return_value = (
            "",
            "",
            "openai_compatible",
            "llama3.1:8b",
            "",
        )

        llm_config = base.get_llm_config()

        assert llm_config.error == "LLM_BASE_URL is required for openai_compatible provider"
        assert llm_config.api_key is None
        mock_log_exception.assert_called_once()

    @patch("plane.app.views.external.base.log_exception")
    @patch("plane.app.views.external.base.get_configuration_value")
    def test_openai_compatible_requires_model(
        self, mock_get_configuration_value, mock_log_exception
    ):
        mock_get_configuration_value.return_value = (
            "",
            "",
            "openai_compatible",
            "",
            "http://localhost:11434/v1",
        )

        llm_config = base.get_llm_config()

        assert llm_config.error == "LLM_MODEL is required for openai_compatible provider"
        assert llm_config.api_key is None
        mock_log_exception.assert_called_once()

    @patch("plane.app.views.external.base.OpenAI")
    def test_openai_compatible_response_uses_base_url(self, mock_openai):
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Generated text"))]
        )
        mock_openai.return_value = mock_client

        text, error = base.get_llm_response(
            "Summarize",
            "The prompt",
            base.OPENAI_COMPATIBLE_PLACEHOLDER_API_KEY,
            "local-model",
            "openai_compatible",
            "http://localhost:11434/v1",
        )

        assert text == "Generated text"
        assert error is None
        mock_openai.assert_called_once_with(
            api_key=base.OPENAI_COMPATIBLE_PLACEHOLDER_API_KEY,
            base_url="http://localhost:11434/v1",
        )
        mock_client.chat.completions.create.assert_called_once_with(
            model="local-model",
            messages=[{"role": "user", "content": "Summarize\nThe prompt"}],
        )
