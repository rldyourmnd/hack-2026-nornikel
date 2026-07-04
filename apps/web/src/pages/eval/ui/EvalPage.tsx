import { Activity, CheckCircle2, Gauge, Server, ShieldCheck, Sigma, TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  fetchEvalSummary,
  fetchHealth,
  fetchStats,
  listAnswerRuns,
  type AnswerRunSummary,
  type EvalSummary,
  type HealthStatus,
  type StatsOverview,
} from "@/shared/api";
import { Panel } from "@/shared/ui";

const METRIC_LABELS: Record<string, { label: string; hint: string; ideal: string }> = {
  citation_coverage: {
    label: "Покрытие цитатами",
    hint: "Доля предложений ответа, подтверждённых span_id из пакета доказательств",
    ideal: "1.0",
  },
  numeric_mismatch_count: {
    label: "Сфабрикованные числа",
    hint: "Числа в ответе, которых нет дословно в процитированных фрагментах",
    ideal: "0",
  },
  unsupported_claim_count: {
    label: "Неподтверждённые утверждения",
    hint: "Предложения без единой валидной цитаты",
    ideal: "0",
  },
  source_label_leak_count: {
    label: "Утечки меток доступа",
    hint: "Цитаты из источников, запрещённых политикой безопасности",
    ideal: "0",
  },
  prompt_injection_success_count: {
    label: "Успешные инъекции",
    hint: "Инструкции, внедрённые в вопрос или документ и исполненные моделью",
    ideal: "0",
  },
  semantic_unsupported_count: {
    label: "Семантически неподтверждённые claims",
    hint: "LLM-verifier не нашёл смысловой поддержки в evidence",
    ideal: "0",
  },
  conflict_count: { label: "Конфликты", hint: "Обнаруженные противоречия в релевантных ответах", ideal: "—" },
  experiment_count: { label: "Эксперименты", hint: "Структурированные эксперименты на вопрос", ideal: "—" },
  evidence_count: { label: "Доказательства", hint: "Среднее число evidence-спанов в ответе", ideal: "—" },
  gap_count: { label: "Пробелы", hint: "Честно показанные пробелы в данных", ideal: "—" },
  latency_ms: { label: "Латентность, мс", hint: "Среднее время ответа", ideal: "—" },
};

function formatMetric(value: number): string {
  return Number.isInteger(value) ? value.toLocaleString("ru-RU") : value.toFixed(3);
}

function formatNumber(value: number | null | undefined): string {
  return (value ?? 0).toLocaleString("ru-RU");
}

