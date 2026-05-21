import { MODEL_CATALOG } from "./catalog";

// Mirrors callimachus/providers.py::PROVIDERS.bare_prefixes. Kept
// hand-synced because the frontend has no build-time codegen step for
// backend constants. If you add a provider there, mirror its stems here.
const BARE_PREFIXES: ReadonlyArray<[string, string]> = [
  ["claude", "anthropic"],
  ["gpt", "openai"],
  ["o1", "openai"],
  ["o3", "openai"],
  ["gemini", "gemini"],
  ["mistral", "mistral"],
  ["command", "cohere"],
  ["llama", "together_ai"],
];

/**
 * Resolve a model-id input to its LiteLLM provider id, matching the
 * backend's `normalise_model_id`. Returns null when nothing matches so
 * the UI can hide the provider-key badge rather than mislabel it.
 *
 * Resolution order:
 *   1. exact catalog hit (handles odd ids like
 *      `together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo`)
 *   2. explicit `provider/model` prefix
 *   3. bare-name stem (e.g. typing `gpt-4o` maps to openai)
 *   4. unknown → null
 */
export function inferProviderId(value: string): string | null {
  const v = value.trim();
  if (!v) return null;
  const exact = MODEL_CATALOG.find((m) => m.id === v);
  if (exact) return exact.provider;
  if (v.includes("/")) return v.split("/", 1)[0];
  const lower = v.toLowerCase();
  for (const [stem, provider] of BARE_PREFIXES) {
    if (lower.startsWith(stem)) return provider;
  }
  return null;
}
