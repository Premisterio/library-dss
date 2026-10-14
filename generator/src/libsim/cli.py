"""Command line entry point (`libsim`)."""

import argparse
import json
import time
from pathlib import Path

from libsim import __version__
from libsim import schema as schema_module
from libsim.params import PRESETS, preset

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

    generate = commands.add_parser("generate", help="Simulate a library and write a v2 dataset.")
    generate.add_argument("--preset", default="demo", choices=PRESETS)
    generate.add_argument("--seed", type=int, default=1)
    generate.add_argument("--users", type=int, help="Number of members (default from preset).")
    generate.add_argument("--months", type=int, help="Observed history length.")
    generate.add_argument("--out", type=Path, default=Path("data/generated"))
    generate.add_argument("--no-gzip", action="store_true", help="Write plain JSON.")

    schema = commands.add_parser("schema", help="Write the dataset v2 JSON Schema.")
    schema.add_argument("--out", type=Path, required=True)

    check = commands.add_parser("validate", help="Planted vs recovered effects for a dataset.")
    check.add_argument("dataset", type=Path, help="Dataset file (.json or .json.gz).")
    check.add_argument("--truth", type=Path, help="Ground truth (default: next to the dataset).")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "catalog":
        return _catalog(args)
    if args.command == "generate":
        return _generate(args)
    if args.command == "schema":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(schema_module.json_schema(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"wrote {args.out}")
        return 0
    if args.command == "validate":
        return _validate(args)
    return 2  # pragma: no cover - argparse rejects unknown commands


def _validate(args: argparse.Namespace) -> int:
    import gzip

    from libsim import validate

    raw = args.dataset.read_bytes()
    dataset = json.loads(gzip.decompress(raw) if args.dataset.suffix == ".gz" else raw)
    stem = args.dataset.name.removesuffix(".gz").removesuffix(".json")
    truth_path = args.truth or args.dataset.with_name(f"{stem}.ground_truth.json")
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    print(validate.markdown(validate.report(dataset, truth)))
    return 0


def _generate(args: argparse.Namespace) -> int:
    from libsim import engine, writer

    overrides = {
        k: v
        for k, v in {"seed": args.seed, "users": args.users, "months": args.months}.items()
        if v is not None
    }
    params = preset(args.preset, **overrides)
    started = time.perf_counter()
    result = engine.simulate(params)
    dataset, truth = writer.write(result, args.out, compress=not args.no_gzip)
    elapsed = time.perf_counter() - started
    print(f"simulated {params.users} members × {params.months} months in {elapsed:.1f}s")
    print(f"dataset:      {dataset}\nground truth: {truth}")
    return 0


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
