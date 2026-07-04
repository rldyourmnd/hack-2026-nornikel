import { ShieldCheck } from "lucide-react";

import type { AskResponse } from "@/shared/api";
import { Panel } from "@/shared/ui";

type EvaluationDashboardProps = {
  answer: AskResponse;
};

export function EvaluationDashboard({ answer }: EvaluationDashboardProps) {
  const metrics = [
    ["Citation coverage", `${Math.round(answer.verification.citation_coverage * 100)}%`],
    ["Unsupported claims", String(answer.verification.unsupported_claim_count)],
    ["Source-label leaks", String(answer.verification.source_label_leak_count)],
    ["Numeric mismatches", String(answer.verification.numeric_mismatch_count)],
    ["Semantic unsupported", String(answer.verification.semantic_unsupported_count)],
  ];

  return (
    <Panel title="Evaluation / security">
      <div className="status-pill">
        <ShieldCheck size={16} />
        Prompt-injection fixture baseline: {answer.verification.prompt_injection_success_count}
      </div>
      <div className="metrics-grid" style={{ marginTop: 12 }}>
        {metrics.map(([label, value]) => (
          <div className="metric" key={label}>
            <div className="metric-value">{value}</div>
            <div className="metric-label">{label}</div>
          </div>
        ))}
      </div>
    </Panel>
  );
}
