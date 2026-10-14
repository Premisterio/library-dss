"""Read an uploaded file (JSON or gzip-compressed JSON) into a validated ParsedDataset."""

import gzip
import io
import zlib
from datetime import date
from typing import Any

import orjson

from app.ingest import IngestError
from app.ingest.frames import ParsedDataset, capabilities_for, frames_from_v2, validate
from app.ingest.schema_v2 import SCHEMA_VERSION
from app.ingest.v1 import as_of_from, frames_from_v1

GZIP_MAGIC = b"\x1f\x8b"


def decompress(content: bytes, limit: int | None = None) -> bytes:
    """Plain or gzip bytes → JSON bytes; with `limit`, refuse more than that many bytes."""
    raw = content
    if content[:2] == GZIP_MAGIC:
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as archive:
                raw = archive.read(-1 if limit is None else limit + 1)  # bounded: no gzip bombs
        except (OSError, EOFError, zlib.error) as exc:
            raise IngestError("dataset.unreadable", "The gzip archive is damaged") from exc
    if limit is not None and len(raw) > limit:
        raise IngestError(
            "dataset.too_large", f"Datasets are limited to {limit // 2**20} MB of uncompressed JSON"
        )
    return raw


def decode(content: bytes) -> dict[str, Any]:
    try:
        document = orjson.loads(decompress(content))
    except orjson.JSONDecodeError as exc:
        raise IngestError("dataset.unreadable", "The file is not valid JSON") from exc
    if not isinstance(document, dict):
        raise IngestError("dataset.unreadable", "The file must contain a JSON object")
    return document


def parse(document: dict[str, Any]) -> ParsedDataset:
    version = document.get("schema_version")
    if version == SCHEMA_VERSION:
        meta = document.get("meta") or {}
        try:
            as_of = date.fromisoformat(meta["as_of"])
        except (KeyError, TypeError, ValueError) as exc:
            raise IngestError(
                "dataset.invalid", "meta.as_of must be a date like 2026-09-30"
            ) from exc
        frames = frames_from_v2(document)
        parsed = ParsedDataset(
            schema_version=SCHEMA_VERSION,
            meta=meta,
            as_of=as_of,
            timezone=str(meta.get("timezone", "Europe/Kyiv")),
            frames=frames,
        )
        validate(parsed)
    elif version is None and isinstance(document.get("users"), list):
        frames = frames_from_v1(document)
        parsed = ParsedDataset(
            schema_version=1,
            meta={"format": "v1 (bachelor thesis)"},
            as_of=as_of_from(frames),
            timezone="UTC",
            frames=frames,
            warnings=["v1 format: only descriptive analytics are available"],
        )
        validate(parsed, strict=False)
    else:
        raise IngestError(
            "dataset.unsupported_version",
            f"Unsupported dataset format (schema_version={version!r}); "
            f"expected {SCHEMA_VERSION} or the v1 format",
        )
    parsed.capabilities = capabilities_for(parsed.frames, parsed.schema_version)
    return parsed
