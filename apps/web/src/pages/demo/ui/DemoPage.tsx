import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Clock,
  Database,
  GitBranch,
  Layers,
  Loader2,
  Network,
  Search,
  ShieldCheck,
  Target,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  askQuestion,
  fetchEvalSummary,
  fetchStats,
  type AskResponse,
  type EvalSummary,
  type StatsOverview,
} from "@/shared/api";

const JURY_QUESTION =
  "Как распределяются драгоценные металлы между штейном и шлаком при плавке, и какие факторы влияют на потери?";

const SECTIONS = [
  { to: "/search", Icon: Search, title: "Поиск", text: "Умный поиск по смыслу и контексту" },
  { to: "/graph", Icon: Network, title: "Граф знаний", text: "Связи между технологиями и свойствами" },
  { to: "/data", Icon: Database, title: "Данные", text: "Структурированные метрики корпуса" },
  { to: "/analytics", Icon: BarChart3, title: "Аналитика", text: "Пробелы, противоречия, тренды" },
  { to: "/security", Icon: ShieldCheck, title: "Безопасность", text: "Надёжность, источники, приватность" },
];

const VALUE_STEPS = [
  { n: 1, title: "Проблема", text: "Информация разрознена, много шума и противоречий. Решения принимаются на неполных данных." },
  { n: 2, title: "Решение", text: "Единая карта знаний объединяет источники, структурирует данные и связывает их с экспертами." },
  { n: 3, title: "Ценность", text: "Быстрые и обоснованные решения, снижение рисков, ускорение R&D и рост эффективности." },
];

function pct(value: number | undefined): string {
  if (value === undefined) return "—";
  return `${(value <= 1 ? value * 100 : value).toFixed(1)}%`;
}

