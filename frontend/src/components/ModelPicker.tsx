import { Autocomplete, Badge, Group, Stack, Text } from "@mantine/core";

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
}

/**
 * Free-form text input with a curated dropdown of known-good LiteLLM
 * model ids. Accepts anything LiteLLM understands — the catalog is just
 * a convenience.
 *
 * When `providers` is supplied, a small badge shows whether the API
 * key for the selected model's provider is configured. The provider is
 * inferred from the `provider/model` prefix.
 */
export function ModelPicker({
  label,
  description,
  value,
  onChange,
  providers,
  disabled,
}: Props) {
  const data = MODEL_CATALOG.map((m) => ({
    value: m.id,
    label: m.notes ? `${m.label}  —  ${m.notes}` : m.label,
  }));

  const providerId = inferProviderId(value);
  const providerStatus = providerId
    ? providers?.find((p) => p.id === providerId)
    : undefined;

  return (
    <Stack gap={4}>
      <Autocomplete
        label={label}
        description={description}
        data={data}
        value={value}
        onChange={onChange}
        placeholder="provider/model, e.g. anthropic/claude-sonnet-4-6"
        disabled={disabled}
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
