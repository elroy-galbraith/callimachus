import { useEffect, useRef, useState } from "react";
import { Alert, Loader, Text } from "@mantine/core";

/**
 * Render a DOT string as an inline SVG via @viz-js/viz (Graphviz WASM).
 *
 * The WASM binary is loaded lazily once and cached at module scope, so
 * subsequent cards on the same page render synchronously.
 */
type VizModule = {
  renderSVGElement(dot: string): SVGSVGElement;
};

let vizInstance: VizModule | null = null;
let vizPromise: Promise<VizModule> | null = null;

async function getViz(): Promise<VizModule> {
  if (vizInstance) return vizInstance;
  if (!vizPromise) {
    vizPromise = import("@viz-js/viz").then(async (mod) => {
      const v = await mod.instance();
      vizInstance = v as unknown as VizModule;
      return vizInstance;
    });
  }
  return vizPromise;
}

export function ProposalMiniGraph({ dot }: { dot: string }) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getViz()
      .then((viz) => {
        if (cancelled) return;
        try {
          const svg = viz.renderSVGElement(dot);
          // Make the SVG responsive to the container width.
          svg.removeAttribute("width");
          svg.removeAttribute("height");
          svg.setAttribute("style", "max-width:100%; height:auto;");
          if (hostRef.current) {
            hostRef.current.replaceChildren(svg);
          }
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setLoading(false);
        }
      })
      .catch((e) => {
        if (cancelled) return;
        setError((e as Error).message);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [dot]);

  if (error) {
    return (
      <Alert color="yellow" variant="light">
        <Text size="xs">Graph render failed: {error}</Text>
      </Alert>
    );
  }
  return (
    <div
      ref={hostRef}
      style={{
        minHeight: 60,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {loading && <Loader size="xs" />}
    </div>
  );
}
