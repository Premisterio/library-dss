"""Layering rules that keep the model base reusable outside the web app."""

import ast
from pathlib import Path

import app

APP_DIR = Path(app.__file__).parent
DOMAIN_DIR = APP_DIR / "domain"
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


def test_domain_layer_is_pure() -> None:
    files = list(DOMAIN_DIR.rglob("*.py"))
    assert files, "domain package is missing"
    violations = {
        f"{path.relative_to(APP_DIR)} imports {module}"
        for path in files
        for module in _imported_modules(path)
        if any(
            module == banned or module.startswith(f"{banned}.") for banned in FORBIDDEN_IN_DOMAIN
        )
    }
    assert not violations, sorted(violations)
