import { useSearchParams } from "react-router-dom";

import { PageHero } from "@/shared/ui";
import { AnalysisWorkbench } from "@/widgets/analysis-workbench";

export function SearchPage() {
  const [searchParams] = useSearchParams();
  const injectedQuestion = searchParams.get("q");

  return (
    <div className="page-wrap">
      <PageHero
        eyebrow="Многопараметрический поиск"
        title="Поиск по материалам, процессам и условиям"
        caption={
          "Естественный вопрос + структурные фильтры. Ответ собирается как evidence packet: " +
          "релевантные источники, точные EvidenceSpan и проверка каждого предложения."
        }
      />
      <AnalysisWorkbench injectedQuestion={injectedQuestion} />
    </div>
  );
}
