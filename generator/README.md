# libsim: an online library simulator

Generates datasets for the DSS. It combines a real book catalogue (Open Library) with a day-by-day simulation of:

- members;
- loans and holds;
- searches;
- subscriptions;
- a randomized retention campaign.

The simulation has **planted dependencies**. Next to each dataset it writes `ground_truth.json`, which is used to measure the quality of the system's decisions.

Model, formulas and the "planted vs recovered" table: [`docs/simulation.md`](../docs/simulation.md). Dataset schema: [`docs/schema/dataset.schema.json`](../docs/schema/dataset.schema.json).

```bash
uv run libsim generate --preset demo --seed 1        # 5000 members × 24 months in ~15 s, ~8 MB gzip
uv run libsim validate data/generated/<id>.json.gz   # planted effects, measured from the data
uv run pytest generator                              # structural tests + signal-recovery tests
```

Presets: `demo`, `weak-signal`, `no-heterogeneity`, `misspecified`, `high-scarcity`.

## Catalogue and calibration

`src/libsim/data/` holds the committed `catalog.csv`, `catalog_meta.json` and `calibration.json`. To rebuild them (dependency group `catalog`, Polars):

```bash
uv run libsim catalog fetch       # ~2 GB of Open Library columns in data/cache (gitignored)
uv run libsim catalog build
uv run libsim catalog calibrate   # goodbooks-10k: aggregates only, raw data is never committed
```

**Sources:**

- Catalogue: Open Library (CC0).
- Behaviour calibration: goodbooks-10k by Zygmunt Zając (CC BY-SA 4.0).

There is no Russian-language content: see the rules in `AGENTS.md` and the test `tests/test_catalog_data.py`.
