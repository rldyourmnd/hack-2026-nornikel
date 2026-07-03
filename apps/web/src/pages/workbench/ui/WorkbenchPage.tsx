import {
  BarChart3,
  Database,
  Gauge,
  Network,
  ShieldCheck,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";

import { AnalyticsPage } from "@/pages/analytics";
import { DataPage } from "@/pages/data";
import { EvalPage } from "@/pages/eval";
import { GraphPage } from "@/pages/graph";
import { SecurityPage } from "@/pages/security";
import { AnalysisWorkbench } from "@/widgets/analysis-workbench";

type PageKey = "search" | "graph" | "data" | "analytics" | "eval" | "security";

const NAV: Array<{ key: PageKey; label: string; Icon: LucideIcon }> = [
  { key: "search", label: "Поиск", Icon: Sparkles },
  { key: "graph", label: "Граф знаний", Icon: Network },
  { key: "data", label: "Данные", Icon: Database },
  { key: "analytics", label: "Аналитика", Icon: BarChart3 },
  { key: "eval", label: "Качество", Icon: Gauge },
  { key: "security", label: "Безопасность", Icon: ShieldCheck },
];

const HEADERS: Record<PageKey, { title: string; caption: string }> = {
  search: {
    title: "Поиск по экспериментам, режимам и свойствам",
    caption:
      "Ответ строится как evidence packet: таблица экспериментов, точные EvidenceSpan, " +
      "графовый путь, противоречия и проверка каждого предложения.",
  },
  graph: {
    title: "Граф знаний",
    caption:
      "Материалы, процессы, оборудование, публикации и эксперты — каждая связь несёт " +
      "ссылки на доказательства в документах.",
  },
  data: {
    title: "Данные и источники",
    caption:
      "Загрузка PDF/DOCX/DOC/XLSX/CSV/MD и веб-страниц, статусы обработки, год и география, " +
      "карантин для сканов без текстового слоя.",
  },
  analytics: {
    title: "Аналитика знаний",
    caption:
      "Матрица пробелов «материал × режим × свойство», история датированных решений и " +
      "публикаций.",
  },
  eval: {
    title: "Качество ответов",
    caption:
      "Автоматическая оценка: покрытие цитатами, отсутствие сфабрикованных чисел, " +
      "устойчивость к prompt-инъекциям, утечки меток доступа.",
  },
  security: {
    title: "Безопасность и аудит",
    caption:
      "Метки доступа источников, контур защиты от инъекций, журнал ответов с результатами " +
      "верификации.",
  },
};

export function WorkbenchPage() {
  const [page, setPage] = useState<PageKey>("search");
  const [injectedQuestion, setInjectedQuestion] = useState<string | null>(null);

  function openSearchWith(question: string) {
    setInjectedQuestion(question);
    setPage("search");
  }

  const header = HEADERS[page];
  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark">
          <div className="brand-symbol">
            <Database size={22} />
          </div>
          <div>
            <div className="brand-title">Научный клубок</div>
            <div className="brand-subtitle">R&D knowledge graph · Норникель</div>
          </div>
        </div>
        <nav className="nav-list" aria-label="Основные разделы">
          {NAV.map(({ key, label, Icon }) => (
            <button
              className={`nav-item ${page === key ? "active" : ""}`}
              key={key}
              onClick={() => setPage(key)}
              type="button"
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="status-pill">Yandex AI Studio · aliceai-llm</span>
          <span className="status-pill">DuckDB + Qdrant hybrid</span>
        </div>
      </aside>
      <section className="content">
        <div className="topbar">
          <div>
            <h1 className="page-title">{header.title}</h1>
            <p className="page-caption">{header.caption}</p>
          </div>
        </div>
        {page === "search" ? (
          <AnalysisWorkbench injectedQuestion={injectedQuestion} />
        ) : null}
        {page === "graph" ? <GraphPage /> : null}
        {page === "data" ? <DataPage /> : null}
        {page === "analytics" ? <AnalyticsPage onGapQuery={openSearchWith} /> : null}
        {page === "eval" ? <EvalPage /> : null}
        {page === "security" ? <SecurityPage /> : null}
      </section>
    </main>
  );
}