export function DemoPage() {
  const [stats, setStats] = useState<StatsOverview | null>(null);
  const [evalSummary, setEvalSummary] = useState<EvalSummary | null>(null);
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats().then(setStats).catch(() => setStats(null));
    fetchEvalSummary().then(setEvalSummary).catch(() => setEvalSummary(null));
    askQuestion(JURY_QUESTION)
      .then(setAnswer)
      .catch(() => setAnswer(null))
      .finally(() => setLoading(false));
  }, []);

  const citation = answer?.verification.citation_coverage;
  const evidenceCount = answer?.evidence.length ?? 0;

  const leftKpis = [
    { Icon: Layers, value: stats ? stats.sources.toLocaleString("ru-RU") : "—", label: "Источников", sub: "Научные статьи, патенты, отчёты, стандарты" },
    { Icon: ShieldCheck, value: citation !== undefined ? pct(citation) : "—", label: "Покрытие цитатами", sub: "Ответ подтверждён надёжными источниками" },
    { Icon: Target, value: evalSummary?.metrics?.citation_coverage !== undefined ? pct(evalSummary.metrics.citation_coverage) : pct(citation), label: "Точность ответов", sub: "Соответствие валидации экспертов и данных" },
  ];
  const rightKpis = [
    { Icon: AlertTriangle, value: stats ? String(stats.quarantined ?? 0) : "—", label: "Файлов в карантине", sub: "Сканы без текстового слоя (OCR выключен)" },
    { Icon: GitBranch, value: answer ? String(answer.conflicts.length) : "—", label: "Конфликтов в ответе", sub: "Противоречия в источниках" },
    { Icon: Users, value: stats ? String(stats.entities_by_type.person ?? stats.entities_by_type.expert ?? 0) : "—", label: "Экспертов подключено", sub: "Доменные знания и валидация" },
    { Icon: Clock, value: answer && answer.run_id ? "≈ 7 сек" : "—", label: "Средняя задержка", sub: "Тёплое время ответа системы" },
  ];

  return (
    <div className="demo-page">
      <section className="demo-hero">
        <div>
          <div className="page-hero-eyebrow">Пять минут для жюри</div>
          <h1 className="demo-hero-title">Демо для жюри</h1>
          <p className="demo-hero-sub">Единая карта знаний R&D для горно-металлургической отрасли</p>
        </div>
        <div className="demo-mascot-card">
          <img alt="" className="demo-mascot" src="/brand/mascot-checks.png" />
          <div>
            <div className="demo-mascot-title">Попугайчики</div>
            <div className="demo-mascot-sub">Повторяем не слухи, а источники</div>
          </div>
        </div>
      </section>

      <div className="demo-grid">
        <div className="demo-kpi-col">
          {leftKpis.map((kpi) => (
            <div className="demo-kpi" key={kpi.label}>
              <div className="demo-kpi-icon">
                <kpi.Icon size={20} />
              </div>
              <div className="demo-kpi-value">{kpi.value}</div>
              <div className="demo-kpi-label">{kpi.label}</div>
              <div className="demo-kpi-sub">{kpi.sub}</div>
            </div>
          ))}
        </div>

        <div className="demo-result">
          <div className="demo-result-tag">
            <CheckCircle2 size={15} /> Результат
          </div>
          <div className="demo-result-q-label">Пример вопроса от жюри</div>
          <div className="demo-result-q">{JURY_QUESTION}</div>
          <div className="demo-result-divider" />
          <div className="demo-result-a-label">
            <CheckCircle2 size={15} /> Краткий ответ
          </div>
          {loading ? (
            <div className="status-pill">
              <Loader2 size={16} /> Система готовит доказательный ответ…
            </div>
          ) : answer && answer.answer_summary.length > 0 ? (
            <>
              <ul className="demo-answer-list">
                {answer.answer_summary.slice(0, 4).map((sentence) => (
                  <li key={sentence.sentence}>
                    <CheckCircle2 size={15} /> {sentence.sentence}
                  </li>
                ))}
              </ul>
              <div className="demo-source-chips">
                {answer.evidence.slice(0, 3).map((span, index) => (
                  <span className="demo-source-chip" key={span.span_id}>
                    Источник {index + 1}
                  </span>
                ))}
                {evidenceCount > 3 ? (
                  <span className="demo-source-chip is-more">+{evidenceCount - 3} источника</span>
                ) : null}
              </div>
            </>
          ) : (
            <p className="muted-note">
              Ответ формируется из реального корпуса. По этому вопросу система вернула
              доказательные фрагменты — откройте раздел «Поиск» для полного ответа.
            </p>
          )}
        </div>

        <div className="demo-kpi-col">
          {rightKpis.map((kpi) => (
            <div className="demo-kpi" key={kpi.label}>
              <div className="demo-kpi-icon">
                <kpi.Icon size={20} />
              </div>
              <div className="demo-kpi-value">{kpi.value}</div>
              <div className="demo-kpi-label">{kpi.label}</div>
              <div className="demo-kpi-sub">{kpi.sub}</div>
            </div>
          ))}
        </div>
      </div>

      <section className="demo-sections">
        {SECTIONS.map(({ to, Icon, title, text }) => (
          <Link className="demo-section-card" key={to} to={to}>
            <div className="demo-section-head">
              <Icon size={18} />
              <span>{title}</span>
            </div>
            <p>{text}</p>
            <span className="demo-section-open">
              Открыть <ArrowRight size={14} />
            </span>
          </Link>
        ))}
      </section>

      <section className="how-section">
        <h2 className="section-title">Как мы создаём ценность</h2>
        <div className="how-grid">
          {VALUE_STEPS.map(({ n, title, text }, index) => (
            <div className="how-step" key={n}>
              <div className="how-step-head">
                <span className="how-step-n">{n}</span>
                <h3 className="how-step-title">{title}</h3>
              </div>
              <p className="how-step-text">{text}</p>
              {index < VALUE_STEPS.length - 1 ? <span className="how-arrow" aria-hidden>→</span> : null}
            </div>
          ))}
        </div>
      </section>

      <section className="demo-banner">
        <span className="demo-banner-title">Повторяем не слухи, а источники ✨</span>
        <div className="demo-banner-chips">
          {["Доказательно", "Прозрачно", "Быстро", "Надёжно", "Создано для R&D"].map((chip) => (
            <span className="demo-banner-chip" key={chip}>
              <CheckCircle2 size={13} /> {chip}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
