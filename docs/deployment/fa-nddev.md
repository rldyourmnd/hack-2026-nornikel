# fa.nddev.asia Deployment Notes (HISTORICAL)

> **Status (2026-07-03): legacy stand.** It still answers with an old
> pre-Yandex build but is NOT deployed to anymore. The production stand is
> https://изи-никель.рф (mirror https://nornikel.nddev.asia) — see
> `nornikel-nddev.md`. Kept for the historical record only.

Target host:

```text
ssh server-nddev
public URL: https://fa.nddev.asia
```

The repository is prepared for container deployment with Docker Compose:

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
```

Required runtime values stay outside git:

- `OPENAI_API_KEY`
- `LITELLM_API_BASE`, when using a non-default OpenAI-compatible gateway
- any future OCR service credentials

Current Compose services:

- `web`: Nginx serving the React build and proxying `/api/` to FastAPI.
- `api`: FastAPI application.
- `qdrant`: vector database placeholder for the retrieval adapter.
- `POST /api/sources/upload` is limited by FastAPI `MAX_SOURCE_UPLOAD_BYTES` and by
  Nginx `client_max_body_size`. The bundled web Nginx config sets `client_max_body_size 6m`
  for the default 5 MiB source limit plus multipart overhead.

For the shared `fa.nddev.asia` server, use a server-only Compose override stored on
the host as `/home/ubuntu/nornikel-kg-search/docker-compose.server.yml`:

- `web` publishes only `127.0.0.1:8513:80`.
- `api` is exposed only inside the Compose network and sets `PROJECT_ROOT=/app`.
- `qdrant` is not published to the host.
- `/home/ubuntu/nornikel-kg-search/data` is bind-mounted for the DuckDB runtime ledger.

TLS is terminated by the host-level Nginx virtual host
`/etc/nginx/conf.d/fa-nddev-asia.conf`. The vhost uses the existing Let's Encrypt
certificate at `/etc/letsencrypt/live/fa.nddev.asia/` and proxies all HTTPS traffic
to `http://127.0.0.1:8513`. Keep its `client_max_body_size` at least as large as the
container Nginx value, otherwise uploads can be rejected before they reach FastAPI.

Before rollout, verify:

```bash
docker compose config
docker compose up --build -d
curl -fsS http://127.0.0.1:5173/
curl -fsS http://127.0.0.1:8000/health
```

On the `fa.nddev.asia` host, verify:

```bash
cd /home/ubuntu/nornikel-kg-search
docker compose -f docker-compose.server.yml ps
curl -fsS http://127.0.0.1:8513/api/health
curl -fsS -X POST http://127.0.0.1:8513/api/qa/ask \
  -H 'Content-Type: application/json' \
  --data '{"question":"Что делали по Ni-30Cu при старении 700 C 8 ч?"}'
sudo nginx -t
curl -I https://fa.nddev.asia
```
