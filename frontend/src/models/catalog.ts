// Curated list of LiteLLM model ids the picker suggests. Free-form
// entry is still allowed — anything LiteLLM understands will work,
// this list just spares users from typing common ones.
//
// Group by provider for the Autocomplete dropdown.

export interface CatalogEntry {
  id: string;        // LiteLLM model id (provider/model)
  label: string;     // friendly name shown in the dropdown
  provider: string;  // matches ProviderStatus.id from /settings
  notes?: string;
}

export const MODEL_CATALOG: CatalogEntry[] = [
  // Anthropic
  { id: "anthropic/claude-opus-4-7",            label: "Claude Opus 4.7",     provider: "anthropic", notes: "most capable; highest cost" },
  { id: "anthropic/claude-sonnet-4-6",          label: "Claude Sonnet 4.6",   provider: "anthropic", notes: "balanced default for ask" },
  { id: "anthropic/claude-haiku-4-5-20251001",  label: "Claude Haiku 4.5",    provider: "anthropic", notes: "fast/cheap default for extractor" },

  // OpenAI
  { id: "openai/gpt-4o",                        label: "GPT-4o",              provider: "openai" },
  { id: "openai/gpt-4o-mini",                   label: "GPT-4o mini",         provider: "openai", notes: "cheap; good for extractor" },
  { id: "openai/o3-mini",                       label: "o3-mini",             provider: "openai", notes: "reasoning model" },

  // Google
  { id: "gemini/gemini-2.5-pro",                label: "Gemini 2.5 Pro",      provider: "gemini" },
  { id: "gemini/gemini-2.5-flash",              label: "Gemini 2.5 Flash",    provider: "gemini", notes: "cheap; good for extractor" },

  // Mistral
  { id: "mistral/mistral-large-latest",         label: "Mistral Large",       provider: "mistral" },

  // Cohere
  { id: "cohere/command-r-plus",                label: "Command R+",          provider: "cohere" },

  // Together AI (Llama and friends)
  { id: "together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo", label: "Llama 3.3 70B (Together)", provider: "together_ai" },
];
