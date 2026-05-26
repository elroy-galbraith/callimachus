import { GraphvizSvg } from "./GraphvizSvg";

export function ProposalMiniGraph({ dot }: { dot: string }) {
  return <GraphvizSvg dot={dot} />;
}
