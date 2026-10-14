"""Layering rules that keep the model base reusable outside the web app."""

import ast
from pathlib import Path

import app

APP_DIR = Path(app.__file__).parent
DOMAIN_DIR = APP_DIR / "domain"
UTILS_DIR = APP_DIR / "utils"
FORBIDDEN_IN_DOMAIN = (
    "fastapi",
    "starlette",
    "sqlalchemy",
    "alembic",
    "app.api",
    "app.core.db",
    "app.models",
    "app.services",
    "app.cli",
    "app.worker",
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _matches(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def _violations(package: Path, banned: tuple[str, ...], allowed: tuple[str, ...] = ()) -> list[str]:
    files = list(package.rglob("*.py"))
    assert files, f"{package.name} package is missing"
    return sorted(
        {
            f"{path.relative_to(APP_DIR)} imports {module}"
            for path in files
            for module in _imported_modules(path)
            if _matches(module, banned) and not _matches(module, allowed)
        }
    )


def test_domain_layer_is_pure() -> None:
    assert not (violations := _violations(DOMAIN_DIR, FORBIDDEN_IN_DOMAIN)), violations


def test_utils_depend_on_nothing_else_in_the_app() -> None:
    banned = (*FORBIDDEN_IN_DOMAIN, "app")
    assert not (violations := _violations(UTILS_DIR, banned, allowed=("app.utils",))), violations
