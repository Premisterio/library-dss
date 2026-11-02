"""`python -m experiments`: run the thesis experiments and rebuild their tables."""

from dataclasses import replace
from pathlib import Path
from typing import Annotated

import typer

from experiments import config as grid_config
from experiments import grid, tables

RESULTS = Path(__file__).parent / "results"

app = typer.Typer(no_args_is_help=True, help="Thesis experiments on libsim (DESIGN.md §6).")


@app.command()
def run(
    config: Annotated[Path, typer.Option(help="The grid (TOML).")] = grid_config.DEFAULT,
    out: Annotated[Path, typer.Option(help="Where the results and tables go.")] = RESULTS,
    workers: Annotated[
        int, typer.Option(min=1, help="Libraries simulated at once, about 0.7 GB of memory each.")
    ] = 2,
    seeds: Annotated[int | None, typer.Option(min=1, help="Only seeds 1…N of each preset.")] = None,
    preset: Annotated[
        list[str] | None, typer.Option(help="Only this preset; repeat for more.")
    ] = None,
) -> None:
    """Simulate every preset × seed, decide like the DSS and its rivals, judge every decision
    against the ground truth, then write the tables."""
    chosen = grid_config.load(config)
    if seeds is not None:
        chosen = replace(chosen, seeds=seeds)
    if preset:
        chosen = replace(chosen, presets=tuple(preset))
    grid.run(chosen, out, workers=workers, echo=typer.echo)
    _show(out)


@app.command("tables")
def rebuild_tables(
    out: Annotated[Path, typer.Option(help="Where the results of a run are.")] = RESULTS,
) -> None:
    """Rebuild the tables from the results of the last run."""
    _show(out)


def _show(out: Path) -> None:
    for name, table in tables.write(out).items():
        typer.echo(f"\n{name}\n{tables.text(table)}")
    typer.echo(f"\n{out / tables.WORKBOOK}")


if __name__ == "__main__":
    app(prog_name="python -m experiments")
