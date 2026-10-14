# AGENTS.md

Guide for AI coding agents (and humans) working on **library-dss**: a decision support system (DSS) for an online library, the author's master's thesis. It evolves the bachelor's analytics app [Premisterio/Diploma](https://github.com/Premisterio/Diploma) (v1, frozen).

If a local `HANDOFF.md` exists (gitignored), read it first: it holds the live session state, uncommitted work and next steps. Update it before you finish.

## Hard rules

1. **Never commit or push without the user's explicit approval** of the changes. Prepare the change, summarize it, wait for "ok". Push only when asked.
2. **The backend is a UI-agnostic platform.** All logic, metrics, sorting and explanations live in the backend. The frontend only renders and computes no metrics. The `/api/v1` contract only changes additively; breaking changes need a new version.
3. **`backend/app/domain` is pure:** no FastAPI, SQLAlchemy, Alembic or app web/DB imports (enforced by `tests/test_architecture.py`). The thesis experiment harness imports it directly.
4. **Ground truth from the simulator never enters the app database.** Only the experiment harness reads `ground_truth.json`.
5. **Newest stack policy:** stay on the latest stable versions (see Stack). Before downgrading anything, check compatibility and ask the user.
6. **Data licenses:**
   - Open Library: CC0.
   - goodbooks-10k: CC BY-SA 4.0. Never commit its raw data. Only aggregate calibration parameters may be committed, with attribution.
7. **Languages:** UI and user-facing docs in Ukrainian; code, comments, commit messages and this file in English.

## Stack

| Area       | Tools                                                                                                                                                                           |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Python     | 3.15, uv workspace (`backend`, `generator`), ruff, ty, pytest, httpx2 (TestClient)                                                                                              |
| Backend    | FastAPI, SQLAlchemy 2.1 (typed), Alembic, psycopg 3, PostgreSQL 18, Typer CLI `dss`, Scalar docs                                                                                |
| Frontend   | TypeScript 7, React 19, Vite 8, Tailwind 4, shadcn/ui (radix, Nova preset), TanStack Query, Vitest                                                                              |
| JS tooling | **oxlint** (type-aware via `oxlint-tsgolint`) + **oxfmt**. Not ESLint/Prettier: `typescript-eslint` does not support TS 7                                                       |
| API client | `packages/api-client`: types generated from OpenAPI by `tools/api-codegen`, which is isolated on TS 5.9 because TS 7 has no JS compiler API. Never edit `src/schema.ts` by hand |
| Infra      | Docker (multi-stage, non-root prod), docker compose (dev), GitHub Actions (SHA-pinned), Dependabot (7-day cooldown), prek hooks                                                 |

## Layout

```text
backend/app/
  api/v1/      thin HTTP adapters (routers, schemas); operation_id = handler name (snake_case, unique)
  services/    use cases: DB + domain orchestration, transaction boundaries
  domain/      model base: analytics, dss/retention, dss/content (pure)
  models/      SQLAlchemy models (Base with naming convention) → Alembic migrations
  core/        config (env only), db (lazy engine), errors (RFC 9457 Problem Details), migrations
  cli/         `dss` Typer CLI: same use cases as the API
backend/migrations/  Alembic
backend/tests/       pytest (`-m db` tests need PostgreSQL)
generator/           `libsim`: library simulator (dataset v2 + ground truth), catalogue builder
frontend/            thin React client (shadcn/ui), talks to the API only via @library-dss/api-client
packages/api-client/ generated typed client + committed openapi.json
tools/api-codegen/   isolated client generator (own lockfile, not a workspace member)
```

## Commands

```bash
# setup
uv sync --all-packages          # Python 3.15 venv (.venv)
npm ci                          # JS workspaces
uv run prek install             # git hooks (ruff, oxfmt, oxlint)

# run
docker compose up -d            # PostgreSQL 18 (:5433) + API (:8000, migrations on start, reload)
npm run dev                     # frontend :5173, proxies /api → :8000

# checks (same as CI)
uv run ruff check . && uv run ruff format --check . && uv run ty check backend generator
(cd backend && uv run pytest)   # needs the compose db, or set DATABASE_URL
(cd generator && uv run pytest)
npm run format:check && npm run typecheck && npm run lint && npm run test && npm run build

# API contract changed → regenerate and commit both files (CI fails on drift)
uv run dss openapi --out packages/api-client/openapi.json
npm run api:generate

# simulator (see docs/simulation.md)
uv run libsim generate --preset demo --seed 1   # → data/generated/<id>.json.gz + ground truth
uv run libsim validate data/generated/<id>.json.gz
uv run libsim schema --out docs/schema/dataset-v2.schema.json   # after changing libsim/schema.py
```

