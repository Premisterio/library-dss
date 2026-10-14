# The `libsim` simulator: a model of an online library

`libsim` generates datasets for the DSS in the tabular format ([schema](schema/dataset.schema.json)). The model and the "Experiments" chapter of the thesis rest on this document.

**Why a simulation.** There are no public lending logs that include subscriptions and campaigns. Evaluating decisions also needs the **truth**, for example whether a discount would really have kept a member.

The simulator plants known dependencies in the data and writes them to a separate `ground_truth.json`. This makes the quality of the DSS models and decisions measurable, not only describable.

## Data: what is real and what is simulated

| Part                                                         | Source                                                                                                                                                          |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Catalogue**                                                | Real, from Open Library (CC0): 3975 books — 211 Ukrainian editions with real demand signals, 798 long-tail Ukrainian books, 2966 popular English-language works |
| **Book popularity and quality**                              | Real Open Library ratings and reading log, plus noise                                                                                                           |
| **Reader behaviour parameters**                              | Calibrated on goodbooks-10k (CC BY-SA 4.0, 6 M ratings by 53 k readers): rating scale, taste concentration, long tail of popularity                             |
| **Members, loans, sessions, holds, subscriptions, campaign** | Simulated by the model below                                                                                                                                    |

There is no Russian-language content: the catalogue has Ukrainian and English editions only (see `AGENTS.md`).

## Time

- **Step and observation window.** The simulation steps one day at a time. The history covers `months` months up to the snapshot date `as_of`.
- **After the snapshot.** The simulation runs `horizon_days` (30) more days past `as_of`. Those events **do not reach** the dataset; they only feed the ground truth about the outcomes of actions.
- **Time zone.** Event times are written in UTC; the local zone is `Europe/Kyiv`.
- **Daily rhythm.** Three reader chronotypes: morning, evening and night owl.
- **Weekly and seasonal rhythm.** Weekends +25% activity, summer −15%, students +25% in September.

## Members

- **Registration.** An initial cohort (35%) plus newcomers, with a growth trend of 25% a year.
- **Profile (visible in the data):**
  - age group and education;
  - language preference (half read Ukrainian only);
  - e-mail opt-in (70%);
  - declared interests: 3 genres, 25% noise.
- **Hidden (ground truth only):**
  - genre tastes, `Dirichlet(11.4 · genre_base · age_tilt)`, where 11.4 is calibrated on goodbooks-10k;
  - reading pace;
  - baseline satisfaction;
  - price sensitivity;
  - a hidden factor (for the `misspecified` preset).

## Satisfaction: the hidden state

Each member has a satisfaction `s` that drifts back to their own level `μ` every day:

```text
s(t+1) = 0.985 · s(t) + 0.015 · μ + N(0, 0.04) + event shocks
```

Events shift `s`:

| Event                     | Shift of `s` |
| ------------------------- | ------------ |
| Finished a book rated ≥ 4 | +0.18        |
| A bad book (rated ≤ 2)    | −0.12        |
| A hold that lapsed        | −0.30        |
| A search with no results  | −0.12        |

A member's activity is multiplied by `exp(0.9 · s)`. The data therefore shows only the **consequences** of satisfaction (activity), never `s` itself, so churn prediction cannot be perfect, just as in reality.

## Reading, loans, holds

- **Choosing a book.**
  - The genre follows the member's tastes.
  - Within the genre, the chance of a book is proportional to `popularity · exp(0.4 · quality)`. Members do not borrow the same book twice.
- **Finishing.**
  - Probability `σ(1.2 + 0.6·quality + 0.7·taste_fit − 0.5·ln(pages/300))`.
  - Unfinished books are dropped at 10–60%.
- **Rating.**
  - Latent value `3.9 + 0.45·quality + 0.35·taste_fit + reader_bias + noise`.
  - Extreme opinions are rated more often, so the distribution is close to goodbooks-10k.
- **Licences.** The number of copies grows with a book's popularity and the size of the audience. 20% of titles are deliberately under-licensed.
- **No free copy.** The member places a hold (60%), borrows another book (30%) or gives up (10%).
- **Holds.** Served first in, first out; they lapse after 21 days.
- **Loan period.** 21 days; then the book returns automatically.

## Search

- **Ordinary searches** appear before a loan (by title or author) and while browsing a genre.
- **Books the library does not have.**
  - 300 catalogue titles are missing from the collection.
  - In 75% of cases, wanting such a book produces a **zero-result search** and a satisfaction shock. This is the observable trace of unmet demand.
- **Candidates.**
  - A distributor offers 60 of those titles.
  - They are the alternatives for the content acquisition module, with a licence price that correlates with demand.

## Subscriptions and churn

**Plans:**

| Plan    | Price    | Period   |
| ------- | -------- | -------- |
| Monthly | 149 UAH  | 30 days  |
| Annual  | 1290 UAH | 365 days |
| Student | 79 UAH   | 30 days  |

