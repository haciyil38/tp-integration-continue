"""Fault injection used to demonstrate and test the retry mechanism."""

import psycopg

from pipeline.db import InsertFn


def flaky(insert: InsertFn, failures: int) -> InsertFn:
    """Wrap an insert function so its first `failures` calls raise OperationalError."""
    remaining = failures

    def wrapper(*args, **kwargs):
        nonlocal remaining
        if remaining > 0:
            remaining -= 1
            raise psycopg.OperationalError("simulated database failure")
        return insert(*args, **kwargs)

    return wrapper
