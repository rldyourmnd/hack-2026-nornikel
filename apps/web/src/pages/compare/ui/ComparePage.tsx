import { ArrowRight, CheckCircle2, MinusCircle } from "lucide-react";
import { Link } from "react-router-dom";

import { PageHero, Panel } from "@/shared/ui";

type Verdict = "strong" | "medium" | "needs_data";

const LEGEND: Array<{ verdict: Verdict; label: string }> = [
  { verdict: "strong", label: "Подтверждено источниками" },
  { verdict: "medium", label: "Частичные данные" },
  { verdict: "needs_data", label: "Нужны данные" },
];

const ROWS: Array<{ metric: string; a: Verdict; b: Verdict; c: Verdict }> = [
  { metric: "Эффективность извлечения", a: "strong", b: "medium", c: "medium" },
  { metric: "CAPEX / OPEX", a: "medium", b: "needs_data", c: "medium" },
  { metric: "Энергозатраты", a: "medium", b: "strong", c: "needs_data" },
  { metric: "Применимость в холодном климате", a: "needs_data", b: "medium", c: "strong" },
  { metric: "Экологические ограничения", a: "medium", b: "medium", c: "strong" },
  { metric: "Уровень доказательности", a: "strong", b: "medium", c: "needs_data" },
];

const COLUMNS = ["Биоокисление", "Гипербарическое выщелачивание", "Флотационные реагенты"];

function VerdictCell({ verdict }: { verdict: Verdict }) {
  if (verdict === "needs_data") {
    return (
      <span className="verdict-cell verdict-needs">
        <MinusCircle size={14} /> нет данных
      </span>
    );
  }
  return (
    <span className={`verdict-cell ${verdict === "strong" ? "verdict-strong" : "verdict-medium"}`}>
      <CheckCircle2 size={14} /> {verdict === "strong" ? "подтверждено" : "частично"}
    </span>
  );
}

export function ComparePage() {
  return (
    <div className="page-wrap">
      <PageHero
        eyebrow="Сравнительный анализ"
        title="Сравнение технологий"
        caption="Сопоставление вариантов по эффективности, CAPEX/OPEX, климату и ограничениям — каждая ячейка с источником или статусом «нужны данные»."
        aside={<img alt="" className="page-hero-illus" src="/brand/an-compare.png" />}
      />

      <Panel title="Рекомендуемая стратегия">
        <p className="muted-note">
          Каждая ячейка сравнения строится из фактов корпуса и ссылается на источник — относительные
          оценки и фактические числа не смешиваются. Ниже — пример структуры для вопроса о повышении
          извлечения никеля; полное сравнение собирается по конкретному запросу в поиске.
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

      <div className="table-scroll">
        <table className="compare-table">
          <thead>
            <tr>
              <th>Показатель</th>
              {COLUMNS.map((col) => (
                <th key={col}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.metric}>
                <td className="compare-metric">{row.metric}</td>
                <td>
                  <VerdictCell verdict={row.a} />
                </td>
                <td>
                  <VerdictCell verdict={row.b} />
                </td>
                <td>
                  <VerdictCell verdict={row.c} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Panel title="Собрать сравнение по своему вопросу">
        <p className="muted-note">
          Задайте сравнительный вопрос — система соберёт таблицу с показателями, источниками и
          группировкой «отечественная / зарубежная практика».
        </p>
        <Link
          className="primary-button"
          to="/search?q=Сравни технологии обеднения шлака по потерям металлов и энергозатратам"
        >
          Открыть в поиске <ArrowRight size={15} />
        </Link>
      </Panel>
    </div>
  );
}
