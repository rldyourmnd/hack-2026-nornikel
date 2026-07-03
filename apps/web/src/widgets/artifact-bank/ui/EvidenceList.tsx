import { FileText, Table2 } from "lucide-react";

import type { EvidenceSpan } from "@/shared/api";
import { Panel } from "@/shared/ui";

type EvidenceListProps = {
  evidence: EvidenceSpan[];
};

export function EvidenceList({ evidence }: EvidenceListProps) {
  return (
    <Panel title="Evidence cards">
      <div className="evidence-list">
        {evidence.map((span) => (
          <article className="evidence-card" key={span.span_id}>
            <div className="evidence-meta">
              <span>
                {span.span_type === "table_row" ? <Table2 size={14} /> : <FileText size={14} />}{" "}
                {span.span_id}
              </span>
              <span>
                page {span.page ?? "-"} · {span.validation_status}
              </span>
            </div>
            <p className="evidence-text">{span.visible_text}</p>
          </article>
        ))}
      </div>
    </Panel>
  );
}