## Conventions

- **Errors:** raise `ApiError(status, "domain.reason", detail)`. Clients rely on the stable `code`; never return ad-hoc error bodies.
- **API responses:** UI-library-agnostic.
  - Raw numbers with units.
  - ISO 8601 UTC timestamps.
  - Enums as codes; labels via `meta/enums`.
  - Charts as tidy `{dimensions, measures, rows}`.
  - Lists as `{items, total, limit, offset}`.
- **Settings:** come only from environment variables (`app.core.config.Settings`). `SECRET_KEY` has no default on purpose.
- **Domain code:** pure functions over DataFrames/dataclasses, deterministic given a seed. No `datetime.now()`: use the dataset `as_of` date.
- **Tests:**
  - every bug fix gets a regression test;
  - DB tests are marked `@pytest.mark.db`;
  - slow generator signal-recovery tests are marked `@pytest.mark.slow`;
  - pytest treats warnings as errors.
- **Simulator:**
  - every planted effect lives in `libsim/params.py`, and the model is documented in `docs/simulation.md`;
  - after changing it, rerun `libsim validate` and update the "planted vs recovered" table.
- **Frontend:**
  - data only via TanStack Query + `api-client`;
  - oxfmt style (no semicolons, double quotes);
  - shadcn components live in `frontend/src/components/ui`.

## Roadmap

| Milestone | Scope                                                                                                                                  | Status            |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| M0        | Monorepo, tooling, skeletons, dev compose, CI                                                                                          | done (2026-10-14) |
| M1        | `libsim` v2: real catalogue (Open Library + goodbooks-10k calibration), daily simulation with planted effects, ground truth, schema v2 | done, in review   |
| M2        | Backend platform: auth, jobs + worker, v1/v2 import, analytics, exports, CLI, demo seed                                                | —                 |
| M3        | Thin shadcn frontend (datasets, overview, analytics, reports) + VPS deploy                                                             | —                 |
| M4a       | Churn prediction (no leakage), explanations                                                                                            | —                 |
| M4b       | Uplift from the randomized campaign, MILP action plan, what-if, decision log                                                           | —                 |
| M5        | Content acquisition MCDA: AHP, TOPSIS/SAW, sensitivity, budget portfolio                                                               | —                 |
| M6        | Thesis experiment harness (seeds × presets × budgets vs baselines)                                                                     | —                 |
| M7        | E2E tests, backup drill, Ukrainian docs, `v2.0`                                                                                        | —                 |

## Decision log

Newest first. Add an entry for every decision that changes scope, stack or rules.

- **2026-10-14 — Simulator.**
  - Daily simulation with hidden satisfaction (AR(1)) and churn only at renewal.
  - Licence scarcity with FIFO holds; zero-result searches reveal demand for held-out titles.
  - A past randomized campaign with heterogeneous effects, including e-mail "sleeping dogs".
  - Ground truth with outcomes under every action (common random numbers).
  - Dataset v2 is columnar JSON (`docs/schema/dataset-v2.schema.json`).
  - 5k members × 24 months simulate in ~15 s; signal-recovery tests pass across seeds.
- **2026-10-14 — Catalogue.**
  - Real data: Open Library (CC0) for Ukrainian and English works, popularity and quality from its ratings and reading log.
  - goodbooks-10k (CC BY-SA 4.0) only to calibrate reader behaviour.
  - Exclude Russian-language editions only.
  - The bachelor-era `book_database.json` is dropped: it has wrong genres, random page counts and Russian titles.
- **2026-10-14 — Process.** No commits/pushes without approval. oxlint stays as the linter.
- **2026-10-14 — Repository.** Fresh repo `Premisterio/library-dss` (public) instead of a `v2` branch in `Diploma`.
- **2026-10-14 — Stack.** Newest possible: Python 3.15, TS 7, Node 26, PostgreSQL 18. The TS 7 gaps are handled with oxlint and the isolated codegen.
- **2026-10-08 — Frontend scope.** The frontend is thin on shadcn defaults; the author will redesign it later, so the backend must be maximally reusable.
- **2026-10-08 — DSS scope.** Both modules: retention (core) and content acquisition (MCDA). Paid VPS hosting.
