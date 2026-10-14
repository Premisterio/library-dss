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


@app.command("create-user")
def create_user(
    email: Annotated[str, typer.Option(help="Login e-mail.")],
    name: Annotated[str, typer.Option(help="Display name.")],
    password: Annotated[
        str,
        typer.Option(prompt=True, hide_input=True, confirmation_prompt=True, envvar="DSS_PASSWORD"),
    ],
    admin: Annotated[bool, typer.Option(help="Grant the admin role.")] = False,
) -> None:
    """Create an analyst account (the way to add users when registration is disabled)."""
    from app.core.db import get_sessionmaker
    from app.core.errors import ApiError
    from app.services import auth

    with get_sessionmaker()() as session:
        try:
            analyst = auth.create_analyst(
                session,
                email=email,
                name=name,
                password=password,
                role="admin" if admin else "analyst",
            )
        except ApiError as exc:
            typer.echo(f"error: {exc.code}: {exc.detail}", err=True)
            raise typer.Exit(1) from exc
    typer.echo(f"created analyst #{analyst.id} <{analyst.email}> ({analyst.role})")


@app.command("refresh-analytics")
def refresh_analytics(
    dataset: Annotated[
        int | None, typer.Option(help="Dataset id; every ready dataset when omitted.")
    ] = None,
) -> None:
    """Recompute stored analytics from the uploaded files (after the analytics code changed)."""
    from sqlalchemy import select

    from app.core.db import get_sessionmaker
    from app.models import Dataset
    from app.services import analytics

    with get_sessionmaker()() as session:
        query = select(Dataset).where(Dataset.status == "ready").order_by(Dataset.id)
        if dataset is not None:
            query = query.where(Dataset.id == dataset)
        targets = list(session.scalars(query))
        if dataset is not None and not targets:
            typer.echo(f"error: dataset #{dataset} does not exist or is not ready", err=True)
            raise typer.Exit(1)
        for target in targets:
            analytics.refresh(session, target)
            typer.echo(f"refreshed dataset #{target.id} ({target.name})")


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
