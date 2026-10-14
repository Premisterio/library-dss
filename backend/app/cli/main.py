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


@app.command("seed-demo")
def seed_demo(
    password: Annotated[
        str,
        typer.Option(
            prompt=True,
            hide_input=True,
            envvar="DSS_PASSWORD",
            help="Password of the demo account (kept if the account exists).",
        ),
    ],
    email: Annotated[str, typer.Option(help="Demo account e-mail.")] = "demo@library.ua",
    name: Annotated[str, typer.Option(help="Demo account name.")] = "Демо-аналітик",
    file: Annotated[
        Path | None, typer.Option(help="Import this dataset file instead of simulating one.")
    ] = None,
    preset: Annotated[str, typer.Option(help="libsim preset.")] = "demo",
    seed: Annotated[int, typer.Option(help="libsim seed.")] = 1,
    users: Annotated[int | None, typer.Option(help="Members (default: the preset's).")] = None,
    months: Annotated[int | None, typer.Option(help="Months of history.")] = None,
) -> None:
    """Create a demo analyst with an imported dataset and a report (reuses what exists)."""
    from app.cli.demo import seed_demo as run_seed
    from app.cli.demo import simulate
    from app.core.config import get_settings
    from app.core.db import get_sessionmaker
    from app.core.errors import ApiError

    if file is not None:
        filename, content = file.name, file.read_bytes()
        dataset_name = file.name.removesuffix(".gz").removesuffix(".json")
    else:
        try:
            filename, content = simulate(preset, seed, users, months)
        except ImportError as exc:
            typer.echo("error: libsim is not installed here; pass --file", err=True)
            raise typer.Exit(1) from exc
        dataset_name = f"Демо ({preset}, seed {seed})"
    try:
        result = run_seed(
            get_sessionmaker(),
            get_settings(),
            email=email,
            name=name,
            password=password,
            filename=filename,
            content=content,
            dataset_name=dataset_name,
        )
    except ApiError as exc:
        typer.echo(f"error: {exc.code}: {exc.detail}", err=True)
        raise typer.Exit(1) from exc
    created = "created" if result.analyst_created else "existing, password unchanged"
    typer.echo(f"analyst  {result.email} ({created})")
    new = "imported" if result.dataset_created else "already there"
    typer.echo(f"dataset  #{result.dataset_id} {result.dataset_status} ({new})")
    if result.report_id is None:
        typer.echo("error: the dataset did not import; see the job error", err=True)
        raise typer.Exit(1)
    typer.echo(f"report   #{result.report_id}")


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