A new member starts with a 14-day trial (55%) or on the free tier (one loan at a time). Trial conversion depends on satisfaction and activity.

**Churn happens only at renewal:**

```text
logit P(churn) = β0[plan] − 1.2·s + 0.25·frustrations_30d − 0.3·ln(1 + tenure_months) + 0.6·inactive_14d + τ(action)
β0: monthly −2.25, annual −0.75, student −2.1
```

After churn there are no more payments and no new loans.

## The past campaign and the effects of actions

**Campaign.** A randomized retention campaign ran for 4 months and ended 3 months before `as_of`. At their first renewal in that window, every paying member is randomly assigned to one of three arms:

- control (40%);
- e-mail (30%);
- a 20% discount (30%).

The true effects **differ between members**:

| Action                                              | Effect `τ` on the churn logit                                     |
| --------------------------------------------------- | ----------------------------------------------------------------- |
| Discount                                            | `−1.3 · price_sensitivity`; none for lost causes (s < −1)         |
| E-mail to a member whose activity is falling        | −0.5                                                              |
| E-mail to a dormant member (no reading for 30 days) | **+0.25**: the reminder provokes a cancellation ("sleeping dogs") |
| E-mail to anyone else                               | −0.05                                                             |

Only members who opted in receive e-mails.

## Ground truth (`*.ground_truth.json`)

The ground truth records:

- **Parameters** and churn coefficients.
- **Hidden state** of every member: `s`, price sensitivity, tastes.
- **The risk group**: members whose period ends within 30 days after `as_of`.
  - For each of them it records `p_true` and the realized outcome for every action (`none`, `email`, `discount`).
  - Outcomes come from **common random numbers**, so actions are compared fairly.
- **Campaign participants:** the true `τ` and `p_true` at assignment.
- **Books:** true quality and popularity.
- **Candidates:** true demand.

## Presets

| Preset             | What it changes                                          |
| ------------------ | -------------------------------------------------------- |
| `demo`             | The base model                                           |
| `weak-signal`      | Effects half as strong, more noise                       |
| `no-heterogeneity` | The effect of an action is the same for everyone         |
| `misspecified`     | Churn depends on a hidden factor that is not in the data |
| `high-scarcity`    | Half the licences, 40% under-licensed titles             |

## Planted vs recovered

`libsim validate` measures the effects **from the data the DSS sees only**. Results for `demo`, seed 1, 5000 members × 24 months:

| Check                                                   | From the data                            | Truth / target              |
| ------------------------------------------------------- | ---------------------------------------- | --------------------------- |
| Churn at renewal                                        | monthly 6.3%, annual 20.4%, student 6.7% | 6–10%, 20–30%               |
| Churn of inactive (≥ 14 days without reading) vs active | 11.8% vs 5.0%                            | planted `+0.6` on the logit |
| Discount effect from the randomization                  | −3.0 pp (SE 2.0)                         | −3.4 pp                     |
| E-mail effect from the randomization                    | −3.4 pp (SE 2.0)                         | −0.5 pp (within 1.5 SE)     |
| Different effects for different members                 | e-mail hurts 10% of members, helps 59%   | planted                     |
| History among loans: young vs 55+                       | 5.2% vs 11.4%                            | age tilt of tastes          |
| Fantasy among loans: young vs 55+                       | 27.4% vs 18.6%                           | age tilt of tastes          |
| Average rating ↔ true quality (≥ 10 ratings)            | Spearman 0.79                            | —                           |
| Zero-result searches ↔ true candidate demand            | Spearman 0.79                            | —                           |
| Weekend / weekday; evening 19–23                        | ×1.13; 42% of sessions                   | rhythm planted              |

These checks are tests (`generator/tests/test_signals.py`) and pass across seeds.

## Limitations and assumptions

The thesis records these as threats to validity:

- **The DSS is evaluated on our own model of the world.** That is why the `misspecified` and `weak-signal` presets exist.
- **Noisy effects.** With ~250 people per campaign arm, the e-mail effect is estimated with a large error. This is realistic; an experiment on the campaign size is part of M6.
- **One action per member, a discount for one period only.** Churn happens only at the end of a period.
- **Open Library popularity signals** reflect Open Library readers, not a Ukrainian audience.
- **goodbooks-10k covers active readers only.** The simulator's activity level is therefore lower, while the shape of the distribution is kept.

## Reproducing

```bash
uv run libsim generate --preset demo --seed 1            # data/generated/demo-s1-<hash>.json.gz + ground truth
uv run libsim validate data/generated/demo-s1-<hash>.json.gz
uv run libsim catalog fetch && uv run libsim catalog build     # rebuild the catalogue (~2 GB cache)
uv run libsim catalog calibrate                                # recompute the calibration
uv run libsim schema --out docs/schema/dataset.schema.json
```

The same parameters and seed give byte-identical files.
