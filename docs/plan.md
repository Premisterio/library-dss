# Plan and progress

The roadmap of library-dss and where it stands. Read it at the start of a session to know what is done and what comes next. Update it when a milestone or a notable part of one is merged.

How each part works is in [DESIGN.md](../DESIGN.md). Working rules are in [AGENTS.md](../AGENTS.md). The live, local session state is in `HANDOFF.md` (gitignored).

## Goal

The author's master's thesis turns an earlier analytics app for an online library into a **decision support system (DSS)** with two decision modules:

- **Subscriber retention:** predict churn, estimate the effect of actions (e-mail, discount) from a past randomized campaign, and choose the best actions under a budget.
- **Content acquisition:** rank candidate titles with multi-criteria methods (AHP, TOPSIS) and pick a portfolio under a budget.

The quality of decisions is measured on `libsim`, a library simulator that plants known effects and writes the ground truth. Everything is built and checked **locally first**. Production deployment is the last milestone, after the thesis supervisor has agreed on the work.

## Progress

| Milestone | Scope                                                                                    | Status           |
| --------- | ---------------------------------------------------------------------------------------- | ---------------- |
| M0        | Repository, tooling, dev compose, CI                                                     | done             |
| M1        | `libsim`: real catalogue, daily simulation with planted effects, ground truth, schema    | done             |
| M2        | Backend platform: auth, import, jobs, analytics, reports, CLI, contract tests            | done (PRs #4–#8) |
| M3        | Thin frontend on shadcn, run locally                                                     | done             |
| M4a       | Churn prediction without leakage, explanations                                           | **next**         |
| M4b       | Action effects, optimal action plan under a budget, what-if, decision log                | —                |
| M5        | Content acquisition: AHP, TOPSIS/SAW, sensitivity, budget portfolio                      | —                |
| M6        | Thesis experiment harness                                                                | —                |
| M7        | Local finish: end-to-end tests, backup drill, user docs, guide for the frontend redesign | —                |
| M8        | Production deployment on a VPS (after the supervisor's approval)                         | —                |

If time runs short, cut in this order: `libsim continue` → Monte Carlo sensitivity → T-learner → the "more copies" content preset.

## Done

### M0. Repository and tooling

- **Repository.** Public repository `Premisterio/library-dss`, with a uv workspace (`backend`, `generator`) and npm workspaces (`frontend`, `packages/*`).
- **Stack.** Python 3.15, PostgreSQL 18, Node 26 and TypeScript 7. Linting is ruff, ty, oxlint and oxfmt, run as prek hooks.
- **CI.** Five jobs: Python, frontend, API client drift, Docker production image, workflow lint. Actions are pinned by SHA, and Dependabot has a cooldown.

### M1. Simulator (`libsim`)

- **Catalogue.** 3975 real books from Open Library (CC0): Ukrainian and English editions only, with no Russian-language content.
- **Calibration.** Reader behaviour is calibrated on goodbooks-10k; only aggregates are committed.
- **Planted effects:**
  - daily simulation with hidden satisfaction;
  - churn only at renewal;
  - licence scarcity with FIFO holds;
  - zero-result searches for missing titles;
  - a randomized retention campaign whose effects differ by member, including e-mail "sleeping dogs".
- **Ground truth and presets.** The ground truth holds the outcome of every action for the risk group. Five presets cover robustness checks, and the "planted vs recovered" table is in [simulation.md](simulation.md).

### M2. Backend platform

- **Auth.** PyJWT and argon2. The refresh token lives in an httpOnly cookie, and `token_version` revokes every token.
- **Contract.** Errors follow RFC 9457 (`application/problem+json`), with labels served by `meta/enums`.
- **Dataset import.**
  - Two formats: `tabular` (libsim) and `nested` (the earlier app's per-user format).
  - A Postgres job queue, a worker, and live progress over SSE.
  - Bulk validation first, then COPY in one transaction. 5k members × 24 months import in about 8 s.
- **Descriptive analytics.** Seven sections, computed at import as of the dataset's `as_of`, in about 0.3 s. Each section has KPIs with units, tidy charts and notes. A value a dataset cannot provide is `null`, never 0.
- **Reports.** A report is a frozen copy of the analytics. It exports to PDF (embedded DejaVu), XLSX, CSV (zip) and JSON, and every export is deterministic.
- **CLI `dss`.** `create-user`, `seed-demo` (demo account, dataset and report in one command), `refresh-analytics` and `openapi`.
- **Tests.**
  - 119 tests on PostgreSQL, 96% coverage.
  - Schemathesis fuzzing of every operation.
  - Snapshots of key responses.
  - Hand-computed exact numbers on a five-member dataset.
  - Regressions for every bug found in the 2026-10-08 audit of the earlier app.

### M3. Thin frontend (local)

- **Stack.** React 19, shadcn/ui (default look), TanStack Query, react-router and recharts.
  - Data comes only through `@library-dss/api-client`, labels come from `meta/enums`, and errors are shown by their `code`.
  - The frontend computes no metrics. The author will redesign it later.
- **Sign-in.** The access token is kept in memory and renewed before it expires. A silent sign-in uses the httpOnly refresh cookie.
- **Datasets.**
  - Upload `.json`/`.json.gz` and follow the import live (SSE read with `fetch`, with polling as a fallback).
  - Show the status, capabilities and validation errors.
  - Delete a dataset after a confirmation.
- **Overview and analytics.**
  - KPIs and weekly activity on the overview; one tab per analytics section.
  - One generic renderer draws every tidy chart as bars, a line, a heatmap or a table. Every chart can switch to its table.
- **Reports.** Create a report from chosen sections, list reports, and download PDF, XLSX, CSV or JSON.
- **Backend fixes found on the way.**
  - Fuzzing found that a NUL character in text input gave 500. It now gives 422.
  - Weekly charts show complete weeks only.
  - Import stages have labels.
- **Quality.**
  - vitest covers the pure logic: chart choice, formatting, session renewal and SSE parsing.
  - The whole flow was walked through in a browser against `seed-demo` data, in light and dark theme.
  - CI runs `oasdiff breaking` on pull requests, so `/api/v1` only grows.

## Next

### M4a. Churn prediction

- **Target.** Paying members whose period ends in the next 30 days. The label is whether that period ended in churn.
- **No leakage.**
  - Rolling cutoffs: train on k ≥ 2, calibrate on k = 1, test on k = 0.
  - One `build_features(frames, cutoff)` for training and scoring, and no snapshot fields.
  - A property test checks that changing events after the cutoff changes no feature.
- **About 25 features:**
  - plan, price, discounts, tenure;
  - 7- and 30-day activity and its trend;
  - completion and ratings;
  - holds and lapses;
  - zero-result searches;
  - demographics and e-mail opt-in.
  - Missing values stay missing, with an indicator.
- **Models.**
  - Baseline rule "inactive 14+ days", logistic regression, HistGradientBoosting (+ Platt).
  - Metrics: ROC-AUC, PR-AUC, Brier (+ skill), ECE with a calibration plot, lift@10%.
  - The model is chosen by Brier/ECE, because the optimizer uses probabilities.
- **Explanations.** Coefficients and permutation importance; for each member, the top three reasons in plain words.
- **API, CLI, UI.** `churn-runs` (job), `activate`, `scores`, `scores/{user}`; pages "Model" and "Risk group".
- **Done when:**
  - the leakage test passes;
  - AUC is within 0.05 of the best achievable (from the ground truth);
  - Brier beats the rule;
  - backtesting works.

### M4b. Action effects, optimal plan, decisions

- **Effects from the campaign:**
  - ATE per arm with Newcombe intervals;
  - segment estimates with shrinkage;
  - a T-learner only if it wins on Qini;
  - fallback to the analyst's assumptions, marked as such;
  - a "cautious" mode that uses the interval bound.
- **Optimization.**
  - A multiple-choice knapsack with `scipy.optimize.milp` (HiGHS): value of a member `V_i`; gain `g_ia = (p_none − p_a)·V_i − (1 − p_a)·d_a·price − c_a`.
  - Constraints: one action per member, the budget, per-action limits, e-mail only with consent, a cooldown between discounts.
  - A greedy baseline and a budget → value curve.
- **What-if.**
  - Inputs: budget, horizon, discount sizes, costs, limits, the source of effects, risk attitude.
  - Compare up to three scenarios; the synchronous preview takes under 1 s for 2k members.
- **Decisions.**
  - Approving a scenario freezes it and exports a CSV of members.
  - An optional random 10% holdout.
  - Evaluation by backtest, and a decision log.
- **Done when:**
  - MILP equals brute force on 200 small problems;
  - the campaign interval contains the true effect;
  - the preview takes under 1 s;
  - approval produces the CSV.

### M5. Content acquisition (MCDA)

- **Alternatives.** 60 candidate titles offered by a distributor.
- **Criteria** (last 90 days):
  - C1 zero-result search demand;
  - C2 genre momentum;
  - C3 genre scarcity (holds per copy);
  - C4 author interest;
  - C5 expected quality (with shrinkage);
  - C6 importance for retention (the share of at-risk members with this genre in their top two);
  - C7 licence cost (a cost criterion).
- **AHP.**
  - Weights from the eigenvector, with the consistency ratio CR.
  - Approval is blocked when CR > 0.10, and the UI points to the three most inconsistent judgements.
- **Ranking and sensitivity.**
  - TOPSIS, plus SAW for comparison, with Kendall τ between them.
  - Sensitivity: sweep one weight and find where the leader changes; Monte Carlo over 2000 Dirichlet weight vectors.
- **Portfolio and UI.** A budget portfolio (knapsack with per-genre limits) and a wizard: criteria → AHP → ranking → sensitivity → portfolio → approval.
- **Validation.**
  - Textbook examples (Saaty; Hwang & Yoon) and a cross-check with `pymcdm`.
  - Property tests: a dominated title never beats its dominator; column scale and order do not matter.

### M6. Experiment harness

- **Design.** 20 seeds × 4 presets × budgets of 5/10/20/40%, in process, with 10k members.
- **Retention policies:** no action, random, "inactive" rule, discount by risk, DSS with assumptions, full DSS, oracle.
- **Retention metrics:**
  - net incremental gain and % of oracle;
  - precision at budget and spend;
  - AUC/Brier against the best achievable;
  - PEHE and Spearman for effects;
  - Qini.
- **Content.**
  - Policies: TOPSIS + knapsack vs "most searched", "cheapest", "top genre", random and oracle.
  - Metric: demand served.
- **Statistics and output.**
  - Mean ± 95% CI and a paired Wilcoxon test against the best baseline.
  - A separate experiment on campaign size.
  - One command rebuilds every table and figure for the thesis from a config and seeds.

### M7. Local finish

- A Playwright end-to-end test: sign in → upload → analytics → train → scenario → approve.
- A backup and restore drill on the local stack.
- User documentation.
- A guide for the frontend redesign: flows, error codes, chart formats.

### M8. Production deployment (last, after the supervisor's approval)

- **Compose.** `docker-compose.prod.yml` with Caddy (automatic HTTPS, the frontend's static files, `/api` proxy, upload size limit), api, a worker with its own health check, and PostgreSQL 18.
- **Images and deploys.** CI builds images and pushes them to GHCR, tagged by SHA. Deploys go over SSH with a health check and roll back to the previous SHA.
- **Backups and accounts.** A nightly `pg_dump` to S3-compatible storage. Registration is off; accounts are made with `dss create-user`.
- **Needed from the author:**
  - a VPS with Ubuntu, ≥ 4 GB RAM and 2 vCPU;
  - a domain with an A record pointing to it;
  - GitHub secrets (SSH key, host);
  - S3-compatible storage for backups.

## Risks

- **The system is evaluated on our own model of the world.** Mitigation: the `misspecified` and `weak-signal` presets, and a threats-to-validity section in the thesis.
- **Noisy action effects (about 250 members per campaign arm).** Mitigation: intervals, shrinkage, assumption fallback, and the campaign-size experiment.
- **Python 3.15 is new.** Packages without wheels need workarounds: DuckDB was replaced by Polars, and PyYAML is built as pure Python. scikit-learn 1.9 and scipy 1.18 do have wheels.
- **Scope.** Each milestone is time-boxed, with the cut order above.

## End-to-end check of the finished system

1. `dss seed-demo`.
2. Overview and analytics match the data.
3. The churn model's metrics are close to the best achievable.
4. A budget scenario is approved and exported as CSV.
5. The content wizard records a decision in the log.
6. The harness reproduces the thesis tables.

## Changes from the initial plan (approved 2026-10-08)

- **A fresh repository.** The project lives in `Premisterio/library-dss`, not on a `v2` branch of the earlier repository, and every step merges to `main` through a reviewed PR.
- **Newest stack.**
  - TypeScript 7: oxlint and oxfmt replace ESLint and Prettier, and the API client is generated by an isolated TypeScript 5.9 tool.
  - Python 3.15.
  - Polars replaces pandas and DuckDB.
- **Real catalogue.** The simulator uses a real catalogue (Open Library + goodbooks-10k calibration) instead of the earlier `book_database.json`.
- **Format names.** Dataset formats are named by structure (`tabular`, `nested`) instead of version numbers.
- **Documentation.** Docs are in English, and design and rules live in DESIGN.md rather than in code comments.
- **Deployment moved to the end.** It moved from M3 to M8, so the work is finished and agreed locally first.
