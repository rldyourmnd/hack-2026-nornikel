import {
  Archive,
  BarChart3,
  Database,
  Network,
  ShieldCheck,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

import { AnalysisWorkbench } from "@/widgets/analysis-workbench";

const nav: Array<[label: string, Icon: LucideIcon]> = [
  ["Анализ", Sparkles],
  ["Artifact bank", Archive],
  ["Граф", Network],
  ["Evaluation", BarChart3],
  ["Security", ShieldCheck],
];

export function WorkbenchPage() {
  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark">
          <div className="brand-symbol">
            <Database size={22} />
          </div>
          <div>
            <div className="brand-title">Nornikel Evidence Graph</div>
            <div className="brand-subtitle">Materials research workbench</div>
          </div>
        </div>
        <nav className="nav-list" aria-label="Основные разделы">
          {nav.map(([label, Icon], index) => (
            <div className={`nav-item ${index === 0 ? "active" : ""}`} key={label}>
              <Icon size={16} />
              {label}
            </div>
          ))}
        </nav>
      </aside>
      <section className="content">
        <div className="topbar">
          <div>
            <h1 className="page-title">Поиск по экспериментам, режимам и свойствам</h1>
            <p className="page-caption">
              Ответ строится как evidence packet: таблица экспериментов, точные EvidenceSpan,
              графовый путь, противоречия, пробелы и проверка неподдержанных claims.
            </p>
          </div>
          <div className="status-strip">
            <span className="status-pill">DuckDB evidence ledger</span>
            <span className="status-pill">CSV/Markdown ingest</span>
          </div>
        </div>
        <AnalysisWorkbench />
      </section>
    </main>
  );
}
