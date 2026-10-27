# Plan and progress

The roadmap of library-dss and where it stands. Read it at the start of a session to know what is done and what comes next. Update it when a milestone or a notable part of one is merged.

How each part works is in [DESIGN.md](../DESIGN.md). Working rules are in [AGENTS.md](../AGENTS.md). The live, local session state is in `HANDOFF.md` (gitignored).

## Goal

The author's master's thesis turns an earlier analytics app for an online library into a **decision support system (DSS)** with two decision modules:

- **Subscriber retention:** predict churn, estimate the effect of actions (e-mail, discount) from a past randomized campaign, and choose the best actions under a budget.
- **Content acquisition:** rank candidate titles with multi-criteria methods (AHP, TOPSIS) and pick a portfolio under a budget.

The quality of decisions is measured on `libsim`, a library simulator that plants known effects and writes the ground truth. Everything is built and checked **locally first**. Production deployment is the last milestone, after the thesis supervisor has agreed on the work.

## Progress

| Milestone | Scope                                                                                    | Status             |
| --------- | ---------------------------------------------------------------------------------------- | ------------------ |
| M0        | Repository, tooling, dev compose, CI                                                     | done               |
| M1        | `libsim`: real catalogue, daily simulation with planted effects, ground truth, schema    | done               |
| M2        | Backend platform: auth, import, jobs, analytics, reports, CLI, contract tests            | done (PRs #4–#8)   |
| M3        | Thin frontend on shadcn, run locally                                                     | done               |
| M4a       | Churn prediction without leakage, explanations                                           | done (PRs #12–#16) |
| M4b       | Action effects, optimal action plan under a budget, what-if, decision log                | **next**           |
| M5        | Content acquisition: AHP, TOPSIS/SAW, sensitivity, budget portfolio                      | —                  |
| M6        | Thesis experiment harness                                                                | —                  |
| M7        | Local finish: end-to-end tests, backup drill, user docs, guide for the frontend redesign | —                  |
| M8        | Production deployment on a VPS (after the supervisor's approval)                         | —                  |

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
  - Layers: `api/` (server state), `lib/` (pure logic), `components/` and `pages/` (markup), so a redesign touches only the markup.
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
- **Visual design.** Apple's Human Interface Guidelines with Liquid Glass, translated to the web (DESIGN §4):
  - glass for the floating sidebar, toolbar and overlays, solid content;
  - one plum accent, a validated chart palette, system fonts;
  - light and dark follow the system by default (the account menu can pick one), with opaque fallbacks for Reduce Transparency and Increase Contrast.
- **Quality.**
  - vitest covers the pure logic: chart choice, formatting, session renewal and SSE parsing.
  - The whole flow was walked through in a browser against `seed-demo` data, in light and dark theme.
  - CI runs `oasdiff breaking` on pull requests, so `/api/v1` only grows.

### M4a. Churn prediction (PRs #12–#16)

- **Target.**
  - The risk group is the paying members whose period ends in the next 30 days.
  - The label is churn without any action: renewals that got a campaign action are left out.
- **No leakage.**
  - Rolling 30-day cutoffs; `build_features(frames, cutoff)` is the only feature code.
  - A Hypothesis property test rewrites the history after random cutoffs and checks that no feature changes.
- **Features.** 26 features in five groups (subscription, activity, reading, frustrations, profile). Undefined values stay missing.
- **Models.**
  - The rule "inactive 14+ days", logistic regression and gradient boosting, fitted by log-loss.
  - A backtest at six origins; the model with the lowest mean Brier score is chosen.
- **Quality on libsim** (5k members).
  - On four demo seeds, the chosen model's AUC is 0.033–0.070 below the best achievable, 0.049 on average.
  - It beats the rule on the Brier score on every dataset tried.
- **Explanations.** Permutation importance, logistic coefficients, and up to three reasons per member ("what if this feature were typical"), one per group and never the profile.
- **Platform.**
  - The `train_churn` job, with runs and scores stored in `churn_runs` and `churn_scores`.
  - The analyst activates the run that decisions use.
  - The API: `churn-runs`, `activate`, `scores`, `scores/{user_id}`. The CLI: `dss train-churn`.
- **UI.** A "Відтік" section with two views:
  - "Модель": runs, training progress, the quality against the rule, calibration, importance, backtest, activation;
  - "Група ризику": the members at risk with their reasons, and a card with every feature against the typical value.
- **Fixed on the way.**
  - libsim wrote period ends after a clock change an hour early.
  - Any job on a dataset used to change the dataset's status.

## Next

### M4b. Action effects, optimal plan, decisions

- **Progress.**
  - Done: the effects of actions and the optimal plan (`domain/retention`, PR #17).
  - Done: effects kept with each churn run, a synchronous plan preview, and approval as a report (PR #18).
  - Next: the UI.
- **Scope, trimmed after a review for over-engineering (2026-10-27).**
  - **Effects.** Each arm's effect comes with Newcombe intervals. E-mail is compared among consenting members. Three activity segments are shrunk toward the overall effect; there is a cautious bound and the analyst's assumptions as a fallback.
    - Kept with the churn run, so no new job or table.
    - By default the plan uses each action's overall effect, because on libsim the segment estimates cost more than they gained (DESIGN §2.9).
  - **Plan.** A multiple-choice knapsack (`scipy.optimize.milp`, solver shared with M5), a greedy baseline and a budget → value curve. Effects shift the churn logit, so they grow with a member's risk.
  - **Preview and decision.**
    - A synchronous preview answers an analytics-shaped section that every client and export can show.
    - Approval freezes it as a report of kind `retention`. The decision log is the list of reports.
  - **Cut:**
    - the T-learner and Qini: too few churns per arm;
    - discount sizes other than the campaign's: no data;
    - comparing three scenarios side by side: the budget curve covers it;
    - the 10% holdout and in-app evaluation: the experiment harness evaluates;
    - new CLI commands.
- **Done when:**
  - the MILP equals brute force on 200 small problems (done);
  - the campaign interval contains the true effect (done, demo seed 1);
  - the preview takes under 1 s (plan and curve for 2k members: about 0.6 s);
  - approval produces the export (done).

### M5. Content acquisition (MCDA)

- **Alternatives.** 60 candidate titles offered by a distributor.
- **Criteria.**
  - They are computed at import as an analytics section `candidates`, stored like the others and rebuilt by `dss refresh-analytics`.
  - Each one is first measured against libsim's true demand. Only the criteria that carry signal are kept, about five instead of seven, which leaves 10 AHP comparisons instead of 21.
  - The candidate list is about 90 days of zero-result search demand, genre momentum and scarcity, author interest, expected quality and licence cost.
  - Cost is counted once: by the portfolio's budget, or as a criterion, not both.
- **AHP.** Weights from the eigenvector, with the consistency ratio CR. Approval is blocked when CR > 0.10, and the three most inconsistent judgements are named.
- **Ranking and sensitivity.**
  - TOPSIS, plus SAW for comparison, with Kendall τ between them.
  - Sensitivity sweeps one weight to find where the leader changes. A Monte Carlo over 2000 Dirichlet weight vectors gives each title a stability figure.
- **Portfolio.** A knapsack under the budget with per-genre limits, using the solver shared with the retention plan (`domain/optimize.py`).
- **API and UI.**
  - One synchronous evaluation endpoint.
  - Approval freezes the result as a report of kind `content`.
  - One page with three panels instead of a wizard: comparisons with a live CR, the ranking with stability and the portfolio, and approval.
- **Validation.**
  - Textbook examples (Saaty; Hwang & Yoon).
  - Property tests: a dominated title never beats its dominator; column scale and order do not matter.
  - The cross-check with `pymcdm` is cut.
  - A "searches per hryvnia" baseline joins the experiment, because zero-result searches already track true demand closely.

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
- **No calibration cutoff for churn models.** The plan was to calibrate on cutoff k = 1 with Platt scaling. On seven libsim datasets, that made both models worse, so the models are fitted by log-loss on every older cutoff and their calibration is measured instead (DESIGN §2.9).
- **Deployment moved to the end.** It moved from M3 to M8, so the work is finished and agreed locally first.
