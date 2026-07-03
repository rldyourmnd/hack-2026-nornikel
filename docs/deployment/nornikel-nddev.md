# Primary Stand Deployment Notes

Target host:

```text
ssh curestry            # 165.22.203.232, 8 vCPU / 31 GiB
primary:  https://изи-никель.рф  (punycode: xn----jtbedbbojo8m.xn--p1ai)
mirror:   https://nornikel.nddev.asia  (secondary, kept alive)
```

DNS prerequisite for the primary domain: an A record for
`изи-никель.рф` and `www` pointing at `165.22.203.232`; the acme
companion issues the certificate automatically once the name resolves.

## Auto-deploy (GitHub Actions)

Every push to `main` runs `.github/workflows/deploy.yml`: ships the
tracked tree over SSH, rebuilds `api`/`web`, restarts the stack and
smoke-checks `/api/health` + `/api/stats/overview`. Repo secrets:
`DEPLOY_SSH_KEY` (dedicated ed25519 deploy key), `DEPLOY_HOST`,
`DEPLOY_USER`. Manual run: the workflow_dispatch button.

Three isolated Docker Compose projects run on the host:

| Project | Path | Purpose |
| --- | --- | --- |
| `nornikel-kg-search` | `/srv/nornikel-kg-search` | api + web + qdrant (this repo) |
| `langfuse` | `/srv/langfuse` | self-hosted Langfuse v3 (observability) |
| `curestry` | `/root/curestry_rca/platform` | unrelated production — do not touch |

## Topology

- TLS terminates at the host-wide `curestry-nginx-1` (nginx-proxy + acme-companion).
  The `web` container joins the external `curestry_frontend` network and publishes
  itself via `VIRTUAL_HOST=nornikel.nddev.asia` + `LETSENCRYPT_HOST`; certificates
  renew automatically.
- Per-vhost upload limit lives in the `curestry_nginx_vhost` volume
  (`client_max_body_size 30m`); the bundled web nginx allows 300s proxy timeouts
  for Docling ingest.
- `api` and `qdrant` are internal-only. `api` also joins the external `lf-net`
  network to reach `langfuse-web:3000`.
- Port `127.0.0.1:8080` is a host-local fallback to the web container.

## Server files not in git

- `/srv/nornikel-kg-search/docker-compose.server.yml` — compose override
  (networks, restart policies, pinned `qdrant/qdrant:v1.16.3`).
- `/srv/nornikel-kg-search/.env` — env matrix from `.env.example` with real
  values (dataeyes key, Langfuse keys, `EMBEDDING_BACKEND=local`).
- `/srv/langfuse/.env` — Langfuse stack secrets (never in git).

## Deploy procedure

```bash
git archive main | ssh curestry 'tar -x -C /srv/nornikel-kg-search'
ssh curestry 'cd /srv/nornikel-kg-search \
  && docker compose -f docker-compose.server.yml build api web \
  && docker compose -f docker-compose.server.yml up -d'
# vector reindex goes THROUGH the api (it owns the DuckDB lock):
curl -fsS -X POST https://nornikel.nddev.asia/api/sources/reindex-all
```

## DuckDB lock contract (important)

The api process holds one persistent DuckDB write connection for its whole
lifetime. Anything that opens `data/catalog.duckdb` directly (batch ingester,
`run_eval.py --store`, ad-hoc DuckDB shells) is mutually exclusive with a
running api — stop the api container for that window:

```bash
ssh curestry 'cd /srv/nornikel-kg-search \
  && docker compose -f docker-compose.server.yml stop api \
  && docker compose -f docker-compose.server.yml run --rm --no-deps -T api \
       python scripts/ingest_corpus.py --dir data/corpus --max-mb 25 \
  && docker compose -f docker-compose.server.yml up -d'
```

The batch ingester expands archives first (.zip, multipart .zip.001/.002,
.rar via bsdtar) and handles .pdf/.docx/.docm/.doc/.xlsx/.xls/.csv/.md/.txt;
images are counted as no-OCR skips.

Smoke:

```bash
curl -fsS https://nornikel.nddev.asia/api/health
curl -fsS -X POST https://nornikel.nddev.asia/api/qa/ask \
  -H 'Content-Type: application/json' \
  --data '{"question":"Что делали по Ni-30Cu при старении 700 C 8 ч?"}'
curl -fsS https://nornikel.nddev.asia/api/gaps/analyze | head -c 200
curl -fsS https://nornikel.nddev.asia/api/eval/summary | head -c 200
```

## Backups

`/root/backup-nornikel.sh` (cron, nightly 03:30) tars the DuckDB ledger,
`data/artifacts`, and a Qdrant snapshot into `/root/backups/nornikel/`,
keeping the last 7 archives. Restore drill: untar into
`/srv/nornikel-kg-search/data` and `docker compose ... up -d`.

## Interim mirror

`https://fa.nddev.asia` (host `server-nddev`) keeps the previous deterministic
build until the final freeze; see `docs/deployment/fa-nddev.md`.
