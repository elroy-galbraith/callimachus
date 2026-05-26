import { Badge, Group, Select, Stack, Text } from "@mantine/core";

import { MODEL_CATALOG } from "../models/catalog";
import { inferProviderId } from "../models/inferProvider";
import type { ProviderStatus } from "../api/types";

interface Props {
  label: string;
  description?: string;
  value: string;
  onChange: (next: string) => void;
  providers?: ProviderStatus[];
  disabled?: boolean;
  placeholder?: string;
  clearable?: boolean;
}

// Ordered list of provider groups — Gemini first per UX preference.
const GROUP_ORDER: { provider: string; label: string }[] = [
  { provider: "gemini",     label: "Google – Gemini" },
  { provider: "anthropic",  label: "Anthropic" },
  { provider: "openai",     label: "OpenAI" },
  { provider: "mistral",    label: "Mistral" },
  { provider: "cohere",     label: "Cohere" },
  { provider: "together_ai", label: "Together AI" },
];

function buildSelectData() {
  const byProvider: Record<string, { value: string; label: string }[]> = {};
  for (const m of MODEL_CATALOG) {
    if (!byProvider[m.provider]) byProvider[m.provider] = [];
    byProvider[m.provider].push({
      value: m.id,
      label: m.notes ? `${m.label}  —  ${m.notes}` : m.label,
    });
  }
  return GROUP_ORDER
    .filter(({ provider }) => byProvider[provider])
    .map(({ provider, label }) => ({ group: label, items: byProvider[provider] }));
}

const SELECT_DATA = buildSelectData();

/**
 * Dropdown (searchable Select) of curated LiteLLM model ids, grouped by
 * provider with Gemini at the top. Accepts an empty string for "unset".
 *
 * When `providers` is supplied, shows a badge indicating whether the
 * selected model's provider API key is configured.
 */
export function ModelPicker({
  label,
  description,
  value,
  onChange,
  providers,
  disabled,
  placeholder = "Select a model…",
  clearable = false,
}: Props) {
  const providerId = inferProviderId(value);
  const providerStatus = providerId
    ? providers?.find((p) => p.id === providerId)
    : undefined;

  return (
    <Stack gap={4}>
      <Select
        label={label}
        description={description}
        data={SELECT_DATA}
        value={value || null}
        onChange={(v) => onChange(v ?? "")}
        placeholder={placeholder}
        disabled={disabled}
        searchable
        clearable={clearable}
        comboboxProps={{ shadow: "md" }}
      />
      {providerStatus && (
        <Group gap="xs" mt={2}>
          <Badge
            size="sm"
            variant="light"
            color={providerStatus.configured ? "green" : "red"}
          >
            {providerStatus.configured
              ? `${providerStatus.label} key set`
              : `${providerStatus.label} key missing`}
          </Badge>
          {!providerStatus.configured && (
            <Text size="xs" c="dimmed">
              Set <code>{providerStatus.env_var}</code> in <code>.env</code> and
              restart the API.
            </Text>
          )}
        </Group>
      )}
    </Stack>
  );
}
