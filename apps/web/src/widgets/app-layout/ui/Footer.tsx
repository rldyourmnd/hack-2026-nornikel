import { ArrowRight, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-cta">
        <div className="footer-cta-icon">
          <ShieldCheck size={26} />
        </div>
        <div className="footer-cta-text">
          <div className="footer-cta-title">Доказательная база для уверенных решений</div>
          <div className="footer-cta-sub">
            Снижаем риски. Ускоряем R&D. Создаём ценность на основе знаний.
          </div>
        </div>
        <Link className="primary-button footer-cta-button" to="/search">
          Открыть поиск <ArrowRight size={16} />
        </Link>
      </div>
      <div className="footer-meta">
        <span>Научный клубок · Команда Попугайчики</span>
        <span className="footer-tagline">Повторяем не слухи, а источники ✨</span>
      </div>
    </footer>
  );
}
