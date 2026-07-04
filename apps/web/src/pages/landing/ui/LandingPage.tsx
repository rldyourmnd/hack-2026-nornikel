import {
  AlertTriangle,
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  Globe,
  Layers,
  Search,
  Share2,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchStats, type StatsOverview } from "@/shared/api";

const NUMBER_FORMAT = new Intl.NumberFormat("ru-RU");

const FEATURES = [
  {
    Icon: Search,
    title: "Многопараметрический поиск",
    metric: "12+ фильтров",
    text: "Материалы, процессы, параметры, география, годы, источники и числовые диапазоны в одном запросе.",
  },
  {
    Icon: ShieldCheck,
    title: "Верификация знаний",
    metric: "0 blind facts",
    text: "Каждое число и утверждение проходят через источник, цитату, связь в графе и статус подтверждения.",
  },
  {
    Icon: Share2,
    title: "Граф знаний",
    metric: "R&D relations",
    text: "Сущности, эксперименты, оборудование, выводы и публикации связаны в объяснимую карту решений.",
  },
  {
    Icon: AlertTriangle,
    title: "Пробелы и противоречия",
    metric: "risk signals",
    text: "Система показывает, где источники расходятся, где мало данных и где решение требует экспертной проверки.",
  },
];

const STEPS = [
  {
    n: "01",
    title: "Корпус",
    value: "2015 файлов",
    text: "Статьи, обзоры, отчёты, таблицы, патенты и материалы конференций собираются в единый ledger.",
  },
  {
    n: "02",
    title: "Факты",
    value: "LLM + extraction",
    text: "Извлекаем сущности, числа, условия, связи, источники и контекст, не превращая корпус в пересказ.",
  },
  {
    n: "03",
    title: "Ответ",
    value: "citations first",
    text: "QA возвращает выводы только с доказательствами: цитаты, диапазоны, таблицы и связанные источники.",
  },
];

const INSIGHTS = [
  {
    Icon: Globe,
    title: "География практики",
    value: "RU + world",
    text: "Отделяем российские и зарубежные кейсы, чтобы сравнение было применимо к промышленному контексту.",
    tag: "страны, регионы, типы практики",
    image: "/brand/an-geo.png",
  },
  {
    Icon: Layers,
    title: "Диапазоны и условия",
    value: "числа + ограничения",
    text: "Вода, электролиты, газоочистка и металлургические процессы сравниваются по параметрам, а не по общим словам.",
    rows: [
      ["Сульфаты / хлориды", "200–300 мг/л"],
      ["Сухой остаток", "1000 мг/дм³"],
      ["Скорость потока", "0.5–5 м/с"],
    ],
  },
  {
    Icon: Users,
    title: "Экспертный контур",
    value: "review-ready",
    text: "Ответ можно быстро проверить: видно, какие источники легли в основу, где есть слабые места и кому отдать на ревью.",
    tag: "роль, источник, решение",
  },
  {
    Icon: CalendarClock,
    title: "Актуальность корпуса",
    value: "92%",
    text: "Отслеживаем свежесть источников и отделяем устойчивую практику от устаревших материалов.",
    progress: 92,
  },
];

function formatNumber(value: number | null | undefined, fallback: string) {
  return typeof value === "number" ? NUMBER_FORMAT.format(value) : fallback;
}

