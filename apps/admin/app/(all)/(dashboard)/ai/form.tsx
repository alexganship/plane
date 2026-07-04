/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Controller, useForm } from "react-hook-form";
import { Lightbulb } from "lucide-react";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { IFormattedInstanceConfiguration, TInstanceAIConfigurationKeys, TInstanceAIProvider } from "@plane/types";
import { CustomSelect } from "@plane/ui";
// components
import type { TControllerInputFormField } from "@/components/common/controller-input";
import { ControllerInput } from "@/components/common/controller-input";
// hooks
import { useInstance } from "@/hooks/store";

type IInstanceAIForm = {
  config: IFormattedInstanceConfiguration;
};

type AIFormValues = Record<TInstanceAIConfigurationKeys, string>;

const LLM_PROVIDER_OPTIONS: Record<TInstanceAIProvider, string> = {
  openai: "OpenAI",
  openai_compatible: "OpenAI Compatible",
  anthropic: "Anthropic",
  gemini: "Gemini",
};

const LLM_MODEL_EXAMPLES: Record<TInstanceAIProvider, string> = {
  anthropic: "claude-3-sonnet-20240229",
  gemini: "gemini-pro",
  openai: "gpt-4o-mini",
  openai_compatible: "llama3.1",
};

const LLM_MODEL_HELPER_TEXT: Record<TInstanceAIProvider, string> = {
  anthropic: "claude-3-sonnet-20240229, claude-3-haiku-20240307, or claude-2.",
  gemini: "gemini-pro, gemini-1.5-pro-latest, or gemini-pro-vision.",
  openai: "gpt-4o-mini.",
  openai_compatible: "llama3.1, qwen2.5-coder, or mistral.",
};

