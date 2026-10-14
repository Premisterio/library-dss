"""Library DSS backend: HTTP API, model base, CLI and job worker."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("library-dss-backend")
except PackageNotFoundError:  # source tree without installation
    __version__ = "0.0.0"
