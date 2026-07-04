/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TInstanceAIProvider = "openai" | "openai_compatible" | "anthropic" | "gemini";

export type TInstanceAIConfigurationKeys =
  | "LLM_API_KEY"
  | "LLM_BASE_URL"
  | "LLM_MODEL"
  | "LLM_OPENAI_COMPATIBLE_API_KEY"
  | "LLM_PROVIDER";
