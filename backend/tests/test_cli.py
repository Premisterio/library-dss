import json
from pathlib import Path

from typer.testing import CliRunner

from app import __version__
from app.cli.main import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.output.strip() == __version__


def test_openapi_export_to_file(tmp_path: Path) -> None:
    target = tmp_path / "openapi.json"
    result = runner.invoke(app, ["openapi", "--out", str(target)])
    assert result.exit_code == 0, result.output
    contract = json.loads(target.read_text(encoding="utf-8"))
    assert contract["info"]["title"] == "Library DSS API"
    assert "/api/v1/health" in contract["paths"]


def test_openapi_export_is_deterministic() -> None:
    first = runner.invoke(app, ["openapi"]).output
    second = runner.invoke(app, ["openapi"]).output
    assert first == second