export function InstanceAIForm(props: IInstanceAIForm) {
  const { config } = props;
  // store
  const { updateInstanceConfigurations } = useInstance();
  // form data
  const {
    handleSubmit,
    watch,
    control,
    formState: { errors, isSubmitting },
  } = useForm<AIFormValues>({
    defaultValues: {
      LLM_API_KEY: config["LLM_API_KEY"],
      LLM_BASE_URL: config["LLM_BASE_URL"],
      LLM_MODEL: config["LLM_MODEL"],
      LLM_OPENAI_COMPATIBLE_API_KEY: config["LLM_OPENAI_COMPATIBLE_API_KEY"],
      LLM_PROVIDER: config["LLM_PROVIDER"] || "openai",
    },
  });

  const llmProvider = watch("LLM_PROVIDER");
  const isOpenAICompatible = llmProvider === "openai_compatible";
  const selectedProvider = Object.prototype.hasOwnProperty.call(LLM_PROVIDER_OPTIONS, llmProvider)
    ? (llmProvider as TInstanceAIProvider)
    : undefined;
  const apiKeyFieldKey = isOpenAICompatible ? "LLM_OPENAI_COMPATIBLE_API_KEY" : "LLM_API_KEY";
  const providerLabel = selectedProvider ? LLM_PROVIDER_OPTIONS[selectedProvider] : "Unknown provider";
  const modelExample = selectedProvider ? LLM_MODEL_EXAMPLES[selectedProvider] : "model-name";
  const modelHelperText = selectedProvider ? LLM_MODEL_HELPER_TEXT[selectedProvider] : "a supported model name.";
  const apiKeyPlaceholder =
    selectedProvider === "anthropic" ? "sk-ant-..." : selectedProvider === "gemini" ? "AIza..." : "sk-...";

  const aiFormFields: TControllerInputFormField[] = [
    {
      key: "LLM_MODEL",
      type: "text",
      label: "LLM Model",
      description: (
        <>
          Use a provider model name, for example {modelHelperText}{" "}
          <a
            href="https://platform.openai.com/docs/models/overview"
            target="_blank"
            className="text-accent-primary hover:underline"
            rel="noreferrer"
          >
            Learn more
          </a>
        </>
      ),
      placeholder: modelExample,
      error: Boolean(errors.LLM_MODEL),
      required: false,
    },
    ...(isOpenAICompatible
      ? [
          {
            key: "LLM_BASE_URL",
            type: "text",
            label: "Base URL",
            description:
              "OpenAI-compatible API endpoint, for example http://ollama:11434/v1, http://vllm:8000/v1, or http://litellm:4000/v1.",
            placeholder: "http://ollama:11434/v1",
            error: Boolean(errors.LLM_BASE_URL),
            required: false,
          } satisfies TControllerInputFormField,
        ]
      : []),
    {
      key: apiKeyFieldKey,
      type: "password",
      label: isOpenAICompatible ? "Compatible API key" : "API key",
      description: (
        <>
          {isOpenAICompatible ? (
            "Optional. Required only if your OpenAI-compatible gateway requires authentication."
          ) : selectedProvider === "anthropic" ? (
            "Use your Anthropic API key."
          ) : selectedProvider === "gemini" ? (
            "Use your Gemini API key."
          ) : (
            <>
              You will find your API key{" "}
              <a
                href="https://platform.openai.com/api-keys"
                target="_blank"
                className="text-accent-primary hover:underline"
                rel="noreferrer"
              >
                here.
              </a>
            </>
          )}
        </>
      ),
      placeholder: apiKeyPlaceholder,
      error: Boolean(errors[apiKeyFieldKey]),
      required: false,
    },
  ];

  const onSubmit = async (formData: AIFormValues) => {
    const payload: Partial<AIFormValues> = { ...formData };

    await updateInstanceConfigurations(payload)
      .then(() =>
        setToast({
          type: TOAST_TYPE.SUCCESS,
          title: "Success",
          message: "AI Settings updated successfully",
        })
      )
      .catch((err) => console.error(err));
  };

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <div>
          <div className="pb-1 text-18 font-medium text-primary">AI provider</div>
          <div className="text-13 font-regular text-tertiary">Configure the LLM provider for Plane AI features.</div>
        </div>
        <div className="grid-col grid w-full grid-cols-1 items-center justify-between gap-x-12 gap-y-8 lg:grid-cols-3">
          <div className="flex flex-col gap-1">
            <h4 className="text-13 text-tertiary">Provider</h4>
            <Controller
              control={control}
              name="LLM_PROVIDER"
              render={({ field: { value: providerValue, onChange } }) => (
                <CustomSelect
                  value={providerValue}
                  label={providerLabel}
                  onChange={onChange}
                  buttonClassName="rounded-md border-subtle"
                  input
                >
                  {Object.entries(LLM_PROVIDER_OPTIONS).map(([key, label]) => (
                    <CustomSelect.Option key={key} value={key} className="w-full">
                      {label}
                    </CustomSelect.Option>
                  ))}
                </CustomSelect>
              )}
            />
            <p className="pt-0.5 text-11 text-tertiary">
              Choose OpenAI, Anthropic, Gemini, or an OpenAI-compatible server such as Ollama, vLLM, or LiteLLM.
            </p>
          </div>
          {aiFormFields.map((field) => (
            <ControllerInput
              key={field.key}
              control={control}
              type={field.type}
              name={field.key}
              label={field.label}
              description={field.description}
              placeholder={field.placeholder}
              error={field.error}
              required={field.required}
            />
          ))}
        </div>
      </div>

      <div className="flex flex-col items-start gap-4">
        <Button variant="primary" size="lg" onClick={handleSubmit(onSubmit)} loading={isSubmitting}>
          {isSubmitting ? "Saving" : "Save changes"}
        </Button>

        <div className="relative inline-flex items-center gap-1.5 rounded-sm border border-accent-subtle bg-accent-subtle px-4 py-2 text-caption-sm-regular text-accent-secondary">
          <Lightbulb className="size-4" />
          <div>
            Use OpenAI-compatible endpoints for self-hosted LLM servers. For custom AI provider needs, please get in{" "}
            <a className="font-medium underline" href="https://plane.so/contact">
              touch with us.
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
