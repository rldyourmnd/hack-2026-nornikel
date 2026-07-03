from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.routes import entities, evals, gaps, graph, health, query, sources


def create_app() -> FastAPI:
    app = FastAPI(
        title="Nornikel Materials KG Search API",
        version="0.1.0",
        description="Evidence-first materials KG and hybrid retrieval MVP API.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(query.router)
    app.include_router(sources.router)
    app.include_router(graph.router)
    app.include_router(entities.router)
    app.include_router(gaps.router)
    app.include_router(evals.router)
    return app


app = create_app()
