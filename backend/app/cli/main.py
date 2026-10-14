"""`dss` command line: the same use cases as the HTTP API, usable from scripts and CI."""

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from pydantic import SecretStr

from app import __version__
from app.core.config import Settings
from app.main import create_app

app = typer.Typer(name="dss", no_args_is_help=True, help="Library DSS command line.")


@app.command()
def version() -> None:
    """Print the backend version."""
    typer.echo(__version__)


@app.command()
def openapi(
    out: Annotated[Path | None, typer.Option(help="Write to this file instead of stdout.")] = None,
) -> None:
    """Export the OpenAPI contract. Needs neither a database nor secrets."""
    schema_only = Settings.model_construct(
        database_url="postgresql+psycopg://schema-export/unused",
        secret_key=SecretStr("x" * 32),
    )
    contract = json.dumps(
        create_app(schema_only).openapi(), ensure_ascii=False, indent=2, sort_keys=True
    )
    if out is None:
        sys.stdout.write(contract + "\n")
    else:
        out.write_text(contract + "\n", encoding="utf-8", newline="\n")
