import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

import { PageHero, Panel } from "@/shared/ui";

export function ComparePage() {
  return (
    <div className="page-wrap">
      <PageHero
        eyebrow="Сравнительный анализ"
        title="Сравнение технологий"
        caption="Сопоставление вариантов по эффективности, CAPEX/OPEX, климату и ограничениям — каждая ячейка с источником."
      />
      <Panel title="Как построить сравнение">
        <p className="muted-note">
          Сравнение технологий строится из фактов корпуса: каждая ячейка ссылается на источник или
          помечается как «нет данных». Задайте сравнительный вопрос в поиске — система соберёт
          таблицу с показателями и evidence.
        </p>
        <Link className="secondary-button" to="/search?q=Сравни технологии обеднения шлака по потерям металлов">
          Собрать сравнение в поиске <ArrowRight size={15} />
        </Link>
      </Panel>
    </div>
  );
}
