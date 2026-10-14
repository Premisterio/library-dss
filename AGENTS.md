# AGENTS.md

Guide for AI coding agents (and humans) working on **library-dss**: a decision support system (DSS) for an online library, the author's master's thesis. It grows out of the author's earlier analytics app [Premisterio/Diploma](https://github.com/Premisterio/Diploma), which is frozen.

Read in this order:

1. `HANDOFF.md` if it exists (local, gitignored): the live session state, uncommitted work and next steps. Update it before you finish.
2. This file: process rules, stack, commands.
3. [DESIGN.md](DESIGN.md): how each part of the app works and the rules it follows. Read the section of every part you change.

## Hard rules

1. **Never commit or push without the user's explicit approval** of the changes. Prepare the change, summarize it, wait for "ok". Push only when asked.
2. **The backend is a UI-agnostic platform.** All logic, metrics, sorting and explanations live in the backend. The frontend only renders and computes no metrics. The `/api/v1` contract only changes additively; breaking changes need a new version.
3. **`backend/app/domain` is pure:** no web or database imports, so the thesis experiment harness can use it directly (DESIGN.md §2.1).
4. **Ground truth from the simulator never enters the app database.** Only the experiment harness reads `ground_truth.json`.
5. **Newest stack policy:** stay on the latest stable versions (see Stack). Before downgrading anything, check compatibility and ask the user.
6. **Data licenses:**
   - Open Library: CC0.
   - goodbooks-10k: CC BY-SA 4.0. Never commit its raw data. Only aggregate calibration parameters may be committed, with attribution.
