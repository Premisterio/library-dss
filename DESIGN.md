# DESIGN.md

How library-dss is built. There is one section per part of the app, covering how it works, the rules it follows and why. Process rules, the stack and commands are in [AGENTS.md](AGENTS.md). The simulator model is in [docs/simulation.md](docs/simulation.md).

Code comments only explain code that is not obvious. Design and rules live here. When you change how a part works, update its section in the same change.

## 1. System

The app is a decision support system (DSS). Its parts follow Sprague & Carlson:

| Subsystem | Code                                                                                                               |
| --------- | ------------------------------------------------------------------------------------------------------------------ |
| Data      | `backend/app/ingest` → library tables, one immutable snapshot per dataset with an `as_of` date                     |
| Models    | `backend/app/domain`: pure functions, shared by the API, CLI, worker and the thesis experiment harness             |
| Dialogue  | HTTP API `/api/v1`, the `dss` CLI and a thin frontend. Any client can replace the frontend without backend changes |

Data flows like this: a dataset file is uploaded, an import job runs, the data lands in library tables plus precomputed results, and the API serves them to any client.

```text
backend/app/
  api/v1/      HTTP adapters: request/response models, no business logic
  services/    use cases: orchestrate the database and the domain, own transactions
  domain/      model base (pure)
  ingest/      dataset files → validated frames → PostgreSQL COPY
  worker/      background job runner
  models/      SQLAlchemy models; backend/migrations: Alembic
  core/        config, database, errors, security
  utils/       small pure helpers for every layer
  cli/         `dss` command line
generator/              libsim: library simulator and catalogue builder
frontend/               thin React client
packages/api-client/    generated TypeScript client + committed openapi.json
tools/api-codegen/      isolated client generator
```

## 2. Backend

### 2.1 Layers

- `api/v1` calls `services`, which call `domain` and the database. Handlers never contain logic.
- `domain` imports no FastAPI, Starlette, SQLAlchemy, Alembic, `app.api`, `app.core.db`, `app.models`, `app.services`, `app.cli` or `app.worker`. This lets the experiment harness use it directly.
- `utils` imports nothing else from `app`, so every layer can use it, including `domain`.
- Both import rules are enforced by `tests/test_architecture.py`.

### 2.2 Core

- **Config.** Settings come only from environment variables (`app.core.config.Settings`).
  - `SECRET_KEY` has no default, so the app refuses to start without it.
  - Each app instance keeps its settings in `app.state.settings`, which lets tests build apps with overrides.
- **Database.** The engine and sessionmaker are created lazily, never at import time. The connect timeout is 5 s, so health probes and tests fail fast.
- **Errors** follow RFC 9457 Problem Details.
  - Raise `ApiError(status, "area.reason", detail)` from any layer. The stable `code` is what clients rely on.
  - Request validation errors become `request.invalid` with `errors[]` (field paths).
  - Unhandled exceptions become `server.error` and are logged.
  - 401 responses carry `WWW-Authenticate: Bearer`.
