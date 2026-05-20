import { Alert, Code } from "@mantine/core";
import { IconKey } from "@tabler/icons-react";

import { useSettings } from "../api/hooks";

/**
 * Inline warning when ``ANTHROPIC_API_KEY`` isn't present in the API
 * process. Mirrors the Streamlit version's ``api_key_warning`` helper —
 * but we never let the user write the key over HTTP (see plan §10).
 */
export function ApiKeyBanner() {
  const { data, isPending } = useSettings();
  if (isPending || !data || data.api_key_set) return null;
  return (
    <Alert
      icon={<IconKey size={16} />}
      color="yellow"
      title="ANTHROPIC_API_KEY is not set"
      mb="md"
    >
      Set it in <Code>.env</Code> at the repo root and restart the API
      server. LLM calls (extraction, NL ask, consolidation) will fail
      until then.
    </Alert>
  );
}
