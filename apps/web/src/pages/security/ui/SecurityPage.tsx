import { useEffect, useState } from "react";

import {
  fetchStats,
  listAnswerRuns,
  type AnswerRunSummary,
  type StatsOverview,
} from "@/shared/api";
import { Panel } from "@/shared/ui";

const LABEL_HINTS: Record<string, string> = {
  public: "открытые материалы",
  internal: "внутренние отчёты",
  confidential: "коммерчески чувствительные",
  restricted: "ограниченный доступ",
};

function verdictChip(run: AnswerRunSummary) {
  const verification = run.verification;
  const clean =
    (verification.unsupported_claim_count ?? 0) === 0 &&
    (verification.source_label_leak_count ?? 0) === 0 &&
    (verification.numeric_mismatch_count ?? 0) === 0;
  return clean ? (
    <span className="status-chip status-ok">верифицирован</span>
  ) : (
    <span className="status-chip status-warn">частично</span>
  );
}

export function SecurityPage() {
  const [stats, setStats] = useState<StatsOverview | null>(null);
  const [runs, setRuns] = useState<AnswerRunSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [nextStats, nextRuns] = await Promise.all([fetchStats(), listAnswerRuns(15)]);
        setStats(nextStats);
        setRuns(nextRuns);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Не удалось загрузить данные");
      }
    })();
  }, []);

  return (
    <div className="workbench-grid">
      <div className="stack">
        <Panel title="Журнал ответов (аудит)">
          {error ? <div className="inline-error">{error}</div> : null}
          {runs.length > 0 ? (
            <table className="experiment-table">
              <thead>
                <tr>
                  <th>Вопрос</th>
                  <th>Режим</th>
                  <th>Латентность</th>
                  <th>Верификация</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.run_id}>
                    <td>{run.question.slice(0, 80)}</td>
                    <td>{run.answer_mode ?? "—"}</td>
                    <td>{run.latency_ms != null ? `${(run.latency_ms / 1000).toFixed(1)} с` : "—"}</td>
                    <td>{verdictChip(run)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="status-pill">Журнал пуст — задайте первый вопрос.</div>
          )}
          <p className="page-caption">
            Каждый ответ сохраняется с воспроизводимым run_id, вопросом, фильтрами и
            полным результатом верификации — основа аудита действий.
          </p>
        </Panel>
      </div>
      <div className="stack">
        <Panel title="Метки доступа источников">
          {stats ? (
            <div className="kv-list">
              {Object.entries(stats.security_labels).map(([label, count]) => (
                <div className="kv-row" key={label}>
                  <span>
                    {label}
                    {LABEL_HINTS[label] ? ` · ${LABEL_HINTS[label]}` : ""}
                  </span>
                  <span className="kv-value">{count}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="status-pill">Загрузка…</div>
          )}
          <p className="page-caption">
            Фильтрация по меткам применяется ДО построения ответа: запрещённые спаны не
            попадают ни в пакет доказательств, ни в промпт модели. Утечка метки — метрика
            eval с целевым нулём.
          </p>
        </Panel>
        <Panel title="Контур защиты">
          <div className="kv-list">
            <div className="kv-row">
              <span>Prompt-инъекции</span>
              <span className="kv-value">текст документов = данные, не команды</span>
            </div>
            <div className="kv-row">
              <span>Цитатный гейт</span>
              <span className="kv-value">предложение без span_id отбрасывается</span>
            </div>
            <div className="kv-row">
              <span>Числовой гейт</span>
              <span className="kv-value">числа сверяются с документами</span>
            </div>
            <div className="kv-row">
              <span>Загрузка файлов</span>
              <span className="kv-value">MIME + размер + карантин</span>
            </div>
            <div className="kv-row">
              <span>Секреты</span>
              <span className="kv-value">только в server-side env</span>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
