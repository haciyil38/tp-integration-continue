from contextlib import nullcontext

import psycopg
import pytest

from pipeline.db import insert_with_retry
from pipeline.faults import flaky
from pipeline.models import ProcessingResult

RESULT = ProcessingResult((), {}, {}, {})


def fake_connect():
    return nullcontext(None)


def always_inserts(*_args):
    return True


def test_succeeds_after_transient_failures():
    insert = flaky(always_inserts, failures=2)
    assert insert_with_retry(
        fake_connect, "f.csv", "sum", RESULT, insert=insert, attempts=3, wait_seconds=0
    )


def test_raises_when_attempts_are_exhausted():
    insert = flaky(always_inserts, failures=5)
    with pytest.raises(psycopg.OperationalError):
        insert_with_retry(
            fake_connect, "f.csv", "sum", RESULT, insert=insert, attempts=3, wait_seconds=0
        )


def test_does_not_retry_data_errors():
    calls = []

    def broken(*_args):
        calls.append(1)
        raise psycopg.errors.NotNullViolation("bad data")

    with pytest.raises(psycopg.errors.NotNullViolation):
        insert_with_retry(
            fake_connect, "f.csv", "sum", RESULT, insert=broken, attempts=3, wait_seconds=0
        )
    assert len(calls) == 1
