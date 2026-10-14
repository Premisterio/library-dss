# libsim — симулятор онлайн-бібліотеки

Генерує датасети формату v2 для СППР: реальний каталог книг (Open Library) плюс поденна симуляція читачів, позик, черг, пошуку, підписок і рандомізованої кампанії утримання із **закладеними залежностями**. Поряд з датасетом пишеться `ground_truth.json`, за яким вимірюється якість рішень системи.

Опис моделі, формули й таблиця «закладено vs відновлено»: [`docs/simulation.md`](../docs/simulation.md). Схема датасету: [`docs/schema/dataset-v2.schema.json`](../docs/schema/dataset-v2.schema.json).

```bash
uv run libsim generate --preset demo --seed 1        # 5000 читачів × 24 міс. за ~15 с, ~8 МБ gzip
uv run libsim validate data/generated/<id>.json.gz   # закладені ефекти, виміряні з даних
uv run pytest generator                              # структурні тести + тести відновлення сигналу
```

Пресети: `demo`, `weak-signal`, `no-heterogeneity`, `misspecified`, `high-scarcity`.

## Каталог і калібрування

`src/libsim/data/` містить закомічені `catalog.csv`, `catalog_meta.json` і `calibration.json`. Перебудувати їх (група залежностей `catalog`, Polars):

```bash
uv run libsim catalog fetch       # ~2 ГБ колонок Open Library у data/cache (gitignored)
uv run libsim catalog build
uv run libsim catalog calibrate   # goodbooks-10k: лише агрегати, сирі дані не комітимо
```

**Джерела:**

- Каталог — Open Library (CC0).
- Калібрування поведінки — goodbooks-10k Zygmunt Zając (CC BY-SA 4.0).

Жодного російськомовного контенту: див. правила в `AGENTS.md` і тест `tests/test_catalog_data.py`.
