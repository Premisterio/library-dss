# DESIGN.md

How library-dss is built. There is one section per part of the app, covering how it works, the rules it follows and why. Process rules, the stack and commands are in [AGENTS.md](AGENTS.md). The simulator model is in [docs/simulation.md](docs/simulation.md).

Code comments only explain code that is not obvious. Design and rules live here. When you change how a part works, update its section in the same change.

## 1. System

The app is a decision support system (DSS) with two decision modules: subscriber retention (churn prediction, action effects, an optimal plan under a budget) and content acquisition (multi-criteria choice under a budget). Its parts follow Sprague & Carlson:

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
  - 405 responses list every method of the path in `Allow` (Starlette alone lists only the first route's).
  - Problems are sent as `application/problem+json`, and the OpenAPI document says so (`LibraryApi.openapi` moves FastAPI's default JSON entries).
- **Security.**
  - Passwords are hashed with argon2id.
  - JWTs (HS256) carry `type` (`access`/`refresh`) and `ver` (the analyst's `token_version`). A refresh token is rejected where an access token is expected.
  - Logout bumps `token_version`, which revokes every token issued earlier.

### 2.3 HTTP API

- **The contract** is OpenAPI 3.1 at `/api/v1/openapi.json`, with docs at `/api/docs`.
  - Inside `/api/v1` changes are additive only. A breaking change needs a new path version.
  - CI runs `oasdiff breaking` on every pull request against the base branch's `openapi.json`. A deliberate exception, such as rejecting input that used to crash, goes into `.github/oasdiff-ignore.txt` with the reason in the PR.
  - Text that reaches PostgreSQL uses `api.schemas.Text`, which rejects NUL characters with 422 (PostgreSQL text cannot hold them, so they used to give 500). An uploaded file's name comes from the multipart header, not a field, so NUL is dropped from it instead.
- **`operation_id` is the handler name** (snake_case, unique; checked by `test_openapi.py`). It becomes the method name in generated clients, so renaming a handler breaks clients.
- **Responses do not assume any UI library:**
  - numbers are raw, with a unit;
  - timestamps are ISO 8601 in UTC, plus the dataset's `timezone`;
  - enums are codes, and their labels come from `GET /meta/enums`;
  - lists use `{items, total, limit, offset}`, with one named `Page` subclass per item type so clients get a named schema;
  - analytics use KPIs and tidy charts (§2.9).
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
- **Performance.** The 5k-member, 24-month libsim demo imports in about 8 s, with a worker peak of about 280 MiB.

### 2.6 Jobs and the worker

- **The queue** is the `jobs` table, with statuses `queued → running → succeeded | failed`.
  - Kinds are `JobKind` codes (`import_dataset`, `train_churn`), labelled in enums `job_kind`.
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
- **Dataset status.** Only import jobs move their dataset to `importing` and, on failure, to `failed`. Any other job on a dataset, such as training, leaves it as it is.
- **Adding a job kind:** add a `JobKind` with its label, enqueue it in a service, register the handler, and report progress with `JobStage` codes.
- **Running a job outside the worker.** `claim(job_id)` takes one specific queued job, for example from the CLI. If a worker already took it, `wait(job_id)` blocks until the job finishes. The CLI does both through `cli/jobs.run_job`.

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
- `format.py`: numbers as Ukrainian text (`12 345,6`, `6,2 %`), for documents people read. The API never formats numbers; clients do.
- A format that belongs to one protocol stays next to its code, such as the COPY timestamp format in `ingest/load.py`.

### 2.9 Domain (model base)

- Domain code is pure functions over Polars frames and dataclasses, deterministic given a seed. Polars rather than pandas: it is fast, typed and already used by the generator. scikit-learn models take numpy arrays exported from Polars.
- Time comes from the dataset's `as_of`, never from the clock.
- `enums.py` holds codes with Ukrainian labels, served by `GET /meta/enums`, so clients never hard-code labels.
  - Genre codes equal the simulator's taxonomy.
  - Labels contain no Russian letters.
  - `test_meta.py` checks both.

**Descriptive analytics** (`domain/analytics`, served by `services/analytics.py` and `GET /datasets/{id}/analytics[/{section}]`):

- **When it runs.**
  - Computed once, at the end of the import job and in its transaction, from the frames already in memory. That takes ~0.3 s for 5k members.
  - Stored per section in `dataset_analytics` as JSONB; the API serves the stored JSON.
  - After the analytics code changes, `dss refresh-analytics` recomputes from the stored uploads. Without stored analytics the API answers `409 analytics.missing`.
- **Sections:** `overview`, `usage`, `content`, `segments`, `search`, `subscriptions`, `cohorts`. Each one is a module with a `build(frames, ctx)` function, registered in `SECTIONS`.
- **Shape of a section** (`model.py`): KPIs, tidy charts and notes.
  - A KPI is `{key, value, unit, window_days}`.
  - A tidy chart is `{dimensions, measures, attributes, rows}`: one row per combination of dimension values. It fits any chart library or a plain table.
  - Attributes describe a row without being plotted. They can tell rows apart when a dimension value repeats, such as one title by different authors; clients show them next to the repeated value.
  - A note is `{code, message_uk}`.
  - Units: `count`, `ratio` (0..1, shown as a percentage), `UAH`, `minutes`, `days`, `rating`.
  - `time` dimension values are ISO dates of the local week or month start.
- **Time.**
  - Every value is "as of the end of `as_of`" in the dataset's time zone (`Context`).
  - Windows are the last 30 days, the last 90 days (`RECENT_DAYS`) or the whole history. `window_days` says which.
  - Weekly charts show complete weeks only: a week cut short by `as_of` would look like a sudden drop.
  - A current count such as paying subscribers or MRR is the state at the end of `as_of`.
- **Missing data.** A value a dataset cannot provide is `null` with a note, never `0`. Examples: renewal outcomes, licences or result counts in nested files. Presence is detected from the data, not from the format.
- **Definitions.**
  - A title is a distinct (title, authors) pair.
  - Churn rate is churned / (renewed + churned) over periods that ended in the window.
  - MRR is each paid period's amount divided by its length in months.
  - Recency buckets count back from `as_of`.
- **Labels.** Every metric, chart, dimension, unit and category code has a Ukrainian label in `ENUMS`, so clients label everything from `GET /meta/enums`. `test_analytics.py` checks this.
- **Tests.** Exact numbers are tested on `mini_document`, a hand-made five-member dataset whose expected values were derived by hand. When a definition changes, derive the new value by hand too.

**Churn prediction** (`domain/churn`):

- **Cutoff.** A prediction is made at a cutoff, the end of a local day. It is the same `Context` the analytics use for as_of.
- **Target.**
  - The risk group at a cutoff is every member whose paid period is running at the cutoff and ends before the end of the local day 30 days later (`RISK_WINDOW_DAYS`).
    - Trials are not paid periods.
    - A member with overlapping paid periods counts once, with the period that started last.
  - The label is whether that period ended in churn (`churned` vs `renewed`). A period without a decided outcome has no label.
  - **Churn without an action.** A renewal that received a campaign action gets no label: an assignment with `delivered`, matched by `target_period_end`. The label therefore means churn without any action, the baseline against which the action plan (M4b) compares actions. Assignment was random, so the remaining renewals are still a fair sample.
- **Rolling cutoffs** (`history_cutoffs`).
  - Cutoff k is as_of − 30·(k + 1) days, back to the first paid period.
    - The risk window of k = 0 ends at as_of.
    - Windows never overlap, so every renewal is labelled at exactly one cutoff.
  - A model tested at cutoff k is trained on every older cutoff, so everything it learns from was known before the cutoff it is checked on.
  - Scoring uses the cutoff at as_of, whose periods are still running.
  - `examples` returns the labelled rows of every cutoff with their `k`.
- **No leakage.**
  - `build_features(frames, cutoff)` is the only feature code, used for training and scoring alike.
  - It reads only rows dated before the cutoff. Anything resolved later is seen as it was at the cutoff:
    - a loan returned later is still out, and its completion and rating are unknown;
    - a hold resolved later is still waiting;
    - the outcome of the running period is never read.
  - Assumptions:
    - Profile fields (age, education, language, e-mail opt-in) are fixed, because the format stores one value per member.
    - A rating is known when the loan is returned.
  - A property test (Hypothesis) rewrites the history after random cutoffs of a simulated dataset: it drops, moves and invents later rows and redraws everything that resolves later. No feature may change.
- **Features.** There are 26, in five groups. Their keys, groups, kinds and units are in `FEATURES`. Their Ukrainian labels are in enums `churn_feature`, and the group labels in `churn_feature_group`.

  | Group                               | Features                                                                                                                                                                                                                                                                            |
  | ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
  | Running period                      | plan, price per month, discount, days since the first paid period, days to renewal                                                                                                                                                                                                  |
  | Activity                            | reading sessions in 7 and 30 days; reading minutes in 30 days; trend `ln((1 + sessions in 30 days) / (1 + sessions in the 30 days before))`; days since the last session; no session in 14 days; active local days in 30 days; loans in 30 days; loans out now; searches in 30 days |
  | Reading (loans returned in 90 days) | completed books, completion rate, average rating, ratings of 1–2                                                                                                                                                                                                                    |
  | Frustrations                        | holds lapsed in 30 days, holds waiting now, zero-result searches in 30 days                                                                                                                                                                                                         |
  | Profile                             | age, education, language, e-mail opt-in                                                                                                                                                                                                                                             |

- **Missing values.** Counts without events are 0. A value that is undefined stays null, never 0. Examples: the days since the last session of a member who never read, completion and rating without returned loans, an unknown profile field. Models handle nulls themselves.
- **Models** (`models.py`).
  - The baseline is the rule "inactive for 14+ days": it predicts the churn rates of inactive and active members in the training rows.
  - The learned models work on a numeric matrix of the features:
    - numbers stay as they are, with NaN when missing;
    - flags become 0/1;
    - each category code gets a 0/1 column, with the codes taken from the enums.
  - Logistic regression puts counts, minutes, days and prices on a log scale, imputes missing values with the median plus an indicator, standardizes, and applies the default L2 penalty.
  - Gradient boosting (`HistGradientBoostingClassifier`) reads NaN directly. Its trees are small (4 leaves, at least 100 rows per leaf) and it learns slowly (rate 0.03, 200 trees), because a year of history holds a few thousand renewals and few churns.
  - Both models are fitted by log-loss and give probabilities directly. There is no separate calibration step: Platt scaling on the newest cutoff was tried and made results worse (see "Quality on libsim"). Calibration is measured instead.
- **Metrics** (`metrics.py`), on the members of the test cutoff:
  - ROC-AUC and PR-AUC (average precision);
  - the Brier score and its skill against always predicting the training churn rate;
  - ECE over 10 equal-count bins by predicted risk, and the bins themselves for a calibration plot;
  - lift: the churn rate in the riskiest 10% over the overall rate.
  - A metric that is undefined for the data, such as AUC with one class, is null.
- **Backtest and choice** (`training.py`).
  - Every model is trained and tested at origins k = 0…5. Origins without both churn and renewal in their training or test rows are skipped, but origin 0 must be usable (`NotEnoughHistoryError`).
  - The chosen model is the learned one with the lowest mean Brier score over the origins, with mean ECE breaking ties. The choice uses probabilities rather than ranking, because the action plan works with probabilities.
  - The chosen model is then refitted on every cutoff and scores the risk group at as_of.
- **Explanations** (`explain.py`). They are computed when a model is trained and kept with it.
  - **Importance** of every feature for the chosen model.
    - It is measured on the test cutoff of origin 0, with the model trained on the older cutoffs, so the rows are ones the model has not seen.
    - It is the mean increase of the Brier score over 5 shuffles of the feature. A category is shuffled as a whole.
  - **Coefficients** of logistic regression, on the standardized scale. There is one per number or flag, one per category code, and one per missing-value indicator. Boosting has none.
  - **Typical values** are taken over every labelled row: the median of each number, and the most common flag or category. A tie goes to the first value in sort order.
  - **Reasons per member.**
    - For each feature, the member's probability is recomputed with that feature at its typical value. The reasons are the features whose typical value would lower the probability most.
    - Limits:
      - at most three reasons;
      - each lowers the probability by at least 0.1 percentage points;
      - at most one per group, so that three ways of saying "reads little" do not crowd out the rest.
    - Profile features are never reasons: they describe who a member is, not why they might leave.
    - A missing value counts as a value, so "no ratings in 90 days" can be a reason.
  - **Shape of a reason.** A reason is structured: `feature`, the member's `value`, the `typical` value and the `effect`. The API adds how to show the values (`kind`, `unit`, `enum`), and so does every feature value of a member. Clients write the sentence from the enums labels, as they do with KPIs, so the API formats no numbers. For example: "Прострочені бронювання за 30 днів: 2 (типово 0)".
  - **Demo example (seed 1).** The most important features are the plan, lapsed holds and tenure. The riskiest member is explained by an annual plan (+19 percentage points), 2 lapsed holds (+11) and 1 active day in 30 (+3).
- **Quality on libsim.** The chosen model scores the members at risk at as_of, and the result is compared with the ground truth (5k members, 24 months; the best achievable AUC comes from the true probabilities):

  | Data                  | Best achievable AUC | AUC gap of the chosen model | Brier: chosen / inactivity rule |
  | --------------------- | ------------------- | --------------------------- | ------------------------------- |
  | demo, seeds 1–4       | 0.70–0.79           | 0.033–0.070, mean 0.049     | 0.0640 / 0.0656 (means)         |
  | weak-signal, seed 1   | 0.67                | 0.083                       | 0.0847 / 0.0859                 |
  | misspecified, seed 1  | 0.84                | 0.095 (a hidden driver)     | 0.0591 / 0.0635                 |
  | high-scarcity, seed 1 | 0.81                | 0.067                       | 0.0713 / 0.0744                 |
  - The chosen model beats the rule on the Brier score everywhere. Its mean predicted risk is within 0.01 of the true mean.
  - Part of the AUC gap cannot be closed: the true probability uses satisfaction and inactivity on the renewal day, up to 30 days after the cutoff.
  - Platt scaling on the newest cutoff, as first planned, made both models worse over these seven datasets:
    - the mean AUC gap grew from 0.059 to 0.060 for logistic regression and from 0.063 to 0.066 for boosting;
    - the mean predicted risk of logistic regression drifted up by 0.008 instead of 0.004.
    - The scaling rests on one cutoff, about 65 churns, and that cutoff is then lost to training.
  - Training and the backtest take about 2 s.

- **Runs** (`services/churn.py`, model `ChurnRun`).
  - `POST /datasets/{id}/churn-runs` checks that the dataset is ready and has retention data (`churn.not_supported` otherwise). It creates a run and queues a `train_churn` job, and answers `202 {run, job}` with `Location` pointing at the job.
  - The run's status and error are its job's, so nothing is kept twice.
  - The job parses the stored upload and builds the examples. It then backtests, chooses and explains a model, and scores the risk group at as_of. Its stages are `parse`, `features`, `backtest`, `scoring`.
  - Too little history fails the job with `churn.not_enough_history`; the dataset stays ready.
  - The run keeps the chosen model's key and a JSON result:
    - the summary (examples, cutoffs, churn rate, members scored and the expected churners, the sum of their probabilities);
    - each model's metrics averaged over the backtest, and every evaluation with its calibration bins;
    - importance, coefficients and typical values.
  - The fitted model itself is not stored. Scores are computed once, the dataset never changes, and training again takes seconds.
  - A run that is still queued or running cannot be deleted (`churn.busy`).
- **Activation.** `POST /churn-runs/{id}/activate` makes a trained run the one decisions use for its dataset, and deactivates the others. The analyst chooses it after reviewing the quality, so training never activates a run by itself. A partial unique index allows one active run per dataset.
- **Scores** (`ChurnScore`).
  - One row per member at risk: rank, probability, plan, period end, every feature value and the reasons.
  - `GET /churn-runs/{id}/scores` lists them, the riskiest first.
  - `GET /churn-runs/{id}/scores/{user_id}` adds every feature with its group and typical value.
  - Scores of a run that is not trained answer `409 churn.not_trained`.
- **Labels.** Clients label everything from the enums: `churn_model`, `churn_metric`, `churn_feature`, `churn_feature_group` and `job_stage`.
- **Tests.**
  - Exact values are checked on `churn_document`, which plants an event at every boundary: at the cutoff, resolved after it, starting after it.
  - On the simulated dataset, the risk group at as_of is checked against libsim's ground truth: the members it renews in the next 30 days.
  - Metrics are checked against values worked out by hand. Reasons, typical values and importance are checked by hand with a stub model whose effects are known.
  - A slow test trains on the demo (seed 1) and checks the done criteria against the ground truth: AUC within 0.05 of the best achievable, and a better Brier score than the rule.
  - `test_churn_api.py` trains through the API and the job runner on an 800-member, 10-month simulation. It covers scores, activation, ownership, deleting, and failures that leave the dataset ready. The CLI test runs `seed-demo` and then `train-churn`.
  - On the 5k-member demo, the examples of all 24 cutoffs take under 1 s.

### 2.10 Reports and exports

- **What a report is.** A report is a titled copy of some or all analytics sections of a dataset, frozen when it is created (`reports.content`). Refreshing or losing the dataset's analytics does not change it. Deleting the dataset deletes its reports.
- **API.**
  - `POST /reports` takes `{dataset_id, title, sections?}`; sections keep the canonical order whatever order is asked.
  - `GET /reports` and `GET /reports/{id}` return the frozen sections in the same shape as the analytics API.
  - `GET /reports/{id}/export?format=pdf|xlsx|csv|json` downloads the file.
- **File names** come from the title: characters other than letters, digits, spaces, `.`, `-` and `_` become `-` (so `Q1/2025` gives `Q1-2025.pdf`), with `filename*` (RFC 6266, UTF-8) and an ASCII fallback `report-<id>.<ext>`.
- **Formats** (`app/exports`, pure functions of a `ReportDocument`):
  - **PDF** (ReportLab, A4 landscape). Text uses DejaVu Sans, embedded from `app/exports/fonts` (free licence alongside), so Ukrainian renders everywhere.
    - Each section shows its notes and a KPI table.
    - Charts with one dimension are drawn: bars for categories, a line for time.
    - Charts with two dimensions become a pivot table of one measure, the first `ratio` measure if there is one. The smaller dimension goes across.
    - Tables show at most 30 rows, or the 12 most recent rows of a time series, and say that the full data is in XLSX/CSV.
  - **XLSX** (XlsxWriter): a summary sheet with every KPI, then one sheet per chart. Headers and category values are Ukrainian labels; numbers stay numbers, with formats.
  - **CSV**: a zip of `kpis.csv` and `<section>-<chart>.csv`, with codes and raw numbers, UTF-8 with a BOM (Excel).
  - **JSON**: the report as stored.
- **Determinism.** Every format is deterministic: no timestamps or random ids beyond the report's `created_at`. The same report always gives the same bytes.

### 2.11 CLI

- `dss` (Typer) runs the same use cases as the API: `create-user`, `seed-demo`, `refresh-analytics`, `train-churn`, `openapi`, ….
- `dss train-churn --dataset ID [--activate]` trains a churn model as the dataset's owner, runs the job here or waits for the worker, and prints each model's mean metrics.
- Imports that touch the database are local to commands, so `dss openapi` needs no database.
- **`dss seed-demo`** gives any client realistic data with one command:
  - it creates the demo analyst (`DSS_PASSWORD` or a prompt);
  - it simulates a libsim dataset, the same file `libsim generate` writes, or imports `--file`;
  - it runs the import itself, or waits for the worker that took it, then creates a report.
  - Running it again reuses the account, the dataset (same SHA-256) and the report.
  - libsim is a dev dependency, so the production image needs `--file`.

### 2.12 Tests

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
  - `mini_document`: a hand-made tabular file with hand-computed analytics.
  - `churn_document`: a hand-made tabular file with hand-computed churn features and labels.
  - `tabular_dataset` and `tabular_truth`: `tabular_document` parsed once per run, and libsim's ground truth for it. They are shared, so tests must not modify them.
- **Slow tests** (`@pytest.mark.slow`) train churn models on the 5k-member demo simulation, which takes about 20 s. CI runs them too.
- **Contract and structure:** `test_openapi.py`, `test_architecture.py` and `test_migrations.py`.
- **Contract fuzzing** (`test_contract.py`, Schemathesis): every operation gets valid and invalid requests (15 examples each in CI). No response may be a 500, and every response must match its documented status, content type, schema and headers. The only exception: registration may reject schema-valid e-mails on reserved domains.
- **Snapshots** (`test_snapshots.py`, syrupy): the dataset, analytics, report and enum responses on `mini_document`, with ids and timestamps masked. After an intended change, run `pytest --snapshot-update` and review the diff of `tests/__snapshots__`.
- **Dependency note.** PyYAML, which Schemathesis needs, has no Python 3.15 wheels. The root `pyproject.toml` makes uv build it as pure Python everywhere.

## 3. Generator (libsim)

- The model, its formulas and the "planted vs recovered" table are in [docs/simulation.md](docs/simulation.md).
  - Every planted effect lives in `libsim/params.py`.
  - After changing the model, rerun `libsim validate` and update the table.
- **Determinism.**
  - Randomness comes from `SeedSequence` streams; ids are deterministic; keys are sorted; gzip `mtime` is 0.
  - The same parameters give byte-identical files.
  - Local times are converted to UTC with the offset of their own day, including the period ends after as_of.
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
  - It is deliberately thin: shadcn components under a visual design grounded in Apple's Human Interface Guidelines ("Visual design" below). A redesign changes presentation only, which is why the backend carries all logic.
  - It renders and computes no metrics. When a field is missing, extend the backend.
  - Labels come from `meta/enums`. Errors are shown by their Problem `code` (`lib/messages.ts`); an unknown code falls back by status, so a raw code never reaches the user.
- **Layers** (`frontend/src`). Data and logic stay out of the markup, so a redesign replaces only `components/` and `pages/`.
  - `api/`: everything that talks to the server. That is the client and session, the query keys, and one hook module per resource (`datasets`, `analytics`, `reports`, `churn`, `jobs`, `auth`, `enums`) holding its queries and mutations. Nothing else calls `api` or `fetch`.
  - `lib/`: pure functions with no React and no network: formatting, chart choice and cell text, status, messages, sections, and churn (which run to show, feature values and reasons as text, metric text). Each module has its tests next to it.
  - `app/`: the router, paths (`paths.*`, `parseId`), route titles and the query client.
  - `components/common/`: content-layer building blocks with no data of their own (`QueryView`, `PanelCard`, `StatTile`, `StatusPill`, `EmptyState`, `ErrorAlert`, `IconButton`, `ConfirmDialog`, `ErrorBoundary`, `JobProgress`, `ProblemList`, `Pager`).
  - `components/glass/`: the functional layer (`Glass`, `GlassToolbar` with `ToolbarSlot`, `SegmentedNav`).
  - `components/<feature>/` (`shell`, `datasets`, `analytics`, `charts`, `reports`, `churn`): feature parts. They get data through props and may use `api/` hooks for their own actions.
  - `styles/`: `tokens.css` (every colour, per appearance and accessibility state) and `surfaces.css` (glass utilities, the scroll edge, the theme layer over shadcn).
  - `pages/`: connect the route to hooks and components; no markup of their own beyond composition.
  - Types come from the generated schema through `api/types.ts`; query keys live only in `api/keys.ts`.
- **Pages and routes** (react-router, `app/router.tsx`):
  - `/login`;
  - `/datasets`: upload with live import progress, list, delete;
  - `/d/:id`: a layout that checks the id, loads the dataset and renders its pages only when it is ready. Its pages read the dataset with `useCurrentDataset()`:
    - the index: overview;
    - `analytics/:section`: one section at a time, switched by a segmented control in the toolbar;
    - `reports`: create, list and download reports;
    - `churn` ("Модель") and `churn/risk` ("Група ризику"), switched by a segmented control in the toolbar:
      - The model view lists the runs and follows a training job live.
      - It shows the chosen run's quality against the rule, calibration, importance and backtest, and activates it. `?run=` picks another run.
      - The risk view pages through the active run's members at risk with their reasons, and a sheet shows one member's features against the typical values.
      - A dataset without retention data says so instead.
  - The dataset pages, which bring the chart library, are loaded lazily.
  - Every route has an error boundary. Errors below the shell stay inside it, so the navigation keeps working.
  - Each route names its page title in `handle`, and the shell toolbar shows it.
- **Server state** (TanStack Query):
  - Analytics are keyed apart from datasets, so refreshing the dataset list never refetches the (immutable) analytics.
  - The dataset list and a dataset that is still importing refresh themselves until the import ends. The churn runs of a dataset refresh themselves while one is training, and every churn query is refreshed when a training job finishes.
  - A failed mutation shows a toast from the mutation cache. A form that shows its own error opts out with `meta: { silent: true }`.
- **Session** (`api/session.ts`, `api/auth.tsx`):
  - The access token lives in memory only and is renewed shortly before it expires, one request at a time.
  - On start, the app tries a silent sign-in with the refresh cookie.
  - Never send the access token to `/auth/refresh`, `/auth/login` or `/auth/register`: refresh would read it as a refresh token.
  - Only a rejected refresh cookie (401/403) or a 401 elsewhere ends the session. A network error or a 5xx during renewal keeps a still-valid session.
  - Whatever ends a session clears the whole query cache, so the next analyst never sees the previous one's data.
  - After an explicit sign-out, the next sign-in starts at the dataset list. After an expired session, it returns to the page that asked for it.
- **Job progress** (`api/jobs.ts`):
  - The job is a query, keyed by its id, that the SSE stream writes into.
  - The SSE stream is read with `fetch()`, because `EventSource` cannot send the Authorization header. It reconnects when the server ends a stream early.
  - While the stream is down, the query polls `GET /jobs/{id}` and keeps polling through errors, so a restarting API does not leave the job unfollowed.
- **Downloads** go through the typed client as a blob and are named from `Content-Disposition` (`filename*` first).
- **Charts** (`lib/charts.ts`, `components/charts/`): one renderer for every tidy chart, chosen from its description.
  - One category dimension → bars; one time dimension → a line of the measures that share the first unit.
  - Two dimensions → a heatmap table of one measure (a ratio when there is one).
  - Otherwise → a table.
  - Every chart can switch to its table. Animation is off, so screenshots and reports show the final state.
  - A chart that fails to render shows a message in its card; the rest of the page stays.
  - `ChartPanel` is the card with the chart/table switch, and `HorizontalBars` draws the bars for tidy charts and for feature importance.
  - `CalibrationChart` puts the predicted probability against the share that churned, with the diagonal dashed.
- **Formatting** (`lib/format.ts`): `uk-UA` locale; ratios as percent; large minute totals as hours; a missing value as `—`.

### Visual design

Grounded in Apple's Human Interface Guidelines and the Liquid Glass material, translated to the web. The rules come from HIG pages (cited as `page › section`) and, for charts, from a validated data-visualisation palette.

- **Thesis.** A calm analytical instrument: the numbers are the content and the only loud thing. Navigation floats on glass above them. One accent marks the single action that matters on a screen. A snapshot capsule always says which dataset and which date the numbers describe.
- **Two layers** (`materials › Liquid Glass`):
  - **Functional layer, glass:** the floating sidebar, the floating toolbar, menus, selects, dialogs, sheets, toasts and the sign-in sheet.
  - **Content layer, solid:** cards, KPI tiles, tables, charts, forms on a page.
  - Glass on content is a defect, and so is glass stacked on glass. A control inside a glass bar (the segmented control) is a recessed fill, not glass of its own.
- **Glass recipe** (`styles/surfaces.css`, utilities `glass` and `glass-thick`):
  - Backdrop blur 24 px with saturation ×1.4.
  - A translucent fill: regular 62% / thick 78% white in light, 55% / 74% graphite in dark. Large and text-heavy surfaces such as the sidebar and menus take thick (`color › Liquid Glass color`).
  - A 1 px light edge, an inner highlight and a soft shadow.
  - Text and icons on glass stay monochrome.
- **Scroll edge effect** (`layout › Visual hierarchy`). Content fades into the page colour where it meets the toolbar, through a mask under the bar.
- **No gradients.** The page is a flat colour; the glass takes its depth from the content that scrolls beneath it.
- **Accessibility states** (`accessibility › Vision`, `liquid-glass` checklist). Each one swaps token values only:
  - Reduce Transparency: glass becomes an opaque raised surface.
  - Increase Contrast: opaque glass, stronger edges and secondary text.
  - Forced colours: plain system surfaces.
  - No `backdrop-filter` support: the opaque fallback.
  - Reduce Motion: animation and transitions collapse to instant; spinners stop.
- **Appearance** (`app/appearance.ts`).
  - Light and dark follow the system by default.
  - The account menu also offers Light and Dark, kept in this browser. The HIG advises against an in-app switch (`dark-mode › Best practices`); it stays at the author's request for demos, behind the menu, with the system as the default.
  - The resolved value is `data-theme` on `<html>`, which the dark tokens and the Tailwind `dark:` variant read. An inline script in `index.html` sets it before the first paint, so a dark page never flashes light.
- **Colour tokens** (`styles/tokens.css`; contrast is WCAG against the surface the colour sits on):

  | Role                           | Light                            | Dark                                |
  | ------------------------------ | -------------------------------- | ----------------------------------- |
  | Page                           | `#f2f2f7`                        | `#0b0b0d`                           |
  | Surface (cards)                | `#ffffff`                        | `#1c1c1e`                           |
  | Text                           | `#1d1d1f` (16.8:1)               | `#f5f5f7` (15.6:1)                  |
  | Secondary text                 | `#6e6e73` (5.1:1; 4.5:1 on page) | `#a1a1a6` (6.6:1)                   |
  | Accent (`--primary`)           | `#8e2f8a`, white label 7.2:1     | `#e07fd8` (6.6:1), dark label 7.7:1 |
  | Destructive                    | `#d70015` (5.4:1)                | `#ff6961` (6.0:1)                   |
  | Status good / critical (icons) | `#0ca30c` / `#d03b3b`            | same                                |

- **Choosing the accent.** The candidates were measured in OKLab against the chart colours and the status colours:
  - Indigo sat 8.8 from the chart blue, so action and data would read as one colour (`color › Best practices`). Teal sat 16–18 from the blue and the status green.
  - Plum is 22 from the blue, 40 from the green and 19 from the red.
- **Where the accent goes** (`color › Liquid Glass color`, `toolbars › Actions`). One prominent button per view: upload, create report, sign in, the way out of an empty or error page. It also marks selection controls (checkbox, progress), the focus ring and the current sidebar item's icon. Nothing else is tinted.
- **Status** (`color › Inclusive color`). A status is an icon in the status colour plus a label in text colour (`StatusPill`), never colour alone.
- **Typography** (`typography`).
  - Fonts: the system stack, which is SF Pro on Apple devices and Segoe UI on Windows; both have Cyrillic. No web font.
  - Sizes: body 14 px (macOS default 13); captions 12 px (minimum 10); card titles 15 px semibold; the toolbar title 15 px semibold; KPI values 26 px semibold.
  - Big standalone numbers keep proportional figures. Tabular figures are only for columns.
- **Shape.**
  - Buttons are capsules, and icon-only buttons are circles.
  - Cards have a radius of about 17 px, a hairline and a faint shadow. Glass bars are about 28 px, dialogs 20 px and menus 14 px.
  - Hit targets are at least 28 px (desktop default).
- **Charts** (data-visualisation method; the palette is validated with its script in both appearances):
  - Series colours: blue `#2a78d6` / `#3987e5`, then orange `#eb6834` / `#d95926`, assigned in that fixed order.
  - Adjacent pairs pass: colour-blind ΔE 24.7 / 26.8, normal vision 33.6 / 31.8, all marks at least 3:1 on the surface.
  - Heatmaps use one sequential blue ramp of seven steps (`heatStep`), flipped in dark so low values recede into the surface. Each step carries the label colour it needs.
  - Bars are 16 px thick, rounded at the data end and square at the baseline. Lines are 2 px.
  - A legend appears for two or more series. Every chart has a table view.
- **Shell.**
  - The sidebar floats (shadcn `variant="floating"`).
  - The toolbar holds:
    - the sidebar toggle and the page title;
    - a center area for view switching;
    - a trailing area for context (the snapshot capsule) and the account menu.
  - Pages fill the center and trailing areas through `ToolbarSlot`. Below `xl` the center area takes its own row, so view switching is never squeezed out.
  - Sign-out lives in the account menu at the top, not at the bottom of the sidebar (`sidebars › Desktop`).
- **Theme layer over shadcn.** `styles/surfaces.css` styles vendor components by their `data-slot` (dialog, menus, select, sheet, sidebar panel, buttons, cards, toasts). The shadcn CLI can then regenerate them without losing the look. `components/ui/sonner.tsx` is the one customised vendor file: it follows the app's appearance and uses the glass fill.
- **Tests and style.**
  - vitest covers the pure logic and the transport (`src/**/*.test.ts`, one file per module).
  - shadcn components (`components/ui`, `hooks/use-mobile.ts`) are generated vendor code: the shadcn CLI may overwrite them, and oxlint skips them.
  - Style is oxlint (type-aware) plus oxfmt (no semicolons, double quotes).

## 5. Infrastructure and CI

- **Dev compose:**
  - `db`: PostgreSQL 18 on port 5433;
  - `api`: applies migrations, reloads on change;
  - `worker`: restarted by watchfiles on change.
  - The frontend runs natively with a `/api` proxy.
- **Production** (planned for the last milestone, see [docs/plan.md](docs/plan.md)): one docker compose on a VPS with Caddy, api, worker and PostgreSQL; images built by CI.
- **Images.** The `prod` target is non-root. Its HEALTHCHECK probes HTTP, so a production worker service needs its own check.
- **CI.**
  - Jobs: Python (ruff, ty, pytest with coverage, generator tests), frontend (format, types, lint, tests, build), API contract drift, Docker prod image, workflow lint (actionlint, zizmor).
  - Actions are pinned by SHA. Dependabot waits 7 days before proposing a version.
  - prek hooks run ruff, oxfmt and oxlint.
