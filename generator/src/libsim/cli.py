"""Command line entry point (`libsim`)."""

import argparse

from libsim import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="libsim",
        description="Online library simulator: generates schema-v2 datasets with ground truth.",
    )
    parser.add_argument("--version", action="version", version=f"libsim {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0
