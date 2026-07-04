/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { isEmpty } from "lodash-es";
import Link from "next/link";
import { useForm } from "react-hook-form";
// plane internal packages
import { API_BASE_URL } from "@plane/constants";
import { Button, getButtonStyling } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { IFormattedInstanceConfiguration, TInstanceOidcAuthenticationConfigurationKeys } from "@plane/types";
// components
import { CodeBlock } from "@/components/common/code-block";
import { ConfirmDiscardModal } from "@/components/common/confirm-discard-modal";
import { ControllerInput, type TControllerInputFormField } from "@/components/common/controller-input";
import { ControllerSwitch, type TControllerSwitchFormField } from "@/components/common/controller-switch";
import { CopyField, type TCopyField } from "@/components/common/copy-field";
// hooks
import { useInstance } from "@/hooks/store";

type Props = {
  config: IFormattedInstanceConfiguration;
};

type OidcConfigFormValues = Record<TInstanceOidcAuthenticationConfigurationKeys, string>;

export function InstanceOidcConfigForm(props: Props) {
  const { config } = props;
  // states
  const [isDiscardChangesModalOpen, setIsDiscardChangesModalOpen] = useState(false);
  // store hooks
  const { updateInstanceConfigurations } = useInstance();
  // form data
  const {
    handleSubmit,
    control,
    reset,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<OidcConfigFormValues>({
    defaultValues: {
      OIDC_DISCOVERY_URL: config["OIDC_DISCOVERY_URL"],
      OIDC_ISSUER_URL: config["OIDC_ISSUER_URL"] || "",
      OIDC_CLIENT_ID: config["OIDC_CLIENT_ID"],
      OIDC_CLIENT_SECRET: config["OIDC_CLIENT_SECRET"],
      OIDC_SCOPE: config["OIDC_SCOPE"] || "openid email profile",
      OIDC_CLIENT_AUTH_METHOD: config["OIDC_CLIENT_AUTH_METHOD"] || "client_secret_post",
      OIDC_ALLOWED_EMAIL_DOMAINS: config["OIDC_ALLOWED_EMAIL_DOMAINS"] || "",
      OIDC_REQUIRE_EMAIL_VERIFIED: config["OIDC_REQUIRE_EMAIL_VERIFIED"] || "0",
      OIDC_ALLOWED_GROUPS: config["OIDC_ALLOWED_GROUPS"] || "",
      OIDC_GROUPS_CLAIM: config["OIDC_GROUPS_CLAIM"] || "groups",
      OIDC_ALLOWED_ROLES: config["OIDC_ALLOWED_ROLES"] || "",
      OIDC_ROLES_CLAIM: config["OIDC_ROLES_CLAIM"] || "realm_access.roles",
      ENABLE_OIDC_SYNC: config["ENABLE_OIDC_SYNC"] || "0",
    },
  });

  const originURL = !isEmpty(API_BASE_URL) ? API_BASE_URL : typeof window !== "undefined" ? window.location.origin : "";

  const OIDC_FORM_FIELDS: TControllerInputFormField[] = [
    {
      key: "OIDC_DISCOVERY_URL",
      type: "text",
      label: "Discovery URL",
      description: (
        <>
          For Authentik, use <CodeBlock>/application/o/plane/.well-known/openid-configuration</CodeBlock>. For Keycloak,
          use <CodeBlock>/realms/company/.well-known/openid-configuration</CodeBlock>.
        </>
      ),
      placeholder: "https://auth.example.com/application/o/plane/.well-known/openid-configuration",
      error: Boolean(errors.OIDC_DISCOVERY_URL),
      required: true,
    },
    {
      key: "OIDC_ISSUER_URL",
      type: "text",
      label: "Issuer URL override",
      description: <>Leave empty to use the issuer from the discovery document.</>,
      placeholder: "https://auth.example.com/application/o/plane/",
      error: Boolean(errors.OIDC_ISSUER_URL),
      required: false,
    },
    {
      key: "OIDC_CLIENT_ID",
      type: "text",
      label: "Client ID",
      description: <>The client ID from your Authentik or Keycloak OIDC application.</>,
      placeholder: "plane",
      error: Boolean(errors.OIDC_CLIENT_ID),
      required: true,
    },
    {
      key: "OIDC_CLIENT_SECRET",
      type: "password",
      label: "Client secret",
      description: <>The client secret from your OIDC application.</>,
      placeholder: "client-secret",
      error: Boolean(errors.OIDC_CLIENT_SECRET),
      required: true,
    },
    {
      key: "OIDC_SCOPE",
      type: "text",
      label: "Scopes",
      description: (
        <>
          Use <CodeBlock>openid email profile</CodeBlock> for Authentik and Keycloak. Add
          <CodeBlock>offline_access</CodeBlock> only if refresh tokens are required.
        </>
      ),
      placeholder: "openid email profile",
      error: Boolean(errors.OIDC_SCOPE),
      required: true,
    },
    {
      key: "OIDC_CLIENT_AUTH_METHOD",
      type: "text",
      label: "Token auth method",
      description: (
        <>
          Use <CodeBlock>client_secret_post</CodeBlock> or <CodeBlock>client_secret_basic</CodeBlock>.
        </>
      ),
      placeholder: "client_secret_post",
      error: Boolean(errors.OIDC_CLIENT_AUTH_METHOD),
      required: true,
    },
    {
      key: "OIDC_ALLOWED_EMAIL_DOMAINS",
      type: "text",
      label: "Allowed email domains",
      description: <>Optional comma-separated domains allowed to sign in.</>,
      placeholder: "example.com, company.com",
      error: Boolean(errors.OIDC_ALLOWED_EMAIL_DOMAINS),
      required: false,
    },
    {
      key: "OIDC_ALLOWED_GROUPS",
      type: "text",
      label: "Allowed groups",
      description: <>Optional comma-separated groups. Authentik commonly works with the default claim below.</>,
      placeholder: "plane-users, plane-admins",
      error: Boolean(errors.OIDC_ALLOWED_GROUPS),
      required: false,
    },
    {
      key: "OIDC_GROUPS_CLAIM",
      type: "text",
      label: "Groups claim",
      description: (
        <>
          Authentik default: <CodeBlock>groups</CodeBlock>.
        </>
      ),
      placeholder: "groups",
      error: Boolean(errors.OIDC_GROUPS_CLAIM),
      required: true,
    },
    {
      key: "OIDC_ALLOWED_ROLES",
      type: "text",
      label: "Allowed roles",
      description: <>Optional comma-separated roles. Useful for Keycloak realm or client roles.</>,
      placeholder: "plane-user, plane-admin",
      error: Boolean(errors.OIDC_ALLOWED_ROLES),
      required: false,
    },
    {
      key: "OIDC_ROLES_CLAIM",
      type: "text",
      label: "Roles claim",
      description: (
        <>
          Keycloak examples: <CodeBlock>realm_access.roles</CodeBlock> or
          <CodeBlock>resource_access.plane.roles</CodeBlock>.
        </>
      ),
      placeholder: "realm_access.roles",
      error: Boolean(errors.OIDC_ROLES_CLAIM),
      required: true,
    },
  ];

  const OIDC_FORM_SWITCH_FIELDS: TControllerSwitchFormField<OidcConfigFormValues>[] = [
    {
      name: "OIDC_REQUIRE_EMAIL_VERIFIED",
      label: "Require verified email",
    },
    {
      name: "ENABLE_OIDC_SYNC",
      label: "Sync profile data on login",
    },
  ];

  const OIDC_SERVICE_FIELD: TCopyField[] = [
    {
      key: "App_Callback_URL",
      label: "App callback URL",
      url: `${originURL}/auth/oidc/callback/`,
      description: <>Paste this into your OIDC provider redirect URI list for the main app.</>,
    },
    {
      key: "Space_Callback_URL",
      label: "Space callback URL",
      url: `${originURL}/auth/spaces/oidc/callback/`,
      description: <>Paste this into your OIDC provider redirect URI list for Plane Space.</>,
    },
  ];

  const onSubmit = async (formData: OidcConfigFormValues) => {
    const payload: Partial<OidcConfigFormValues> = { ...formData };

    try {
      const response = await updateInstanceConfigurations(payload);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Done!",
        message: "Your OIDC authentication is configured. You should test it now.",
      });
      reset({
        OIDC_DISCOVERY_URL: response.find((item) => item.key === "OIDC_DISCOVERY_URL")?.value,
        OIDC_ISSUER_URL: response.find((item) => item.key === "OIDC_ISSUER_URL")?.value,
        OIDC_CLIENT_ID: response.find((item) => item.key === "OIDC_CLIENT_ID")?.value,
        OIDC_CLIENT_SECRET: response.find((item) => item.key === "OIDC_CLIENT_SECRET")?.value,
        OIDC_SCOPE: response.find((item) => item.key === "OIDC_SCOPE")?.value,
        OIDC_CLIENT_AUTH_METHOD: response.find((item) => item.key === "OIDC_CLIENT_AUTH_METHOD")?.value,
        OIDC_ALLOWED_EMAIL_DOMAINS: response.find((item) => item.key === "OIDC_ALLOWED_EMAIL_DOMAINS")?.value,
        OIDC_REQUIRE_EMAIL_VERIFIED: response.find((item) => item.key === "OIDC_REQUIRE_EMAIL_VERIFIED")?.value,
        OIDC_ALLOWED_GROUPS: response.find((item) => item.key === "OIDC_ALLOWED_GROUPS")?.value,
        OIDC_GROUPS_CLAIM: response.find((item) => item.key === "OIDC_GROUPS_CLAIM")?.value,
        OIDC_ALLOWED_ROLES: response.find((item) => item.key === "OIDC_ALLOWED_ROLES")?.value,
        OIDC_ROLES_CLAIM: response.find((item) => item.key === "OIDC_ROLES_CLAIM")?.value,
        ENABLE_OIDC_SYNC: response.find((item) => item.key === "ENABLE_OIDC_SYNC")?.value,
      });
    } catch (err) {
      console.error(err);
    }
  };

  const handleGoBack = (e: React.MouseEvent<HTMLAnchorElement, MouseEvent>) => {
    if (isDirty) {
      e.preventDefault();
      setIsDiscardChangesModalOpen(true);
    }
  };

  return (
    <>
      <ConfirmDiscardModal
        isOpen={isDiscardChangesModalOpen}
        onDiscardHref="/authentication"
        handleClose={() => setIsDiscardChangesModalOpen(false)}
      />
      <div className="flex flex-col gap-8">
        <div className="grid w-full grid-cols-2 gap-x-12 gap-y-8">
          <div className="col-span-2 flex flex-col gap-y-4 pt-1 md:col-span-1">
            <div className="pt-2.5 text-18 font-medium">OIDC provider details for Plane</div>
            {OIDC_FORM_FIELDS.map((field) => (
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
            {OIDC_FORM_SWITCH_FIELDS.map((field) => (
              <ControllerSwitch key={field.name} control={control} field={field} />
            ))}
            <div className="flex flex-col gap-1 pt-4">
              <div className="flex items-center gap-4">
                <Button
                  variant="primary"
                  size="lg"
                  onClick={(e) => void handleSubmit(onSubmit)(e)}
                  loading={isSubmitting}
                  disabled={!isDirty}
                >
                  {isSubmitting ? "Saving" : "Save changes"}
                </Button>
                <Link href="/authentication" className={getButtonStyling("secondary", "lg")} onClick={handleGoBack}>
                  Go back
                </Link>
              </div>
            </div>
          </div>
          <div className="col-span-2 md:col-span-1">
            <div className="flex flex-col gap-y-4 rounded-lg bg-layer-3 px-6 pt-1.5 pb-4">
              <div className="pt-2 text-18 font-medium">Plane-provided details for OIDC</div>
              {OIDC_SERVICE_FIELD.map((field) => (
                <CopyField key={field.key} label={field.label} url={field.url} description={field.description} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
