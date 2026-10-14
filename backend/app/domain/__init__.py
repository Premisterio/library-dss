"""Model base of the DSS: analytics, retention and content models.

Pure functions over DataFrames and dataclasses. This package must not import the web
layer or the database (enforced by tests/test_architecture.py), so the same models run
from the API, the CLI, the worker and the thesis experiment harness.
"""
