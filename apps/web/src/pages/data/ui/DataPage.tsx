import { RefreshCcw } from "lucide-react";
import { useEffect, useState } from "react";

import {
  deleteSource,
  enrichSource,
  fetchStats,
  importUrl,
  listSources,
  reindexAll,
  uploadSource,
  type SourceSummary,
  type StatsOverview,
} from "@/shared/api";
import { Panel } from "@/shared/ui";
import { ArtifactBankPanel } from "@/widgets/artifact-bank";

export function DataPage() {
  const [sources, setSources] = useState<SourceSummary[]>([]);
  const [stats, setStats] = useState<StatsOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  async function refresh() {
    try {
      setError(null);
      const [nextSources, nextStats] = await Promise.all([listSources(), fetchStats()]);
      setSources(nextSources);
      setStats(nextStats);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить данные");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  // Background enrichment: keep polling while anything is still processing.
  useEffect(() => {
    if (!sources.some((source) => source.status === "running")) {
      return;
    }
    const timer = window.setInterval(() => {
      void refresh();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [sources]);

  async function withBusy(action: () => Promise<unknown>, doneNotice?: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      await refresh();
      if (doneNotice) {
        setNotice(doneNotice);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Операция не выполнена");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="workbench-grid">
      <div className="stack">
        {stats ? (
          <Panel title="Состояние корпуса">
            <div className="stat-grid">
              <div className="stat-card">
                <div className="stat-value">{stats.sources}</div>
                <div className="stat-label">источников</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.evidence_spans}</div>
                <div className="stat-label">evidence-спанов</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.measurements}</div>
                <div className="stat-label">измерений</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.relations}</div>
                <div className="stat-label">связей графа</div>
              </div>
            </div>
            <div className="button-row">
              <button
                className="secondary-button"
                disabled={busy}
                onClick={() => {
                  void withBusy(
                    () => reindexAll(),
                    "Фоновый реиндекс запущен — поиск обновится по мере пересборки.",
                  );
                }}
                type="button"
              >
                <RefreshCcw size={14} /> Пересобрать поисковый индекс
              </button>
            </div>
            {notice ? <div className="status-pill">{notice}</div> : null}
          </Panel>
        ) : null}

        <ArtifactBankPanel
          error={error}
          loading={busy}
          onDelete={(sourceId) => withBusy(() => deleteSource(sourceId))}
          onEnrich={(sourceId) =>
            withBusy(
              () => enrichSource(sourceId),
              "Переобогащение запущено — статус источника обновится автоматически.",
            )
          }
          onImportUrl={(url) => withBusy(() => importUrl(url))}
          onUpload={(file) => withBusy(() => uploadSource(file))}
          sources={sources}
        />
      </div>
      <div className="stack">
        <Panel title="Как обрабатываются данные">
          <div className="kv-list">
            <div className="kv-row">
              <span>PDF / DOCX / DOCM</span>
              <span className="kv-value">Docling, таблицы построчно</span>
            </div>
            <div className="kv-row">
              <span>DOC (legacy)</span>
              <span className="kv-value">antiword / catdoc</span>
            </div>
            <div className="kv-row">
              <span>XLSX / XLS</span>
              <span className="kv-value">листы → строки с провенансом</span>
            </div>
            <div className="kv-row">
              <span>ZIP / .zip.001 / RAR</span>
              <span className="kv-value">батч-ингестер разворачивает</span>
            </div>
            <div className="kv-row">
              <span>Сканы без текста</span>
              <span className="kv-value">карантин (без OCR)</span>
            </div>
          </div>
          <p className="page-caption">
            После парсинга каждый документ проходит извлечение сущностей
            (словарь → GLiNER → LLM), становится узлом-публикацией графа с годом и
            географией и индексируется в гибридный поиск (dense 1536 + BM25).
          </p>
        </Panel>
      </div>
    </div>
  );
}
