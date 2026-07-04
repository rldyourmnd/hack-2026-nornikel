import { useEffect, useState } from "react";

import { analyzeGaps, type GapsAnalysis } from "@/shared/api";
import { Panel } from "@/shared/ui";

type GapsBoardProps = {
  onGapQuery: (query: string) => void;
};

export function GapsBoard({ onGapQuery }: GapsBoardProps) {
  const [analysis, setAnalysis] = useState<GapsAnalysis | null>(null);
  const [material, setMaterial] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const result = await analyzeGaps();
        setAnalysis(result);
        if (result.materials.length > 0) {
          setMaterial(result.materials[0]);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Не удалось получить пробелы");
      }
    })();
  }, []);

  if (error) {
    return (
      <Panel title="Пробелы в данных">
        <div className="inline-error">{error}</div>
      </Panel>
    );
  }
  if (!analysis) {
    return (
      <Panel title="Пробелы в данных">
        <div className="status-pill">Загрузка матрицы покрытия…</div>
      </Panel>
    );
  }

  const cells = analysis.cells.filter((cell) => cell.material_name === material);
  const regimes = [...new Set(cells.map((cell) => cell.regime_name))];
  const properties = [...new Set(cells.map((cell) => cell.property_name))];

  return (
    <Panel title="Пробелы в данных">
      <div className="gaps-header">
        <select
          className="gaps-select"
          onChange={(event) => setMaterial(event.target.value)}
          value={material}
        >
          {analysis.materials.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <span className="source-meta">
          покрыто {analysis.covered_count} · пробелов {analysis.gap_count}
        </span>
      </div>
      <div className="gaps-matrix-wrap">
        <table className="gaps-matrix">
          <thead>
            <tr>
              <th>Режим \ Свойство</th>
              {properties.map((property) => (
                <th key={property}>{property}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {regimes.map((regime) => (
              <tr key={regime}>
                <td>{regime}</td>
                {properties.map((property) => {
                  const cell = cells.find(
                    (item) => item.regime_name === regime && item.property_name === property,
                  );
                  if (!cell) return <td key={property}>—</td>;
                  return (
                    <td key={property}>
                      {cell.covered ? (
                        <span className="gap-cell covered" title={cell.experiment_ids.join(", ")}>
                          ✓
                        </span>
                      ) : (
                        <button
                          className="gap-cell gap"
                          onClick={() =>
                            onGapQuery(
                              `Что известно про ${cell.property_name} для ${cell.material_name} после ${cell.regime_name}?`,
                            )
                          }
                          title="Нет данных — запустить вопрос"
                          type="button"
                        >
                          ∅
                        </button>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
