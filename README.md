# library-dss — СППР онлайн-бібліотеки

Система підтримки прийняття рішень для онлайн-бібліотеки: магістерська робота, що розвиває бакалаврську [систему аналізу даних користувачів](https://github.com/Premisterio/Diploma). Головні модулі:

- **Утримання підписників:** прогноз відтоку, оцінка ефекту дій, оптимальний план дій під бюджет.
- **Закупівля контенту:** багатокритеріальний вибір (AHP + TOPSIS) і відбір під бюджет.
- **Генератор `libsim`:** симулятор бібліотеки із закладеними залежностями, на якому експериментально оцінюється якість рішень.

> Статус: v2 у розробці. Зараз готовий каркас проєкту (M0).

## Стек

| Частина  | Технології                                                                                     |
| -------- | ---------------------------------------------------------------------------------------------- |
| Backend  | Python 3.15, FastAPI, SQLAlchemy 2.1, Alembic, PostgreSQL 18, uv, ruff, ty, pytest             |
| Frontend | TypeScript 7, React 19, Vite 8, Tailwind 4, shadcn/ui, TanStack Query, oxlint, oxfmt, Vitest   |
| Контракт | OpenAPI 3.1 (`/api/v1`) → типізований клієнт `@library-dss/api-client` (openapi-fetch)         |
| CI       | GitHub Actions: lint, типи, тести, синхронність API-клієнта, Docker-образ, actionlint + zizmor |

## Швидкий старт

Потрібні Docker Desktop і Node.js 26 (≥ 24). Встановлювати `uv` локально необов'язково: Python-частина працює в Docker.

```bash
docker compose up -d     # PostgreSQL 18 + API з авто-перезавантаженням
npm install
npm run dev              # фронтенд на http://localhost:5173 (проксі /api → :8000)
```

- API-документація (Scalar): <http://localhost:8000/api/docs>
- Перевірка готовності: <http://localhost:8000/api/v1/ready>
- Типові змінні оточення лежать у [`.env.example`](.env.example); скопіюйте у `.env`, щоб змінити.

## Перевірки (ті самі, що в CI)

```bash
docker compose exec api pytest                  # тести бекенду (з БД)
npm run format:check && npm run typecheck && npm run lint && npm run test && npm run build
```

Якщо змінювали API, оновіть контракт і клієнт (CI перевіряє, що вони синхронні):

```bash
docker compose exec -T api dss openapi > packages/api-client/openapi.json
npm run api:generate
```

Git-хуки: `uv run prek install` (потрібен локальний `uv`).

## Структура

```text
backend/            FastAPI-застосунок: app/{api/v1, services, domain, models, core, cli}, міграції, тести
generator/          libsim — симулятор бібліотеки (генератор датасетів v2 + ground truth)
frontend/           тонкий React-клієнт на shadcn/ui (лише відображення, вся логіка в API)
packages/api-client згенерований TypeScript-клієнт API, спільний для будь-якого фронтенду
tools/api-codegen   ізольований генератор клієнта (TS 7 поки не має JS compiler API)
```

Ключова ідея архітектури: `app/domain` (база моделей СППР) не залежить від вебу й БД. Ті самі моделі викликаються з API, CLI (`dss`), фонового виконавця й експериментального стенду магістерської.

## Правила

- Увесь контент (дані, каталог, інтерфейс) українською або англійською. Російськомовного контенту немає.
- Код і коментарі англійською, документація й інтерфейс українською.

## Ліцензія

[BSD 3-Clause](LICENSE) © 2025–2026 Volodymyr Hrehul
