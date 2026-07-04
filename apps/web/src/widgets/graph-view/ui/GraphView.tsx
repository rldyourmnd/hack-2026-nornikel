import { Atom, Beaker, FileText, GitBranch, TestTube2, type LucideIcon } from "lucide-react";

import type { GraphPath } from "@/shared/api";
import { Panel } from "@/shared/ui";

const nodeKinds = [
  "Material",
  "Experiment",
  "Regime",
  "Step",
  "Measurement",
  "Property",
  "Evidence",
  "Document",
];

type GraphViewProps = {
  graphPaths: GraphPath[];
};

export function GraphView({ graphPaths }: GraphViewProps) {
  const path = graphPaths[0];

  if (!path) {
    return (
      <Panel title="Графовый путь">
        <div className="status-pill">Для ответа не был построен графовый путь.</div>
      </Panel>
    );
  }

  return (
    <Panel title="Графовый путь">
      <div className="graph-canvas">
        {path.nodes.map((node, index) => {
          const Icon: LucideIcon =
            index === 1
              ? TestTube2
              : index === 0
                ? Atom
                : index === 6
                  ? FileText
                  : index === 2
                    ? Beaker
                    : GitBranch;
          return (
            <div className="graph-node" key={node}>
              <div className="graph-icon">
                <Icon size={17} />
              </div>
              <div>
                <div className="graph-label">{node}</div>
                <div className="graph-kind">
                  {nodeKinds[index] ?? "Node"} {path.relationships[index] ? `→ ${path.relationships[index]}` : ""}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}