export function EvalPage() {
  const [summary, setSummary] = useState<EvalSummary | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [stats, setStats] = useState<StatsOverview | null>(null);
  const [runs, setRuns] = useState<AnswerRunSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchEvalSummary()
      .then(setSummary)
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Не удалось получить метрики");
      });
    void fetchHealth().then(setHealth).catch(() => setHealth(null));
    void fetchStats().then(setStats).catch(() => setStats(null));
    void listAnswerRuns(5).then(setRuns).catch(() => setRuns([]));
  }, []);

  const latestVerification = useMemo(() => runs[0]?.verification ?? {}, [runs]);
  const unsafeSignals =
    (latestVerification.unsupported_claim_count ?? 0) +
    (latestVerification.numeric_mismatch_count ?? 0) +
    (latestVerification.prompt_injection_success_count ?? 0) +
    (latestVerification.source_label_leak_count ?? 0);
  const latestCoverage = latestVerification.citation_coverage;

  return (
    <div className="page-wrap quality-page-v2">
      <section className="quality-command-center">
        <div>
          <div className="section-eyebrow">Evidence quality gates</div>
          <h2>Качество ответов: цитаты, числа, безопасность, полнота графа</h2>
          <p>
            Эта страница показывает не презентационные проценты, а реальные runtime-сигналы: health API,
            eval summary, последние QA runs и объём графа, на котором строятся ответы.
          </p>
        </div>
        <div className={`quality-verdict ${unsafeSignals === 0 ? "ok" : "warn"}`}>
          {unsafeSignals === 0 ? <CheckCircle2 size={28} /> : <TriangleAlert size={28} />}
          <strong>{unsafeSignals === 0 ? "No unsafe claims" : `${unsafeSignals} signals`}</strong>
          <span>по последнему ответу</span>
        </div>
      </section>

      <section className="quality-gate-grid">
        {[
          { Icon: Server, label: "API", value: health?.status ?? "unknown", hint: health?.embedding_backend ?? "backend" },
          { Icon: ShieldCheck, label: "LLM", value: health?.llm_configured ? "configured" : "not configured", hint: health?.llm_enabled ? "enabled" : "disabled" },
          { Icon: Sigma, label: "Numeric facts", value: formatNumber(stats?.numeric_facts), hint: "проверяются дословно" },
          { Icon: Activity, label: "Quarantine", value: formatNumber(stats?.quarantined), hint: "не идёт в ответы" },
          {
            Icon: Gauge,
            label: "Citation coverage",
            value: latestCoverage === undefined ? "n/a" : `${Math.round(latestCoverage * 100)}%`,
            hint: "последний run",
          },
        ].map(({ Icon, label, value, hint }) => (
          <article className="quality-gate-card" key={label}>
            <Icon size={21} />
            <span>{label}</span>
            <strong>{value}</strong>
            <small>{hint}</small>
          </article>
        ))}
      </section>

      <div className="workbench-grid workbench-grid-wide">
        <div className="stack">
          <Panel title="Метрики последнего eval-прогона">
            {error ? <div className="inline-error">{error}</div> : null}
            {summary ? (
              <>
                <div className="status-pill">
                  {summary.status === "stored_eval_run"
                    ? `Сохранённый прогон ${summary.run_id ?? ""} · ${summary.question_count ?? "?"} вопросов`
                    : "Живая проверка (сохранённый прогон ещё не записан)"}
                </div>
                {Object.keys(summary.metrics).length > 0 ? (
                  <table className="experiment-table quality-table">
                    <thead>
                      <tr>
                        <th>Метрика</th>
                        <th>Значение</th>
                        <th>Цель</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(summary.metrics).map(([name, value]) => {
                        const meta = METRIC_LABELS[name];
                        return (
                          <tr key={name}>
                            <td>
                              <div>{meta?.label ?? name}</div>
                              {meta ? <div className="source-meta">{meta.hint}</div> : null}
                            </td>
                            <td>{formatMetric(value)}</td>
                            <td>{meta?.ideal ?? "—"}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                ) : (
                  <div className="qa-empty-state compact">
                    Для нового полного графа сохранённый eval ещё не записан; live QA runs и health-сигналы показаны справа и сверху.
                  </div>
                )}
              </>
            ) : (
              <div className="status-pill">Загрузка eval…</div>
            )}
          </Panel>
        </div>

        <div className="stack">
          <Panel title="Последние QA-проверки">
            {runs.length > 0 ? (
              <div className="quality-run-list">
                {runs.map((run) => (
                  <article className="quality-run-card" key={run.run_id}>
                    <strong>{run.question}</strong>
                    <span>
                      coverage {run.verification.citation_coverage ?? "n/a"} · unsupported {run.verification.unsupported_claim_count ?? 0} · numeric mismatches {run.verification.numeric_mismatch_count ?? 0}
                    </span>
                    <small>{new Date(run.created_at).toLocaleString("ru-RU")}</small>
                  </article>
                ))}
              </div>
            ) : (
              <div className="qa-empty-state compact">Пока нет сохранённых QA runs после переключения графа.</div>
            )}
          </Panel>

          <Panel title="Как устроена проверка">
            <div className="quality-contract-list">
              <div><strong>1</strong><span>Каждое предложение ответа должно иметь supporting span.</span></div>
              <div><strong>2</strong><span>Числа сверяются с процитированными фрагментами, не с памятью модели.</span></div>
              <div><strong>3</strong><span>Prompt-injection и source-label leaks считаются отдельными gate-сигналами.</span></div>
              <div><strong>4</strong><span>При недостатке evidence система показывает пробел, а не додумывает ответ.</span></div>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
