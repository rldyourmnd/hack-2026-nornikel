import {
  BarChart3,
  Database,
  Gauge,
  GitCompareArrows,
  Network,
  Sparkles,
  Users,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  to: string;
  label: string;
  Icon: LucideIcon;
};

// Primary product navigation, shared by the header and mobile menu. The logo
// links to the landing page (`/`); these are the working sections.
export const NAV_ITEMS: NavItem[] = [
  { to: "/search", label: "Поиск", Icon: Sparkles },
  { to: "/graph", label: "Граф знаний", Icon: Network },
  { to: "/data", label: "Данные", Icon: Database },
  { to: "/analytics", label: "Аналитика", Icon: BarChart3 },
  { to: "/compare", label: "Сравнение", Icon: GitCompareArrows },
  { to: "/experts", label: "Эксперты", Icon: Users },
  { to: "/eval", label: "Качество", Icon: Gauge },
];

// Canonical entity-type → color (matches the graph nodes and CSS tokens).
export const ENTITY_COLORS: Record<string, string> = {
  material: "var(--entity-material)",
  process: "var(--entity-process)",
  regime: "var(--entity-process)",
  condition: "var(--entity-process)",
  property: "var(--entity-experiment)",
  equipment: "var(--entity-equipment)",
  facility: "var(--entity-equipment)",
  experiment: "var(--entity-experiment)",
  publication: "var(--entity-publication)",
  person: "var(--entity-expert)",
  expert: "var(--entity-expert)",
  team: "var(--entity-expert)",
  laboratory: "var(--entity-expert)",
  organization: "var(--entity-expert)",
  conclusion: "var(--entity-conclusion)",
  value: "var(--entity-conclusion)",
};

export function entityColor(entityType: string): string {
  return ENTITY_COLORS[entityType] ?? "var(--color-text-muted)";
}
