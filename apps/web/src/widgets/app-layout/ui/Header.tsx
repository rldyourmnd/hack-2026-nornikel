import { Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Link } from "react-router-dom";

import { fetchHealth, type HealthStatus } from "@/shared/api";
import { NAV_ITEMS } from "@/shared/config/nav";

export function Header() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  const runtimeLabel = health
    ? health.llm_enabled && health.llm_configured
      ? "LLM-профиль включён"
      : "детерминированный режим"
    : "статус недоступен";

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <Link className="brand" to="/" onClick={() => setOpen(false)}>
          <img alt="Научный клубок" className="brand-logo" src="/brand/logo.png" />
          <span className="brand-name">Научный клубок</span>
        </Link>
        <span className="team-badge">R&D Knowledge Graph</span>

        <nav className={`site-nav ${open ? "open" : ""}`} aria-label="Разделы">
          {NAV_ITEMS.map(({ to, label, Icon }) => (
            <NavLink
              className={({ isActive }) => `site-nav-link ${isActive ? "active" : ""}`}
              key={to}
              to={to}
              onClick={() => setOpen(false)}
            >
              <Icon size={15} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="header-right">
          <span className="hackathon-badge" title={`Runtime: ${runtimeLabel}`}>
            Норникель Hackathon
          </span>
          <button
            aria-label="Меню"
            className="menu-toggle"
            onClick={() => setOpen((value) => !value)}
            type="button"
          >
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>
    </header>
  );
}