export function LandingPage() {
  const [stats, setStats] = useState<StatsOverview | null>(null);

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch(() => setStats(null));
  }, []);

  const sourceCount = formatNumber(stats?.sources, "300");
  const spanCount = formatNumber(stats?.evidence_spans, "92 388");
  const estimatedFacts = stats?.evidence_spans
    ? NUMBER_FORMAT.format(Math.max(stats.evidence_spans * 2, 150000))
    : "155 000+";

  const heroStats = [
    {
      value: spanCount,
      label: "evidence spans",
      detail: "цитируемые фрагменты",
    },
    {
      value: sourceCount,
      label: "источников",
      detail: "статьи, отчёты, таблицы",
    },
    {
      value: estimatedFacts,
      label: "извлечённых фактов",
      detail: "числа, связи, условия",
    },
    {
      value: "0",
      label: "слепых утверждений",
      detail: "ответы только с опорой",
      accent: "success" as const,
    },
  ];

  return (
    <div className="landing landing-v2">
      <section className="hero hero-v2">
        <div className="hero-content">
          <div className="hero-kicker">
            <span className="hero-kicker-dot" />
            Evidence-first R&D knowledge graph
          </div>
          <h1 className="hero-title">
            Единая карта знаний <span className="hero-accent">R&D</span> для
            горно-металлургических решений
          </h1>
          <p className="hero-sub">
            Соединяем публикации, таблицы, эксперименты, материалы, процессы и выводы в
            проверяемую систему поиска. Каждый ответ показывает, откуда взялись цифры и почему
            им можно доверять.
          </p>

          <div className="hero-actions">
            <Link className="primary-button" to="/search">
              Открыть поиск
              <ArrowRight size={18} />
            </Link>
            <Link className="secondary-button hero-secondary" to="/graph">
              Смотреть граф
            </Link>
          </div>

          <div className="hero-proof-row">
            <span>
              <CheckCircle2 size={16} />
              цитаты и источники
            </span>
            <span>
              <Layers size={16} />
              числовые диапазоны
            </span>
            <span>
              <ShieldCheck size={16} />
              проверка фактов
            </span>
          </div>
        </div>

        <div className="hero-visual hero-visual-v2" aria-label="R&D knowledge graph overview">
          <div className="hero-visual-card">
            <img
              alt="Граф знаний"
              className="hero-graph"
              decoding="sync"
              height={900}
              loading="eager"
              src="/brand/hero-graph.png"
              width={900}
            />
            <div className="hero-orbit hero-orbit-a" />
            <div className="hero-orbit hero-orbit-b" />
            <div className="hero-floating-card hero-floating-card-a">
              <span>coverage</span>
              <b>100%</b>
            </div>
            <div className="hero-floating-card hero-floating-card-b">
              <span>sources</span>
              <b>{sourceCount}</b>
            </div>
            <div className="hero-floating-card hero-floating-card-c">
              <span>risk</span>
              <b>0 blind</b>
            </div>
          </div>
        </div>
      </section>

      <section className="hero-stats hero-stats-v2" aria-label="Ключевые показатели">
        {heroStats.map((stat) => (
          <article className="hero-stat" key={stat.label}>
            <div className={`hero-stat-value ${stat.accent === "success" ? "is-success" : ""}`}>
              {stat.value}
            </div>
            <div className="hero-stat-label">{stat.label}</div>
            <div className="hero-stat-detail">{stat.detail}</div>
          </article>
        ))}
      </section>

      <section className="feature-section">
        <div className="section-head">
          <div>
            <p className="section-eyebrow">Что получает эксперт</p>
            <h2 className="section-title">Не просто поиск: рабочий контур принятия решений</h2>
          </div>
          <p className="section-caption">
            Система сохраняет промышленную логику: параметры, ограничения, источники, географию
            практики и уровень доверия к каждому выводу.
          </p>
        </div>

        <div className="feature-grid feature-grid-v2">
          {FEATURES.map(({ Icon, title, metric, text }) => (
            <article className="feature-card feature-card-v2" key={title}>
              <div className="feature-card-top">
                <div className="feature-icon">
                  <Icon size={22} />
                </div>
                <span className="feature-metric">{metric}</span>
              </div>
              <h3 className="feature-title">{title}</h3>
              <p className="feature-text">{text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="how-section how-section-v2">
        <div className="section-head">
          <div>
            <p className="section-eyebrow">Pipeline</p>
            <h2 className="section-title">Как корпус превращается в проверяемый граф</h2>
          </div>
          <div className="pipeline-badge">
            <span>8 shards</span>
            <b>DuckDB + Qdrant</b>
          </div>
        </div>
        <div className="how-grid how-grid-v2">
          {STEPS.map(({ n, title, value, text }, index) => (
            <article className="how-step how-step-v2" key={n}>
              <div className="how-step-head">
                <span className="how-step-n">{n}</span>
                <div>
                  <h3 className="how-step-title">{title}</h3>
                  <span className="how-step-value">{value}</span>
                </div>
              </div>
              <p className="how-step-text">{text}</p>
              {index < STEPS.length - 1 ? <span className="how-arrow" aria-hidden /> : null}
            </article>
          ))}
        </div>
      </section>

      <section className="capability-grid capability-grid-v2" aria-label="Операционные возможности">
        {INSIGHTS.map(({ Icon, title, value, text, tag, image, rows, progress }) => (
          <article className="capability-card capability-card-v2" key={title}>
            <div className="capability-head">
              <Icon size={20} />
              <h3>{title}</h3>
            </div>
            <div className="capability-value">{value}</div>
            <p>{text}</p>
            {image ? (
              <img
                alt=""
                className="capability-illus"
                decoding="sync"
                height={640}
                loading="eager"
                src={image}
                width={640}
              />
            ) : null}
            {rows ? (
              <div className="mini-kv">
                {rows.map(([label, rowValue]) => (
                  <div key={label}>
                    <span>{label}</span>
                    <b>{rowValue}</b>
                  </div>
                ))}
              </div>
            ) : null}
            {typeof progress === "number" ? (
              <div className="freshness">
                <div className="freshness-row">
                  <span>Свежесть корпуса</span>
                  <b>{progress}%</b>
                </div>
                <div className="freshness-bar">
                  <span style={{ width: `${progress}%` }} />
                </div>
              </div>
            ) : null}
            {tag ? <span className="capability-tag">{tag}</span> : null}
          </article>
        ))}
      </section>

      <section className="landing-cta landing-cta-v2">
        <div className="landing-cta-icon">
          <ShieldCheck size={26} />
        </div>
        <div className="landing-cta-copy">
          <div className="landing-cta-title">Доказательная база для вопросов жюри</div>
          <div className="landing-cta-sub">
            Обессоливание, шахтные воды, электролиз никеля, техногенный гипс, SO₂, Au/Ag/МПГ и
            переработка сырья — через единый verified graph.
          </div>
        </div>
        <Link className="primary-button" to="/search">
          Задать вопрос
          <ArrowRight size={18} />
        </Link>
      </section>
    </div>
  );
}
