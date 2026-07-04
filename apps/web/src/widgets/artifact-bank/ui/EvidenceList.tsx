import { FileText, Table2 } from "lucide-react";

import type { EvidenceSpan } from "@/shared/api";
import { Panel } from "@/shared/ui";

type EvidenceListProps = {
  evidence: EvidenceSpan[];
  citationIndex?: Map<string, number>;
  highlightedSpanId?: string | null;
  sourceColorMap?: Map<string, string>;
};

function locatorText(locator: Record<string, unknown> | undefined): string | null {
  if (!locator) return null;
  const parts: string[] = [];
  const sheet = locator.sheet ?? locator.sheet_name;
  const row = locator.row ?? locator.row_index;
  const table = locator.table ?? locator.table_index;
  const block = locator.block ?? locator.block_index;
  if (sheet != null) parts.push(`лист ${String(sheet)}`);
  if (table != null) parts.push(`таблица ${String(table)}`);
  if (row != null) parts.push(`строка ${String(row)}`);
  if (block != null && parts.length === 0) parts.push(`блок ${String(block)}`);
  return parts.length > 0 ? parts.join(" · ") : null;
}

export function EvidenceList({
  evidence,
  citationIndex,
  highlightedSpanId,
  sourceColorMap,
}: EvidenceListProps) {
  return (
    <Panel title="Evidence cards">
      <div className="evidence-list">
        {evidence.map((span) => {
          const number = citationIndex?.get(span.span_id);
          const locator = locatorText(span.locator);
          const sourceColor = sourceColorMap?.get(span.source_id);
          return (
            <article
              className={
                "evidence-card" + (highlightedSpanId === span.span_id ? " evidence-card-active" : "")
              }
              id={`evidence-${span.span_id}`}
              key={span.span_id}
              style={sourceColor ? { borderColor: sourceColor } : undefined}
            >
              <div className="evidence-meta">
                <span>
                  {number != null ? (
                    <span
                      className="citation-badge"
                      style={sourceColor ? { background: sourceColor } : undefined}
                    >
                      {number}
                    </span>
                  ) : null}
                  {span.span_type === "table_row" ? <Table2 size={14} /> : <FileText size={14} />}{" "}
                  {span.span_id}
                </span>
                <span>
                  page {span.page ?? "-"}
                  {locator ? ` · ${locator}` : ""} · {span.validation_status}
                </span>
              </div>
              <p className="evidence-text">{span.visible_text}</p>
            </article>
          );
        })}
      </div>
    </Panel>
  );
}
