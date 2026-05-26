import { useEffect, useRef, useState } from "react";
import { Alert, Loader, Text } from "@mantine/core";

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

/**
 * Render a DOT string as an inline SVG via @viz-js/viz (Graphviz WASM).
 *
 * When ``onNodeClick`` is provided, each ``<g class="node">`` in the SVG
 * gets a click listener. The listener reads the ``<title>`` child (which
 * Graphviz sets to the DOT node ID) and calls
 * ``onNodeClick(decodeURIComponent(title))``.
 */
export function GraphvizSvg({
  dot,
  onNodeClick,
}: {
  dot: string;
  onNodeClick?: (nodeId: string) => void;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const onNodeClickRef = useRef(onNodeClick);
  useEffect(() => {
    onNodeClickRef.current = onNodeClick;
  }, [onNodeClick]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getViz()
      .then((viz) => {
        if (cancelled) return;
        try {
          const svg = viz.renderSVGElement(dot);
          svg.removeAttribute("width");
          svg.removeAttribute("height");
          svg.setAttribute("style", "max-width:100%; height:auto;");
          if (onNodeClickRef.current) {
            svg.querySelectorAll("g.node").forEach((g) => {
              const title = g.querySelector("title")?.textContent;
              if (!title) return;
              (g as SVGGElement).style.cursor = "pointer";
              g.addEventListener("click", (e) => {
                e.stopPropagation();
                onNodeClickRef.current?.(decodeURIComponent(title));
              });
            });
          }
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
      style={{
        minHeight: 60,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {loading && <Loader size="xs" />}
      <div
        ref={hostRef}
        style={{
          width: "100%",
          display: loading ? "none" : "flex",
          justifyContent: "center",
        }}
      />
    </div>
  );
}
