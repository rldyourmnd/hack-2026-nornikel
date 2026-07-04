import { GapsBoard } from "@/widgets/gaps-board";
import { DecisionsTimeline } from "@/widgets/timeline";

type AnalyticsPageProps = {
  onGapQuery: (question: string) => void;
};

export function AnalyticsPage({ onGapQuery }: AnalyticsPageProps) {
  return (
    <div className="workbench-grid">
      <div className="stack">
        <GapsBoard onGapQuery={onGapQuery} />
      </div>
      <div className="stack">
        <DecisionsTimeline />
      </div>
    </div>
  );
}
