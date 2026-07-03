import { Database, FileUp, Link2, Loader2 } from "lucide-react";
import { type FormEvent, useState } from "react";

import type { SourceSummary } from "@/shared/api";
import { Panel } from "@/shared/ui";

type ArtifactBankPanelProps = {
  sources: SourceSummary[];
  loading: boolean;
  error: string | null;
  onUpload: (file: File) => Promise<void>;
  onImportUrl: (url: string) => Promise<void>;
  onDelete: (sourceId: string) => Promise<void>;
};

const STATUS_LABELS: Record<string, string> = {
  completed: "готов",
  running: "обработка",
  quarantined: "карантин",
  failed: "ошибка",
  ledger: "в леджере",
};

function statusChipClass(status: string): string {
  switch (status) {
    case "completed":
    case "ledger":
      return "status-chip status-ok";
    case "running":
      return "status-chip status-running";
    case "quarantined":
      return "status-chip status-warn";
    case "failed":
      return "status-chip status-error";
    default:
      return "status-chip";
  }
}

export function ArtifactBankPanel({
  sources,
  loading,
  error,
  onUpload,
  onImportUrl,
  onDelete,
}: ArtifactBankPanelProps) {
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      return;
    }
    const form = event.currentTarget;
    await onUpload(file);
    setFile(null);
    form.reset();
  }

  async function handleUrlSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) {
      return;
    }
    await onImportUrl(trimmed);
    setUrl("");
  }

  return (
    <Panel title="Artifact bank">
      <form className="upload-row" onSubmit={handleSubmit}>
        <label className="file-control">
          <FileUp size={16} />
          <span>{file ? file.name : "PDF / DOCX / DOC / XLSX / CSV / MD"}</span>
          <input
            accept=".pdf,.docx,.docm,.doc,.xlsx,.xls,.csv,.md,.markdown,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv,text/markdown,text/plain"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            type="file"
          />
        </label>
        <button className="secondary-button" disabled={loading || !file} type="submit">
          {loading ? <Loader2 size={16} /> : <Database size={16} />}
          Ingest
        </button>
      </form>
      <form className="upload-row" onSubmit={handleUrlSubmit}>
        <label className="file-control">
          <Link2 size={16} />
          <input
            className="url-input"
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://… online resource"
            type="url"
            value={url}
          />
        </label>
        <button
          className="secondary-button"
          disabled={loading || url.trim().length === 0}
          type="submit"
        >
          {loading ? <Loader2 size={16} /> : <Link2 size={16} />}
          Import URL
        </button>
      </form>
      {error ? <div className="inline-error">{error}</div> : null}
      <div className="source-list">
        {sources.map((source) => (
          <article className="source-card" key={source.source_id}>
            <div>
              <div className="source-title">{source.title}</div>
              <div className="source-meta">
                {source.document_type} · {source.security_label}
                {source.year ? ` · ${source.year}` : ""}
                {source.geography
                  ? ` · ${source.geography === "ru" ? "отечественный" : "зарубежный"}`
                  : ""}{" "}
                ·{" "}
                <span className={statusChipClass(source.status)}>
                  {STATUS_LABELS[source.status] ?? source.status}
                </span>
              </div>
            </div>
            <div className="source-counts">
              <span>{source.evidence_count} evidence</span>
              <span>{source.measurement_count} facts</span>
            </div>
            <button
              aria-label={`Delete source ${source.title}`}
              className="secondary-button"
              disabled={loading}
              onClick={async () => {
                await onDelete(source.source_id);
              }}
              type="button"
            >
              Delete
            </button>
          </article>
        ))}
      </div>
    </Panel>
  );
}
