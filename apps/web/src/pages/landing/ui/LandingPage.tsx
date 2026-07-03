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

const FEATURES = [
  {
    Icon: Search,
    title: "Многопараметрический поиск",
    text: "Поиск по материалам, процессам, условиям, географии и времени. Поддержка числовых диапазонов и ограничений.",
  },
  {
    Icon: ShieldCheck,
    title: "Верификация знаний",
    text: "Каждый факт — с источником, уровнем достоверности и датой актуализации. Никаких неподтверждённых утверждений.",
  },
  {
    Icon: Share2,
    title: "Граф знаний",
    text: "Связи между сущностями, экспериментами и выводами. Прозрачная структура и объяснимые ответы.",
  },
  {
    Icon: AlertTriangle,
    title: "Пробелы и противоречия",
    text: "Система выявляет пробелы в знаниях и противоречия между источниками — чтобы вы не принимали рискованных решений.",
  },
];

const STEPS = [
  {
    n: 1,
    title: "Загрузка корпуса",
    text: "Загружаем публикации, патенты, отчёты и данные экспериментов из разных источников.",
  },
  {
    n: 2,
    title: "Извлечение фактов",
    text: "Нейромодели извлекают факты: сущности, числа, условия, связи и источники.",
  },
  {
    n: 3,
    title: "Ответ с доказательствами",
    text: "Система отвечает на вопросы с цитатами и таблицами. Каждое число — с подтверждением.",
  },
];

export function LandingPage() {
  const [stats, setStats] = useState<StatsOverview | null>(null);

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch(() => setStats(null));
  }, []);

  const heroStats = [
    { Icon: Layers, value: stats ? stats.evidence_spans.toLocaleString("ru-RU") : "—", label: "evidence spans" },
    { Icon: null, value: stats ? String(stats.sources) : "—", label: "источников" },
    {
      Icon: CheckCircle2,
      value: "0",
      label: "неподтверждённых чисел",
      accent: "success" as const,
    },
    { Icon: Globe, value: "RU / зарубеж", label: "география практики" },
  ];

  return (
    <div className="landing">
      <section className="hero">
        <div className="hero-content">
          <h1 className="hero-title">
            Единая карта знаний <span className="hero-accent">R&D</span> для
            горно-металлургической отрасли
          </h1>
          <p className="hero-sub">
            Соединяем статьи, эксперименты, материалы, процессы, оборудование, экспертов и выводы —
            чтобы каждое решение опиралось на доказательства.
          </p>
          <div className="hero-actions">
            <Link className="primary-button" to="/demo">
              Смотреть демо <ArrowRight size={16} />
            </Link>
            <Link className="secondary-button" to="/search">
              Как это работает
            </Link>
          </div>
          <div className="hero-pill">
            <img alt="" className="hero-pill-mascot" src="/brand/mascot.png" />
            Не чирикаем без источника
          </div>
        </div>
        <div className="hero-visual">
          <img alt="Граф знаний" className="hero-graph" src="/brand/hero-graph.png" />
        </div>
      </section>

      <section className="hero-stats">
        {heroStats.map((stat, index) => (
          <div className="hero-stat" key={index}>
            <div className={`hero-stat-value ${stat.accent === "success" ? "is-success" : ""}`}>
              {stat.value}
            </div>
            <div className="hero-stat-label">{stat.label}</div>
          </div>
        ))}
      </section>

      <section className="feature-grid">
        {FEATURES.map(({ Icon, title, text }) => (
          <article className="feature-card" key={title}>
            <div className="feature-icon">
              <Icon size={22} />
            </div>
            <h3 className="feature-title">{title}</h3>
            <p className="feature-text">{text}</p>
          </article>
        ))}
      </section>

      <section className="how-section">
        <h2 className="section-title">Как это работает</h2>
        <div className="how-grid">
          {STEPS.map(({ n, title, text }, index) => (
            <div className="how-step" key={n}>
              <div className="how-step-head">
                <span className="how-step-n">{n}</span>
                <h3 className="how-step-title">{title}</h3>
              </div>
              <p className="how-step-text">{text}</p>
              {index < STEPS.length - 1 ? <span className="how-arrow" aria-hidden>→</span> : null}
            </div>
          ))}
        </div>
      </section>

      <section className="capability-grid">
        <article className="capability-card">
          <div className="capability-head">
            <Globe size={20} />
            <h3>География</h3>
          </div>
          <p>Фильтруйте результаты по странам, регионам и типам практики.</p>
          <img alt="" className="capability-illus" src="/brand/an-geo.png" />
          <span className="capability-tag">Россия и зарубежная практика</span>
        </article>

        <article className="capability-card">
          <div className="capability-head">
            <Layers size={20} />
            <h3>Диапазоны и условия</h3>
          </div>
          <p>Учитываем концентрации, температуры, давления и скорости потока.</p>
          <div className="mini-kv">
            <div><span>Температура</span><b>200 – 600 °C</b></div>
            <div><span>Концентрация</span><b>0.1 – 100 г/л</b></div>
            <div><span>Скорость потока</span><b>0.5 – 5 м/с</b></div>
          </div>
        </article>

        <article className="capability-card">
          <div className="capability-head">
            <Users size={20} />
            <h3>Команды и эксперты</h3>
          </div>
          <p>Распределяйте экспертизу, назначайте ревью и ведите историю решений.</p>
          <span className="capability-tag">Ролевая экспертиза и ревью</span>
        </article>

        <article className="capability-card">
          <div className="capability-head">
            <CalendarClock size={20} />
            <h3>Актуализация знаний</h3>
          </div>
          <p>Отслеживаем свежесть источников и предлагаем обновления.</p>
          <div className="freshness">
            <div className="freshness-row">
              <span>Свежесть корпуса</span>
              <b>92%</b>
            </div>
            <div className="freshness-bar">
              <span style={{ width: "92%" }} />
            </div>
          </div>
        </article>
      </section>
    </div>
  );
}