7. **Languages:** the UI is Ukrainian (enum labels, user-facing messages such as `message_uk`). Everything else is English: code, comments, docs, READMEs, commit messages, PRs.
8. **No Russian-language content** anywhere: data, catalogue, UI, fixtures or examples.
9. **Rules and design live in DESIGN.md, not in code comments.** Comments explain only code that is not obvious. When a change alters how a part works, update its DESIGN.md section in the same change.
10. **Names describe what things are, not project history:** no "v1/v2", "bachelor", "old/new" labels in identifiers, files, messages or docs. Real version fields and paths stay (`/api/v1`, a file's `schema_version`).

## Stack

| Area       | Tools                                                                                                                                                                           |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Python     | 3.15, uv workspace (`backend`, `generator`), ruff, ty, pytest, httpx2 (TestClient)                                                                                              |
| Backend    | FastAPI, SQLAlchemy 2.1 (typed), Alembic, psycopg 3, PostgreSQL 18, Typer CLI `dss`, Scalar docs                                                                                |
| Frontend   | TypeScript 7, React 19, Vite 8, Tailwind 4, shadcn/ui (radix, Nova preset), TanStack Query, Vitest                                                                              |
| JS tooling | **oxlint** (type-aware via `oxlint-tsgolint`) + **oxfmt**. Not ESLint/Prettier: `typescript-eslint` does not support TS 7                                                       |
| API client | `packages/api-client`: types generated from OpenAPI by `tools/api-codegen`, which is isolated on TS 5.9 because TS 7 has no JS compiler API. Never edit `src/schema.ts` by hand |
| Infra      | Docker (multi-stage, non-root prod), docker compose (dev), GitHub Actions (SHA-pinned), Dependabot (7-day cooldown), prek hooks                                                 |

## Commands

```bash
# setup
uv sync --all-packages          # Python 3.15 venv (.venv)
npm ci                          # JS workspaces
uv run prek install             # git hooks (ruff, oxfmt, oxlint)

# run
docker compose up -d            # PostgreSQL 18 (:5433) + API (:8000, migrations on start, reload) + worker
npm run dev                     # frontend :5173, proxies /api → :8000

# checks (same as CI)
uv run ruff check . && uv run ruff format --check . && uv run ty check backend generator
(cd backend && uv run pytest)   # uses database dss_test on the compose server (created on first run)
(cd generator && uv run pytest)
npm run format:check && npm run typecheck && npm run lint && npm run test && npm run build

# new migration (numbered automatically, see DESIGN.md §2.7)
(cd backend && uv run alembic revision --autogenerate -m "what changed")

# API contract changed → regenerate and commit both files (CI fails on drift)
uv run dss openapi --out packages/api-client/openapi.json
npm run api:generate

# simulator (see docs/simulation.md)
uv run libsim generate --preset demo --seed 1   # → data/generated/<id>.json.gz + ground truth
uv run libsim validate data/generated/<id>.json.gz
uv run libsim schema --out docs/schema/dataset.schema.json   # after changing libsim/schema.py
```

## Conventions

Short rules; the reasons and details are in DESIGN.md.

- **Errors:** raise `ApiError(status, "area.reason", detail)`; clients rely on the stable `code` (§2.2).
- **API responses:** raw numbers with units, ISO 8601 UTC timestamps, enum codes with labels from `meta/enums`, lists as `{items, total, limit, offset}`; another analyst's resource answers 404 (§2.3).
- **Long operations** are jobs with a registered handler and progress reports (§2.6).
- **Time:** UTC everywhere through `app.utils.dates`; never `datetime.now()` (§2.8). Domain code uses the dataset's `as_of` (§2.9).
- **Migrations** are numbered `0001`, `0002`, … in one chain, one file per revision named `NNNN_<slug>.py`. Create them with `alembic revision --autogenerate -m "…"` (it assigns the number) and review the generated code. Never edit a migration that has reached `main`; add a new one (§2.7).
- **Settings** come only from environment variables; `SECRET_KEY` has no default (§2.2).
- **Tests:** every bug fix gets a regression test; pytest treats warnings as errors; backend tests run against PostgreSQL in rolled-back transactions (§2.11).
- **Simulator:** planted effects live in `libsim/params.py`; after changing the model, rerun `libsim validate` and update `docs/simulation.md` (§3).
- **Frontend:** data only via TanStack Query + `api-client`; oxfmt style; shadcn components in `frontend/src/components/ui` (§4).

## Roadmap

| Milestone | Scope                                                                                                                                    | Status            |
| --------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| M0        | Monorepo, tooling, skeletons, dev compose, CI                                                                                            | done (2026-10-14) |
| M1        | `libsim`: real catalogue (Open Library + goodbooks-10k calibration), daily simulation with planted effects, ground truth, dataset schema | done (2026-10-14) |
| M2        | Backend platform: auth, jobs + worker, dataset import, analytics, exports, CLI, demo seed                                                | in progress       |
| M3        | Thin shadcn frontend (datasets, overview, analytics, reports) + VPS deploy                                                               | —                 |
| M4a       | Churn prediction (no leakage), explanations                                                                                              | —                 |
| M4b       | Uplift from the randomized campaign, MILP action plan, what-if, decision log                                                             | —                 |
| M5        | Content acquisition MCDA: AHP, TOPSIS/SAW, sensitivity, budget portfolio                                                                 | —                 |
| M6        | Thesis experiment harness (seeds × presets × budgets vs baselines)                                                                       | —                 |
| M7        | E2E tests, backup drill, user docs, first release                                                                                        | —                 |

## Decision log

Newest first. Add an entry for every decision that changes scope, stack or rules.

- **2026-10-14 — Documentation, naming and language.**
  - `DESIGN.md` documents every part of the app (how it works, its rules, why); code comments no longer state rules.
  - Names describe what things are, not project history: no "v1/v2" or "bachelor" in identifiers, files, messages or docs. Datasets expose `format` (`tabular` | `nested`) instead of an arbitrary version number.
  - All documentation is in English; only the UI is Ukrainian.
- **2026-10-14 — Migration names and shared helpers.**
  - Alembic revisions are numbered (`0001_initial_schema.py`, revision `"0001"`) instead of random hashes: readable order and `down_revision`. `migrations/env.py` assigns the number.
  - `app/utils/` holds pure helpers shared by several layers; the first one is `dates.py`.
- **2026-10-14 — Background jobs and dataset import.**
  - Queue = the `jobs` table; the worker claims jobs with `SELECT … FOR UPDATE SKIP LOCKED` (no Redis/Celery). Jobs abandoned by a stopped worker are failed after `JOB_STALE_SECONDS` without a heartbeat.
  - Live progress via FastAPI's native SSE (`EventSourceResponse`), bounded to 10 minutes per stream; clients reconnect.
  - Uploads are stored gzip-compressed in PostgreSQL (`dataset_files`), so one `pg_dump` backs up everything; duplicates are detected by the SHA-256 of the uncompressed JSON (per analyst).
  - Import = orjson → Polars frames → bulk validation (all problems reported at once, up to 20) → COPY, in one transaction. Measured on the 5k × 24-month demo: ~8 s, worker peak ~280 MiB.
  - Two file formats, named by structure: `tabular` (libsim) and `nested` (one object per user, the format of the earlier app). Nested files import with `capabilities=["descriptive"]`; their unmapped fields go to `lib_users.extra`.
- **2026-10-14 — Backend analytics on Polars.** The backend computes analytics with Polars (fast, modern API; it is already used by the generator), not pandas. scikit-learn (M4) works on numpy arrays exported from Polars.
- **2026-10-14 — Auth.**
  - PyJWT + pwdlib (argon2id). Tokens carry `type` and `ver`; refresh tokens are rejected where access is required (a bug of the earlier app).
  - Logout bumps `token_version`, which revokes every token.
  - Browsers get the refresh token only as an httpOnly cookie (path `/api/v1/auth`, rotated); CLI clients may request it in the body.
  - Prod sets `ALLOW_REGISTRATION=false` and creates accounts with `dss create-user`.
- **2026-10-14 — Simulator.**
  - Daily simulation with hidden satisfaction (AR(1)) and churn only at renewal.
  - Licence scarcity with FIFO holds; zero-result searches reveal demand for held-out titles.
  - A past randomized campaign with heterogeneous effects, including e-mail "sleeping dogs".
  - Ground truth with outcomes under every action (common random numbers).
  - The dataset file is columnar JSON (`docs/schema/dataset.schema.json`).
  - 5k members × 24 months simulate in ~15 s; signal-recovery tests pass across seeds.
- **2026-10-14 — Catalogue.**
  - Real data: Open Library (CC0) for Ukrainian and English works, popularity and quality from its ratings and reading log.
  - goodbooks-10k (CC BY-SA 4.0) only to calibrate reader behaviour.
  - Exclude Russian-language editions only.
  - The earlier app's `book_database.json` is dropped: it has wrong genres, random page counts and Russian titles.
- **2026-10-14 — Process.** No commits/pushes without approval. oxlint stays as the linter.
- **2026-10-14 — Repository.** Fresh repo `Premisterio/library-dss` (public) instead of a new branch in `Diploma`.
- **2026-10-14 — Stack.** Newest possible: Python 3.15, TS 7, Node 26, PostgreSQL 18. The TS 7 gaps are handled with oxlint and the isolated codegen.
- **2026-10-08 — Frontend scope.** The frontend is thin on shadcn defaults; the author will redesign it later, so the backend must be maximally reusable.
- **2026-10-08 — DSS scope.** Both modules: retention (core) and content acquisition (MCDA). Paid VPS hosting.
