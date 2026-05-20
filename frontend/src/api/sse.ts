import type { JobEvent } from "./types";

// SSE base URL: match the REST client so the dev proxy works for both.
const BASE = import.meta.env.VITE_API_BASE ?? "/api";

/**
 * Subscribe to a JobRegistry job over SSE.
 *
 * Returns an ``unsubscribe`` function. ``onEnd`` fires exactly once;
 * after that the EventSource is closed. ``onEvent`` fires for each
 * ``progress`` event the server emits.
 */
export function subscribeJob(
  jobId: string,
  handlers: {
    onEvent?: (e: JobEvent) => void;
    onEnd?: (status: "done" | "error") => void;
    onError?: (err: Event) => void;
  },
): () => void {
  const es = new EventSource(`${BASE}/jobs/${jobId}/events`);
  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    es.close();
  };

  es.addEventListener("progress", (e) => {
    try {
      handlers.onEvent?.(JSON.parse((e as MessageEvent).data) as JobEvent);
    } catch {
      /* ignore malformed event */
    }
  });
  es.addEventListener("end", (e) => {
    let status: "done" | "error" = "done";
    try {
      status = JSON.parse((e as MessageEvent).data).status;
    } catch {
      /* ignore */
    }
    handlers.onEnd?.(status);
    close();
  });
  es.onerror = (err) => {
    handlers.onError?.(err);
    close();
  };

  return close;
}