- **Security.**
  - Passwords are hashed with argon2id.
  - JWTs (HS256) carry `type` (`access`/`refresh`) and `ver` (the analyst's `token_version`). A refresh token is rejected where an access token is expected.
  - Logout bumps `token_version`, which revokes every token issued earlier.

### 2.3 HTTP API

- **The contract** is OpenAPI 3.1 at `/api/v1/openapi.json`, with docs at `/api/docs`.
  - Inside `/api/v1` changes are additive only. A breaking change needs a new path version.
- **`operation_id` is the handler name** (snake_case, unique; checked by `test_openapi.py`). It becomes the method name in generated clients, so renaming a handler breaks clients.
- **Responses do not assume any UI library:**
  - numbers are raw, with a unit;
  - timestamps are ISO 8601 in UTC, plus the dataset's `timezone`;
  - enums are codes, and their labels come from `GET /meta/enums`;
  - lists use `{items, total, limit, offset}`, with one named `Page` subclass per item type so clients get a named schema.
- **Ownership.** Every resource belongs to an analyst. Another analyst's resource answers 404, not 403, so ids do not leak.
- **Long operations** answer `202 {resource, job}` with a `Location` header pointing at the job.
  - Clients poll `GET /jobs/{id}` or follow `GET /jobs/{id}/events`, a Server-Sent Events stream built on FastAPI's `EventSourceResponse`.
  - Checks such as ownership run in dependencies, because the stream has already started by the time the generator runs.
  - A stream ends when the job finishes, or after 10 minutes; `EventSource` reconnects.
  - Errors of streaming routes are documented as JSON (`PROBLEM_JSON_RESPONSES`).
- **Auth.**
  - Browsers get the refresh token only as an httpOnly cookie (path `/api/v1/auth`, rotated on every refresh) and keep the access token in memory.
  - CLI clients ask for the refresh token in the body (`include_refresh_token`) and send it as a Bearer token.
  - Production disables registration; accounts are created with `dss create-user`.

### 2.4 Services

- Services are the use cases, shared by the API, CLI and worker.
- They own transaction boundaries (`commit`) and raise `ApiError` for expected failures.
- Lookups take the analyst, e.g. `get_for(session, id, analyst)`, so ownership is checked in one place.

### 2.5 Dataset import

There are two file formats, detected by content:

| Format    | Shape                                                                        | Detected by                             | Supports                                      |
| --------- | ---------------------------------------------------------------------------- | --------------------------------------- | --------------------------------------------- |
| `tabular` | `{schema_version, meta, tables: {name: {columns, rows}}}`, written by libsim | `schema_version` = `SCHEMA_VERSION` (2) | everything its data allows (see capabilities) |
| `nested`  | `{users: [{account, profile, activity}]}`, one object per user               | no `schema_version` and a `users` list  | descriptive analytics only                    |

- **Tabular files.**
  - The tables map one to one onto database tables; the JSON Schema is [docs/schema/dataset.schema.json](docs/schema/dataset.schema.json).
  - `app/ingest/schema.py` mirrors `libsim.schema.TABLES`, because the generator is not part of the backend image. `test_ingest.py` keeps the two equal.
- **Nested files.**
  - They have no licences, holds, campaigns or candidate titles, and their codes differ, so enum checks are skipped and the fields they lack may be empty.
  - Genres are mapped onto the catalogue genres; unmapped user fields go to `lib_users.extra`.
  - `as_of` is the date of the latest activity, and the time zone is UTC.
- **Upload** (`services/datasets.create_from_upload`):
  - The size limit `MAX_UPLOAD_MB` applies to the upload and to the decompressed JSON. Decompression is bounded, so a gzip bomb gets 413.
  - The content must be a JSON object, otherwise 422.
  - Duplicates are found by the SHA-256 of the decompressed JSON, per analyst, and answer 409.
  - The file is stored gzip-compressed in `dataset_files` (TOAST compression off), so one `pg_dump` backs up everything and imports can be rerun.
- **Import pipeline** (the `import_dataset` job), all in one transaction:
  1. orjson parses the file.
  2. Polars frames are built and typed by the schema.
  3. Validation collects every problem first, so the analyst can fix the file in one go: required values, codes, unique keys, references, and nothing dated after `as_of` (except subscription period ends). Up to 20 problems are reported.
  4. Rows are written with PostgreSQL COPY.
- **Failures.**
  - `IngestError(code, detail, errors)` fails the job and the dataset with that error.
  - Values the database rejects during COPY become `dataset.invalid`.
  - Nothing partial is left behind.
- **Capabilities.**
  - `descriptive` is always present.
  - `retention` needs subscription periods and campaign assignments.
  - `content` needs candidate titles and searches.
  - Nested files get `descriptive` only.

### 2.6 Jobs and the worker

- **The queue** is the `jobs` table, with statuses `queued → running → succeeded | failed`.
  - `claim_next` takes the oldest queued job with `SELECT … FOR UPDATE SKIP LOCKED` in its own transaction, so workers never share a job.
  - Redis and Celery are not needed.
- **Handlers** are registered in `app/worker/runner.HANDLERS[kind]`.
  - A handler does all its work in the session it receives. The runner commits that work together with the job's success, or rolls it back and records `{code, detail, errors}`.
  - `IngestError` and `ApiError` are expected failures. Anything else is recorded as `job.crashed` and logged.
- **Progress** is reported through `progress(fraction, stage)`.
  - Each report is written in its own short transaction, so clients see it while the job's transaction is still open.
  - Each report also refreshes the heartbeat.
- **Recovery.** Every 60 s the worker fails `running` jobs whose heartbeat is older than `JOB_STALE_SECONDS`, as `job.interrupted`. They cannot resume.
- **Shutdown.** On SIGINT/SIGTERM the current job is finished first; compose allows 60 s for that.
- **Adding a job kind:** enqueue it in a service, register the handler, and report progress.

### 2.7 Models and migrations

- **Models.**
  - SQLAlchemy 2 typed models.
  - A naming convention gives constraints deterministic names, which keeps migrations reviewable.
  - Every timestamp is `timestamptz` in UTC.
- **Library tables.**
  - Each has `dataset_id … ON DELETE CASCADE`, and natural ids from the file are unique per dataset.
  - There are no foreign keys between library tables: the importer validates references in bulk, which keeps COPY fast.
- **Migrations.**
  - Alembic revisions are numbered `0001`, `0002`, … in one chain, in files `NNNN_<slug>.py`.
  - `migrations/env.py` assigns the next number for `alembic revision`, with or without `--autogenerate`.
  - Review the generated code before committing.
  - `test_migrations.py` fails when models and migrations differ (`alembic check`) or when the chain breaks.
  - The api container applies migrations on start.

### 2.8 Utilities

- `app/utils` holds pure helpers that two or more places need.
- `dates.py`: time is stored and exchanged in UTC. Use `utc_now`, `parse_utc`, `start_of_day_utc`, `end_of_day_utc`, `month_start`, `ISO_UTC_FORMAT` and `UTC_DATETIME` instead of `datetime.now()` or new format strings.
- A format that belongs to one protocol stays next to its code, such as the COPY timestamp format in `ingest/load.py`.

### 2.9 Domain (model base)

- Domain code is pure functions over Polars frames and dataclasses, deterministic given a seed.
- Time comes from the dataset's `as_of`, never from the clock.
- `enums.py` holds codes with Ukrainian labels, served by `GET /meta/enums`, so clients never hard-code labels.
  - Genre codes equal the simulator's taxonomy.
  - Labels contain no Russian letters.
  - `test_meta.py` checks both.

### 2.10 CLI

- `dss` (Typer) runs the same use cases as the API: `create-user`, `openapi`, ….
- Imports that touch the database are local to commands, so `dss openapi` needs no database.

### 2.11 Tests

- pytest treats warnings as errors. Every bug fix gets a regression test. Regressions from the 2026-10-08 audit of the previous app say so in their docstrings.
- **Database.**
  - Locally, tests use a separate `dss_test` database on the compose server, created on first run, so the dev worker never takes test jobs. CI uses its own database.
  - Migrations run once per test run.
  - Each test runs in a transaction that is rolled back (`db_session`, `join_transaction_mode="create_savepoint"`), so application commits only release savepoints.
- **Jobs.**
  - `run_jobs` runs queued jobs synchronously. Like the real worker, each step gets its own session, here a savepoint on the test connection.
  - `test_worker.py` uses real committed transactions and deletes its analyst at the end. It covers SKIP LOCKED, atomic failure, recovery and the poll loop.
- **Fixtures.**
  - `tabular_document`: a small libsim dataset.
  - `nested_document`: a hand-made nested-format file, Ukrainian and English content only.
- **Contract and structure:** `test_openapi.py`, `test_architecture.py` and `test_migrations.py`.

## 3. Generator (libsim)

- The model, its formulas and the "planted vs recovered" table are in [docs/simulation.md](docs/simulation.md).
  - Every planted effect lives in `libsim/params.py`.
  - After changing the model, rerun `libsim validate` and update the table.
- **Determinism.**
  - Randomness comes from `SeedSequence` streams; ids are deterministic; keys are sorted; gzip `mtime` is 0.
  - The same parameters give byte-identical files.
- **Output.**
  - The dataset is a tabular file; `libsim/schema.py` is the source of the format.
  - `libsim schema` writes the JSON Schema.
  - `ground_truth.json` (hidden state, outcomes under every action) is read only by the experiment harness, never by the app.
- **Catalogue.**
  - Works come from Open Library (CC0). Reader behaviour is calibrated on goodbooks-10k (CC BY-SA 4.0), and only aggregates are committed, with attribution.
  - Russian-language editions are excluded. The guards check language codes, the letters ё/ъ/ы/э and Russian dictionaries.
- Slow signal-recovery tests are marked `@pytest.mark.slow`.

## 4. API client and frontend

- **API client.**
  - `packages/api-client` is generated from the committed `openapi.json` by `tools/api-codegen`. That tool is isolated on TypeScript 5.9 because TypeScript 7 has no JS compiler API.
  - Never edit `src/schema.ts` by hand. CI fails when the client drifts from the backend.
- **Frontend.**
  - It renders and computes no metrics. When a field is missing, extend the backend.
  - Data comes only through TanStack Query and the api client. Labels come from `meta/enums`. Errors are mapped by their Problem `code`.
  - shadcn components live in `frontend/src/components/ui`. Style is oxlint plus oxfmt (no semicolons, double quotes).

## 5. Infrastructure and CI

- **Dev compose:**
  - `db`: PostgreSQL 18 on port 5433;
  - `api`: applies migrations, reloads on change;
  - `worker`: restarted by watchfiles on change.
  - The frontend runs natively with a `/api` proxy.
- **Images.** The `prod` target is non-root. Its HEALTHCHECK probes HTTP, so a production worker service needs its own check.
- **CI.**
  - Jobs: Python (ruff, ty, pytest with coverage, generator tests), frontend (format, types, lint, tests, build), API contract drift, Docker prod image, workflow lint (actionlint, zizmor).
  - Actions are pinned by SHA. Dependabot waits 7 days before proposing a version.
  - prek hooks run ruff, oxfmt and oxlint.
