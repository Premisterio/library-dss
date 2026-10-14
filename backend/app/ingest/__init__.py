"""Dataset import: parse a file (v2 or the bachelor-era v1 format), validate it and load it.

Parsing and validation work on Polars frames and never touch the database; `load` writes the
validated frames with PostgreSQL COPY inside the caller's transaction.
"""


class IngestError(Exception):
    """The file cannot be imported; `code` is a stable Problem Details code."""

    def __init__(self, code: str, detail: str, errors: list[str] | None = None) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.errors = errors or []

    def as_problem(self) -> dict[str, object]:
        return {"code": self.code, "detail": self.detail, "errors": self.errors}
