import { ArrowRight, CheckCircle2, Database, GitCompare, MinusCircle, ShieldCheck, Sigma } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchStats, type StatsOverview } from "@/shared/api";
import { PageHero, Panel } from "@/shared/ui";

type Verdict = "strong" | "medium" | "needs_data";

const LEGEND: Array<{ verdict: Verdict; label: string }> = [
  { verdict: "strong", label: "Подтверждено источниками" },
  { verdict: "medium", label: "Частичные данные" },
  { verdict: "needs_data", label: "Нужны данные" },
];

const ROWS: Array<{ metric: string; a: Verdict; b: Verdict; c: Verdict; note: string }> = [
  { metric: "Селективность / извлечение", a: "strong", b: "medium", c: "medium", note: "проверяется по evidence spans и numeric facts" },
  { metric: "CAPEX / OPEX", a: "medium", b: "needs_data", c: "medium", note: "если числа не найдены — показываем пробел" },
  { metric: "Энергозатраты", a: "medium", b: "strong", c: "needs_data", note: "числа сверяются с цитатами" },
  { metric: "Применимость к руде / воде / газу", a: "needs_data", b: "medium", c: "strong", note: "учитываются материал, режим, география" },
  { metric: "Экологические ограничения", a: "medium", b: "medium", c: "strong", note: "связи с limitation / condition" },
  { metric: "Уровень доказательности", a: "strong", b: "medium", c: "needs_data", note: "coverage, unsupported, source labels" },
];

const COLUMNS = ["Мембранная очистка", "Реагентная обработка", "Глубокая закачка / изоляция"];
const DEFAULT_COMPARE_QUERY =
  "Технико-экономическое сравнение вариантов подготовки воды (обессоливания) для предприятий горно-металлургической промышленности";

function VerdictCell({ verdict }: { verdict: Verdict }) {
  if (verdict === "needs_data") {
    return (
      <span className="verdict-cell verdict-needs">
        <MinusCircle size={14} /> нужны данные
      </span>
    );
  }
  return (
    <span className={`verdict-cell ${verdict === "strong" ? "verdict-strong" : "verdict-medium"}`}>
      <CheckCircle2 size={14} /> {verdict === "strong" ? "подтверждено" : "частично"}
    </span>
  );
}

function formatNumber(value: number | null | undefined): string {
  return (value ?? 0).toLocaleString("ru-RU");
}

export function ComparePage() {
  const [stats, setStats] = useState<StatsOverview | null>(null);

  useEffect(() => {
    void fetchStats().then(setStats).catch(() => setStats(null));
  }, []);

  return (
    <div className="page-wrap compare-page-v2">
      <PageHero
        eyebrow="Сравнительный анализ"
        title="Сравнение технологий на evidence-графе"
        caption="Сопоставление вариантов по эффективности, CAPEX/OPEX, климату и ограничениям. Ответ строится через поиск, а матрица показывает, где есть доказательства и где нужны данные."
        aside={<img alt="" className="page-hero-illus" src="/brand/an-compare.png" />}
      />

      <section className="compare-proof-strip">
        {[
          { Icon: Database, value: stats?.sources, label: "источников в ledger" },
          { Icon: Sigma, value: stats?.numeric_facts, label: "числовых фактов" },
          { Icon: GitCompare, value: stats?.relations, label: "связей для объяснений" },
          { Icon: ShieldCheck, value: stats?.quarantined, label: "карантин без домыслов" },
        ].map(({ Icon, value, label }) => (
          <article className="compare-proof-card" key={label}>
            <Icon size={21} />
            <strong>{formatNumber(value)}</strong>
            <span>{label}</span>
          </article>
        ))}
      </section>

      <Panel title="Как читать сравнение">
        <p className="muted-note">
          Матрица ниже — демонстрационный шаблон для вопросов жюри: вода, шахтные воды,
          SO2, техногенный гипс, электролитическое производство. В рабочем сценарии пользователь
          отправляет сравнительный вопрос в поиск, получает таблицу вариантов, цитаты и список
          источников для каждой ячейки.
        </p>
        <div className="verdict-legend">
          {LEGEND.map(({ verdict, label }) => (
            <span className="verdict-legend-item" key={verdict}>
              <span className={`verdict-dot verdict-${verdict === "needs_data" ? "needs" : verdict}`} />
              {label}
            </span>
          ))}
        </div>
      </Panel>

      <div className="table-scroll compare-table-shell">
        <table className="compare-table compare-table-v2">
          <thead>
            <tr>
              <th>Критерий</th>
              {COLUMNS.map((col) => (
                <th key={col}>{col}</th>
              ))}
              <th>Контроль доказательности</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.metric}>
                <td className="compare-metric">{row.metric}</td>
                <td><VerdictCell verdict={row.a} /></td>
                <td><VerdictCell verdict={row.b} /></td>
                <td><VerdictCell verdict={row.c} /></td>
                <td className="compare-note">{row.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <section className="compare-cta-panel">
        <div>
          <div className="section-eyebrow">jury scenario</div>
          <h2>Собрать сравнение по реальному вопросу</h2>
          <p>
            Запустим вопрос про технико-экономическое сравнение подготовки воды: система найдёт
            evidence, выделит цитаты по источникам и покажет, где данных недостаточно.
          </p>
        </div>
        <Link className="primary-button" to={`/search?q=${encodeURIComponent(DEFAULT_COMPARE_QUERY)}`}>
          Открыть в поиске <ArrowRight size={15} />
        </Link>
      </section>
    </div>
  );
}
