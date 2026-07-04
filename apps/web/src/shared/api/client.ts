import type {
  AnswerRunSummary,
  ArchiveUploadResponse,
  AskFilters,
  AskResponse,
  EntitySearchResult,
  EvalSummary,
  GapsAnalysis,
  GraphNeighborhood,
  HealthStatus,
  SourceIngestResponse,
  SourceSummary,
  StatsOverview,
  TimelineEvent,
  TypedEntity,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

type ErrorPayload = {
  detail?: unknown;
};

function formatServerErrorDetail(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }
        if (typeof item === "object" && item !== null) {
          if (
            "loc" in item &&
            typeof item.msg === "string" &&
            Array.isArray(item.loc)
          ) {
            const location = item.loc.join(".");
            return `${location}: ${item.msg}`;
          }
          if ("msg" in item && typeof item.msg === "string") {
            return item.msg as string;
          }
        }
        return JSON.stringify(item);
      })
      .filter((item) => item.length > 0)
      .join(" | ");
  }
  if (typeof detail === "object" && detail !== null) {
    return JSON.stringify(detail);
  }
  return "Unknown error";
}

async function readErrorMessage(response: Response, context: string): Promise<string> {
  try {
    const payload = (await response.json()) as ErrorPayload;
    if (payload && "detail" in payload) {
      const message = formatServerErrorDetail(payload.detail);
      return `${context}: ${message}`;
    }
  } catch {
    // keep fallback below
  }
  return `${context}: ${response.status}`;
}

function hasNonEmptyFilters(filters: AskFilters | undefined): filters is AskFilters {
  if (!filters) {
    return false;
  }

  return Object.values(filters).some((value) =>
    Array.isArray(value) ? value.length > 0 : value !== undefined,
  );
}

export async function askQuestion(
  question: string,
  filters?: AskFilters,
  allowedLabels?: string[],
): Promise<AskResponse> {
  const body: {
    question: string;
    language: "ru" | "en";
    include_graph: boolean;
    include_gaps: boolean;
    filters?: AskFilters;
    allowed_labels?: string[];
  } = {
    question,
    language: "ru",
    include_graph: true,
    include_gaps: true,
  };

  if (hasNonEmptyFilters(filters)) {
    body.filters = filters;
  }
  if (allowedLabels && allowedLabels.length > 0) {
    body.allowed_labels = allowedLabels;
  }

  const response = await fetch(`${API_BASE_URL}/qa/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "QA request failed"));
  }

  return (await response.json()) as AskResponse;
}

export async function listSources(): Promise<SourceSummary[]> {
  const response = await fetch(`${API_BASE_URL}/sources`);

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "Sources request failed"));
  }

  const payload = (await response.json()) as { sources: SourceSummary[] };
  return payload.sources;
}

export async function uploadSource(file: File): Promise<SourceIngestResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/sources/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "Source upload failed"));
  }

  return (await response.json()) as SourceIngestResponse;
}

export async function uploadArchive(file: File): Promise<ArchiveUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/sources/upload-archive`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "Archive upload failed"));
  }

  return (await response.json()) as ArchiveUploadResponse;
}

export async function importUrl(url: string): Promise<SourceIngestResponse> {
  const response = await fetch(`${API_BASE_URL}/sources/import-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "URL import failed"));
  }

  return (await response.json()) as SourceIngestResponse;
}

export async function deleteSource(sourceId: string): Promise<{ source_id: string; deleted: boolean }> {
  const response = await fetch(`${API_BASE_URL}/sources/${sourceId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "Source delete failed"));
  }

  return (await response.json()) as { source_id: string; deleted: boolean };
}

export async function fetchNeighborhood(
  entityId: string,
  depth = 1,
  limit = 100,
): Promise<GraphNeighborhood> {
  const params = new URLSearchParams({
    entity_id: entityId,
    depth: String(depth),
    limit: String(limit),
  });
  const response = await fetch(`${API_BASE_URL}/graph/neighborhood?${params}`);
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "Neighborhood request failed"));
  }
  return (await response.json()) as GraphNeighborhood;
}

export async function fetchEntitiesByType(
  entityType: string,
  limit = 24,
): Promise<TypedEntity[]> {
  const response = await fetch(
    `${API_BASE_URL}/entities/by-type?entity_type=${encodeURIComponent(entityType)}&limit=${limit}`,
  );
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "Entities request failed"));
  }
  const payload = (await response.json()) as { entities: TypedEntity[] };
  return payload.entities;
}

export async function searchEntities(query: string): Promise<EntitySearchResult[]> {
  const params = new URLSearchParams({ q: query });
  const response = await fetch(`${API_BASE_URL}/entities/search?${params}`);
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "Entity search failed"));
  }
  const payload = (await response.json()) as { entities: EntitySearchResult[] };
  return payload.entities;
}

export async function analyzeGaps(): Promise<GapsAnalysis> {
  const response = await fetch(`${API_BASE_URL}/gaps/analyze`);
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "Gaps analysis failed"));
  }
  return (await response.json()) as GapsAnalysis;
}

export async function fetchTimeline(): Promise<TimelineEvent[]> {
  const response = await fetch(`${API_BASE_URL}/graph/timeline`);
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "Timeline request failed"));
  }
  const payload = (await response.json()) as { events: TimelineEvent[] };
  return payload.events;
}

export async function fetchStats(): Promise<StatsOverview> {
  const response = await fetch(`${API_BASE_URL}/stats/overview`);
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "Stats request failed"));
  }
  return (await response.json()) as StatsOverview;
}

export async function fetchHealth(): Promise<HealthStatus> {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "Health request failed"));
  }
  return (await response.json()) as HealthStatus;
}

export async function listAnswerRuns(limit = 20): Promise<AnswerRunSummary[]> {
  const response = await fetch(`${API_BASE_URL}/stats/answer-runs?limit=${limit}`);
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "Answer runs request failed"));
  }
  const payload = (await response.json()) as { runs: AnswerRunSummary[] };
  return payload.runs;
}

export async function fetchEvalSummary(): Promise<EvalSummary> {
  const response = await fetch(`${API_BASE_URL}/eval/summary`);
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "Eval summary request failed"));
  }
  return (await response.json()) as EvalSummary;
}

export async function enrichSource(sourceId: string): Promise<{ scheduled: boolean }> {
  const response = await fetch(`${API_BASE_URL}/sources/${sourceId}/enrich`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "Enrich request failed"));
  }
  return (await response.json()) as { scheduled: boolean };
}

export async function reindexAll(): Promise<{ scheduled: boolean }> {
  const response = await fetch(`${API_BASE_URL}/sources/reindex-all`, { method: "POST" });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "Reindex request failed"));
  }
  return (await response.json()) as { scheduled: boolean };
}
