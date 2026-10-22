# library-dss: a decision support system for an online library

A decision support system (DSS) for an online library, built as a master's thesis. It grows out of an earlier [user data analytics system](https://github.com/Premisterio/Diploma). Main modules:

- **Subscriber retention:** churn prediction, the effect of actions, and the best action plan within a budget.
- **Content acquisition:** multi-criteria choice (AHP + TOPSIS) and selection within a budget.
- **The `libsim` generator:** a library simulator with planted dependencies, used to measure the quality of decisions experimentally.

> Status: in development; the roadmap and progress are in [docs/plan.md](docs/plan.md).

## Stack

| Part     | Technologies                                                                                 |
| -------- | -------------------------------------------------------------------------------------------- |
| Backend  | Python 3.15, FastAPI, SQLAlchemy 2.1, Alembic, PostgreSQL 18, uv, ruff, ty, pytest           |
| Frontend | TypeScript 7, React 19, Vite 8, Tailwind 4, shadcn/ui, TanStack Query, oxlint, oxfmt, Vitest |
| Contract | OpenAPI 3.1 (`/api/v1`) → typed client `@library-dss/api-client` (openapi-fetch)             |
| CI       | GitHub Actions: lint, types, tests, API client in sync, Docker image, actionlint + zizmor    |

## Quick start

You need Docker Desktop and Node.js 26 (≥ 24). A local `uv` is optional, because the Python part runs in Docker.

```bash
docker compose up -d     # PostgreSQL 18 + API with auto-reload + background worker
docker compose exec -e DSS_PASSWORD=demo-password api dss seed-demo   # demo@library.ua + data + report
npm install
npm run dev              # frontend at http://localhost:5173 (proxies /api → :8000)
```

- API docs (Scalar): <http://localhost:8000/api/docs>
- Readiness check: <http://localhost:8000/api/v1/ready>
- Default environment variables are in [`.env.example`](.env.example); copy it to `.env` to change them.

## Checks (the same as CI)

```bash
docker compose exec api pytest                  # backend tests (with the database)
npm run format:check && npm run typecheck && npm run lint && npm run test && npm run build
```

After changing the API, update the contract and the client (CI checks that they match):

```bash
docker compose exec -T api dss openapi > packages/api-client/openapi.json
npm run api:generate
```

Git hooks: `uv run prek install` (needs a local `uv`).

## Structure

```text
backend/            FastAPI app: app/{api/v1, services, domain, ingest, worker, models, core, utils, cli}, migrations, tests
generator/          libsim: library simulator (dataset generator + ground truth)
frontend/           thin React client on shadcn/ui (rendering only, all logic is in the API)
packages/api-client generated TypeScript API client, shared by any frontend
tools/api-codegen   isolated client generator (TS 7 has no JS compiler API yet)
```

The key architectural idea: `app/domain`, the model base of the DSS, depends on neither the web layer nor the database. The same models run from the API, the CLI (`dss`), the background worker and the thesis experiment harness. How each part works: [DESIGN.md](DESIGN.md). Rules for contributors and agents: [AGENTS.md](AGENTS.md).

## Rules

- All content (data, catalogue, UI) is in Ukrainian or English. There is no Russian-language content.
- The UI is in Ukrainian; code, comments and documentation are in English.

## License

[BSD 3-Clause](LICENSE) © 2025–2026 Volodymyr Hrehul
