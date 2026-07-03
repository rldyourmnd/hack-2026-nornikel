import { useEffect, useState } from "react";

import { fetchEvalSummary, type EvalSummary } from "@/shared/api";
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
  conflict_count: {
    label: "Конфликтов на вопрос",
    hint: "Среднее число обнаруженных противоречий в релевантных ответах",
    ideal: "—",
  },
  experiment_count: {
    label: "Экспериментов на вопрос",
    hint: "Среднее число подобранных структурированных экспериментов",
    ideal: "—",
  },
  evidence_count: {
    label: "Доказательств на вопрос",
    hint: "Среднее число evidence-спанов в пакете ответа",
    ideal: "—",
  },
  gap_count: {
    label: "Пробелов на вопрос",
    hint: "Среднее число честно показанных пробелов в данных",
    ideal: "—",
  },
  latency_ms: { label: "Латентность, мс", hint: "Среднее время ответа", ideal: "—" },
};

export function EvalPage() {
  const [summary, setSummary] = useState<EvalSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setSummary(await fetchEvalSummary());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Не удалось получить метрики");
      }
    })();
  }, []);

  return (
    <div className="workbench-grid">
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
              <table className="experiment-table">
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
                        <td>{Number.isInteger(value) ? value : value.toFixed(3)}</td>
                        <td>{meta?.ideal ?? "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </>
          ) : (
            <div className="status-pill">Загрузка…</div>
          )}
        </Panel>
      </div>
      <div className="stack">
        <Panel title="Как устроена проверка">
          <div className="kv-list">
            <div className="kv-row">
              <span>17 eval-вопросов</span>
              <span className="kv-value">включая адверсариальные</span>
            </div>
            <div className="kv-row">
              <span>Гейт цитат</span>
              <span className="kv-value">каждое предложение → span_id</span>
            </div>
            <div className="kv-row">
              <span>Числовой гейт</span>
              <span className="kv-value">цифры дословно из документов</span>
            </div>
            <div className="kv-row">
              <span>Инъекции</span>
              <span className="kv-value">2 сценария атаки в наборе</span>
            </div>
          </div>
          <p className="page-caption">
            Eval запускается детерминированно (без сети и LLM-ключей) в CI и с реальной
            моделью на стенде. Ответ, не прошедший верификацию, деградирует до
            детерминированной сводки — сфабрикованный текст не доходит до пользователя.
          </p>
        </Panel>
      </div>
    </div>
  );
}
