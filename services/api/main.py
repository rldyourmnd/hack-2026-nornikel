from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.routes import entities, evals, gaps, graph, health, query, sources, stats

# Application INFO logs (reindex completion markers, semantic merges, ingest
# progress) must reach docker logs — uvicorn configures only its own loggers.
logging.getLogger("nornikel_kg").setLevel(logging.INFO)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)


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
    app.include_router(stats.router)
    return app


app = create_app()
