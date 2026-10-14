"""Command line entry point (`libsim`)."""

import argparse
from pathlib import Path

from libsim import __version__

PACKAGE_DATA = Path(__file__).parent / "data"
DEFAULT_CACHE = Path("data/cache")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="libsim",
        description="Online library simulator: generates schema-v2 datasets with ground truth.",
    )
    parser.add_argument("--version", action="version", version=f"libsim {__version__}")
    commands = parser.add_subparsers(dest="command")

    catalog = commands.add_parser("catalog", help="Build the real book catalogue (offline tool).")
    steps = catalog.add_subparsers(dest="step", required=True)

    fetch = steps.add_parser("fetch", help="Download the needed Open Library columns into a cache.")
    fetch.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    fetch.add_argument("--refresh", action="store_true", help="Re-download existing files.")

    build = steps.add_parser("build", help="Build catalog.csv + catalog_meta.json from the cache.")
    build.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    build.add_argument("--out", type=Path, default=PACKAGE_DATA)

    calibrate = steps.add_parser(
        "calibrate", help="Derive reader-behaviour parameters from goodbooks-10k (aggregates only)."
    )
    calibrate.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    calibrate.add_argument("--out", type=Path, default=PACKAGE_DATA)
    calibrate.add_argument("--refresh", action="store_true", help="Re-download goodbooks-10k.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "catalog":
        return _catalog(args)
    return 2  # pragma: no cover - argparse rejects unknown commands


def _catalog(args: argparse.Namespace) -> int:
    # Needs the `catalog` dependency group (polars); the simulator itself does not.
    from libsim.catalog import goodbooks, openlibrary

    if args.step == "calibrate":
        source = goodbooks.fetch(args.cache_dir, refresh=args.refresh)
        calibration = goodbooks.calibrate(source)
        goodbooks.write(calibration, args.out)
        print(f"wrote calibration.json to {args.out} | {calibration['size']}")
    elif args.step == "fetch":
        openlibrary.fetch(args.cache_dir, refresh=args.refresh)
        print(f"cached Open Library tables in {args.cache_dir}")
    elif args.step == "build":
        catalog, meta = openlibrary.build(args.cache_dir)
        openlibrary.write(catalog, meta, args.out)
        print(f"wrote {meta['rows']} books to {args.out} | {meta['by_segment']}")
    return 0
