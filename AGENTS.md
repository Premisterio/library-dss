# AGENTS.md

Guide for AI coding agents (and humans) working on **library-dss**: a decision support system (DSS) for an online library, the author's master's thesis. It grows out of the author's earlier analytics app [Premisterio/Diploma](https://github.com/Premisterio/Diploma), which is frozen.

Read in this order:

1. `HANDOFF.md` if it exists (local, gitignored): the live state, open PRs, uncommitted work and next steps. Update it after every PR (opened, updated or merged) and before you finish.
2. [docs/plan.md](docs/plan.md): the roadmap, what is done and what comes next. Update it when a milestone (or a notable part of one) is merged.
3. This file: process rules, stack, commands.
4. [DESIGN.md](DESIGN.md): how each part of the app works and the rules it follows. Read the section of every part you change.

Keep this file general: rules, stack, commands, conventions. Progress and the roadmap go to docs/plan.md, the live session state to `HANDOFF.md`, how things work to DESIGN.md, and the history of changes stays in git and PRs (no dated entries here).

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
docker compose exec -e DSS_PASSWORD=… api dss seed-demo   # demo analyst + dataset + report

# checks (same as CI)
uv run ruff check . && uv run ruff format --check . && uv run ty check backend generator
(cd backend && uv run pytest)   # uses database dss_test on the compose server (created on first run)
(cd generator && uv run pytest)
npm run format:check && npm run typecheck && npm run lint && npm run test && npm run build

# new migration (numbered automatically, see DESIGN.md §2.7)
(cd backend && uv run alembic revision --autogenerate -m "what changed")

# analytics code changed → recompute stored analytics of existing datasets
docker compose exec api dss refresh-analytics

# an intended change of API responses → refresh snapshots and review the diff
(cd backend && uv run pytest tests/test_snapshots.py --snapshot-update)

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
- **Descriptive analytics** are computed once at import, as of the dataset's `as_of`, and stored; a value a dataset cannot provide is `null` with a note, never `0`. After changing analytics code, run `dss refresh-analytics` (§2.9).
- **Long operations** are jobs with a registered handler and progress reports (§2.6).
- **Time:** UTC everywhere through `app.utils.dates`; never `datetime.now()` (§2.8). Domain code uses the dataset's `as_of` (§2.9).
- **Migrations** are numbered `0001`, `0002`, … in one chain, one file per revision named `NNNN_<slug>.py`. Create them with `alembic revision --autogenerate -m "…"` (it assigns the number) and review the generated code. Never edit a migration that has reached `main`; add a new one (§2.7).
- **Reports** are frozen copies of analytics; exports are deterministic and name files after the title safely (§2.10).
- **Settings** come only from environment variables; `SECRET_KEY` has no default (§2.2).
- **Tests:** every bug fix gets a regression test; pytest treats warnings as errors; backend tests run against PostgreSQL in rolled-back transactions (§2.12).
- **Simulator:** planted effects live in `libsim/params.py`; after changing the model, rerun `libsim validate` and update `docs/simulation.md` (§3).
- **Frontend:** server calls only in `src/api/` (TanStack Query hooks over `api-client`); pure logic in `src/lib/`; markup in `components/` and `pages/`, reusing `components/common` and `components/glass`; oxfmt style; shadcn components in `frontend/src/components/ui` (§4).
- **Visual design:** follow DESIGN §4 "Visual design": glass only for the floating functional layer, never on content; colours only from `styles/tokens.css`, with every new colour checked for contrast in light, dark and the accessibility states; one accented action per view.
