# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.license.api.views.instance import has_llm_configured


@pytest.mark.unit
class TestInstanceLLMConfig:
    def test_openai_requires_api_key_for_instance_flag(self):
        assert has_llm_configured("sk-test", "openai", "gpt-4o-mini", "") is True
        assert has_llm_configured("", "openai", "gpt-4o-mini", "") is False
        assert has_llm_configured("sk-test", "", "", "") is True

    def test_openai_compatible_can_be_configured_without_api_key(self):
        assert has_llm_configured("", "openai_compatible", "llama3.1:8b", "http://ollama:11434/v1") is True

    def test_openai_compatible_ignores_api_key_when_base_url_is_missing(self):
        assert has_llm_configured("sk-test", "openai_compatible", "llama3.1:8b", "") is False

    def test_openai_compatible_requires_model_and_base_url_for_instance_flag(self):
        assert has_llm_configured("", "openai_compatible", "", "http://ollama:11434/v1") is False
        assert has_llm_configured("", "openai_compatible", "llama3.1:8b", "") is False

    @pytest.mark.parametrize("provider", ["anthropic", "gemini", "unknown"])
    def test_unsupported_provider_is_not_configured(self, provider):
        assert has_llm_configured("sk-test", provider, "gpt-4o-mini", "http://example.test/v1") is False
