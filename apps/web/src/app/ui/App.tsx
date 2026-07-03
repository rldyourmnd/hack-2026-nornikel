import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";

import { AnalyticsPage } from "@/pages/analytics";
import { ComparePage } from "@/pages/compare";
import { DataPage } from "@/pages/data";
import { DemoPage } from "@/pages/demo";
import { EvalPage } from "@/pages/eval";
import { ExpertsPage } from "@/pages/experts";
import { GraphPage } from "@/pages/graph";
import { LandingPage } from "@/pages/landing";
import { SearchPage } from "@/pages/search";
import { SecurityPage } from "@/pages/security";
import { PageHero } from "@/shared/ui";
import { AppLayout } from "@/widgets/app-layout";

function HeroImage({ src }: { src: string }) {
  return <img alt="" className="page-hero-illus" src={src} />;
}

function GraphRoute() {
  return (
    <div className="page-wrap">
      <PageHero
        eyebrow="Интерактивный исследовательский граф"
        title="Граф знаний"
        caption="Материалы, процессы, оборудование, публикации и эксперты — каждая связь несёт ссылки на доказательства."
        aside={<HeroImage src="/brand/feat-path.png" />}
      />
      <GraphPage />
    </div>
  );
}

function DataRoute() {
  return (
    <div className="page-wrap">
      <PageHero
        eyebrow="Контроль корпуса"
        title="Данные и источники"
        caption="Загрузка PDF/DOCX/DOC/XLSX/CSV/MD и веб-страниц, статусы обработки, год и география, карантин без OCR."
        aside={<HeroImage src="/brand/feat-ingest.png" />}
      />
      <DataPage />
    </div>
  );
}

function AnalyticsRoute() {
  const navigate = useNavigate();
  return (
    <div className="page-wrap">
      <PageHero
        eyebrow="Управленческая аналитика"
        title="Пробелы и противоречия"
        caption="Матрица покрытия «материал × режим × свойство», история датированных решений и публикаций."
        aside={<HeroImage src="/brand/an-heatmap.png" />}
      />
      <AnalyticsPage
        onGapQuery={(question) => navigate(`/search?q=${encodeURIComponent(question)}`)}
      />
    </div>
  );
}

function EvalRoute() {
  return (
    <div className="page-wrap">
      <PageHero
        eyebrow="Качество ответов"
        title="Метрики верификации"
        caption="Покрытие цитатами, отсутствие сфабрикованных чисел, устойчивость к prompt-инъекциям, утечки меток."
        aside={<HeroImage src="/brand/an-quality.png" />}
      />
      <EvalPage />
    </div>
  );
}

function SecurityRoute() {
  return (
    <div className="page-wrap">
      <PageHero
        eyebrow="Доверие и прозрачность"
        title="Безопасность и аудит"
        caption="Метки доступа источников, контур защиты от инъекций, журнал ответов с результатами верификации."
        aside={<HeroImage src="/brand/feat-security.png" />}
      />
      <SecurityPage />
    </div>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<LandingPage />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="graph" element={<GraphRoute />} />
          <Route path="data" element={<DataRoute />} />
          <Route path="analytics" element={<AnalyticsRoute />} />
          <Route path="compare" element={<ComparePage />} />
          <Route path="experts" element={<ExpertsPage />} />
          <Route path="eval" element={<EvalRoute />} />
          <Route path="security" element={<SecurityRoute />} />
          <Route path="demo" element={<DemoPage />} />
          <Route path="*" element={<Navigate replace to="/" />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
