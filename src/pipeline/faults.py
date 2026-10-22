"""Fault injection used to demonstrate and test the retry mechanisms."""

from collections.abc import Callable
from typing import Any

import psycopg
from botocore.exceptions import EndpointConnectionError


def flaky(fn: Callable[..., Any], failures: int, make_error: Callable[[], Exception]):
    """Wrap fn so its first `failures` calls raise the error built by make_error."""
    remaining = failures

    def wrapper(*args, **kwargs):
        nonlocal remaining
        if remaining > 0:
            remaining -= 1
            raise make_error()
        return fn(*args, **kwargs)

    return wrapper


def flaky_db(fn: Callable[..., Any], failures: int):
    return flaky(fn, failures, lambda: psycopg.OperationalError("simulated database failure"))


def flaky_s3(fn: Callable[..., Any], failures: int):
    return flaky(fn, failures, lambda: EndpointConnectionError(endpoint_url="simulated S3 outage"))
