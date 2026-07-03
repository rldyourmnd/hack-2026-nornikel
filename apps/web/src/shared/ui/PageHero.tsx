import type { ReactNode } from "react";

type PageHeroProps = {
  eyebrow?: string;
  title: string;
  caption?: string;
  actions?: ReactNode;
  aside?: ReactNode;
};

export function PageHero({ eyebrow, title, caption, actions, aside }: PageHeroProps) {
  return (
    <section className="page-hero">
      <div className="page-hero-main">
        {eyebrow ? <div className="page-hero-eyebrow">{eyebrow}</div> : null}
        <h1 className="page-hero-title">{title}</h1>
        {caption ? <p className="page-hero-caption">{caption}</p> : null}
        {actions ? <div className="page-hero-actions">{actions}</div> : null}
      </div>
      {aside ? <div className="page-hero-aside">{aside}</div> : null}
    </section>
  );
}
