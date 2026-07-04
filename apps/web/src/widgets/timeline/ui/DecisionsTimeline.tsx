import { CalendarClock } from "lucide-react";
import { useEffect, useState } from "react";

import { fetchTimeline, type TimelineEvent } from "@/shared/api";
import { Panel } from "@/shared/ui";

export function DecisionsTimeline() {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        setEvents(await fetchTimeline());
      } catch {
        // Timeline data is additive; keep the page usable when it is unavailable.
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  if (!loaded) {
    return (
      <Panel title="История решений">
        <div className="status-pill">Загрузка…</div>
      </Panel>
    );
  }
  if (events.length === 0) {
    return (
      <Panel title="История решений">
        <div className="status-pill">
          Датированные решения появятся после загрузки документов с выводами.
        </div>
      </Panel>
    );
  }
  return (
    <Panel title="История решений">
      <div className="timeline-list">
        {events.map((event) => (
          <article className="timeline-item" key={event.entity_id}>
            <div className="timeline-icon">
              <CalendarClock size={15} />
            </div>
            <div>
              <div className="timeline-date">
                {event.date ?? (event.year ? String(event.year) : "без даты")}
              </div>
              <div className="timeline-title">{event.title}</div>
              <div className="source-meta">
                {event.entity_type} · {event.evidence_span_ids.length} evidence
              </div>
            </div>
          </article>
        ))}
      </div>
    </Panel>
  );
}
