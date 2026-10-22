"""Needs Postgres (docker compose up -d postgres)."""

from datetime import datetime
from decimal import Decimal
from functools import partial

import psycopg
import pytest

from pipeline import db
from pipeline.config import Settings
from pipeline.faults import flaky_db
from pipeline.generate import generate_files
from pipeline.models import FlaggedTransaction, ProcessingResult, Transaction
from pipeline.run import run_pipeline
from pipeline.sources import local_source

pytestmark = pytest.mark.integration

FILES = ["transactions_001.csv", "transactions_002.csv", "transactions_003.csv"]

ALICE = "FR7630001000010000000000A01"
BOB = "FR7630002000020000000000B02"
CARL = "DE89370400440532013000"
DIEGO = "ES9121000418450200051332"
ELLA = "GB29NWBK60161331926819"


@pytest.fixture
def connect():
    connect_fn = partial(db.connect, Settings.from_env())
    with connect_fn() as conn:
        db.init_schema(conn)
        conn.execute("TRUNCATE processed_files CASCADE")
    return connect_fn


@pytest.fixture
def data_dir(tmp_path):
    generate_files(tmp_path)
    return tmp_path


def fetch(connect, query, params=()):
    with connect() as conn:
        return conn.execute(query, params).fetchall()


def count(connect, table):
    return fetch(connect, f"SELECT count(*) FROM {table}")[0][0]


def test_inserted_values_are_correct(connect, data_dir):
    outcomes = run_pipeline(local_source(data_dir), connect, wait_seconds=0)

    assert outcomes == dict.fromkeys(FILES, True)
    assert count(connect, "processed_files") == 3
    assert count(connect, "transactions") == 16

    f1 = "transactions_001.csv"
    assert dict(
        fetch(connect, "SELECT iban, total FROM sent_by_iban WHERE file_key = %s", (f1,))
    ) == {
        ALICE: Decimal("1500.50"),
        BOB: Decimal("10000.01"),
        CARL: Decimal("7500.00"),
        DIEGO: Decimal("50.25"),
    }
    assert dict(
        fetch(connect, "SELECT bank, total FROM sent_by_bank WHERE file_key = %s", (f1,))
    ) == {
        "BNP Paribas": Decimal("1500.50"),
        "Societe Generale": Decimal("10000.01"),
        "Deutsche Bank": Decimal("7500.00"),
        "Santander": Decimal("50.25"),
    }
    assert dict(
        fetch(connect, "SELECT iban, total FROM received_by_iban WHERE file_key = %s", (f1,))
    ) == {
        BOB: Decimal("1200.00"),
        CARL: Decimal("300.50"),
        ALICE: Decimal("5000.00"),
        DIEGO: Decimal("7500.00"),
        ELLA: Decimal("5050.26"),
    }

    # 7500.00 and 5000.01 are flagged; 5000.00 (exactly the threshold) is not.
    flagged = fetch(
        connect,
        "SELECT montant FROM transactions WHERE file_key = %s AND flagged ORDER BY montant",
        (f1,),
    )
    assert [row[0] for row in flagged] == [Decimal("5000.01"), Decimal("7500.00")]
    assert fetch(connect, "SELECT count(*) FROM transactions WHERE flagged")[0][0] == 6

    assert dict(fetch(connect, "SELECT iban, sum(total) FROM sent_by_iban GROUP BY iban")) == {
        ALICE: Decimal("6851.50"),
        BOB: Decimal("10030.01"),
        CARL: Decimal("21299.99"),
        DIEGO: Decimal("6250.25"),
        ELLA: Decimal("15075.50"),
    }


def test_rerun_does_not_process_files_twice(connect, data_dir):
    run_pipeline(local_source(data_dir), connect, wait_seconds=0)
    outcomes = run_pipeline(local_source(data_dir), connect, wait_seconds=0)

    assert outcomes == dict.fromkeys(FILES, False)
    assert count(connect, "processed_files") == 3
    assert count(connect, "transactions") == 16
    assert count(connect, "sent_by_iban") == 3 * 4  # 4 distinct senders in each of the 3 files


def test_same_content_under_another_name_is_skipped(connect, data_dir):
    run_pipeline(local_source(data_dir), connect, wait_seconds=0)
    (data_dir / "copy.csv").write_bytes((data_dir / FILES[0]).read_bytes())

    outcomes = run_pipeline(local_source(data_dir), connect, wait_seconds=0)

    assert outcomes["copy.csv"] is False
    assert count(connect, "transactions") == 16


def test_retry_recovers_from_insertion_failures(connect, data_dir):
    insert = flaky_db(db.insert_file_results, failures=2)

    outcomes = run_pipeline(
        local_source(data_dir), connect, insert=insert, attempts=3, wait_seconds=0
    )

    assert outcomes == dict.fromkeys(FILES, True)
    assert count(connect, "transactions") == 16  # no duplicate despite the retries


def test_failed_insertion_rolls_back_everything(connect):
    tx = FlaggedTransaction(
        Transaction(datetime(2026, 1, 1), "A", "FR", "B", "C", "FR", Decimal("1")), flagged=False
    )
    # A None total violates NOT NULL after the marker and the transactions were inserted.
    broken = ProcessingResult((tx,), {"X": None}, {}, {})

    with pytest.raises(psycopg.errors.NotNullViolation):
        db.insert_with_retry(connect, "broken.csv", "sum", broken, wait_seconds=0)

    assert count(connect, "processed_files") == 0
    assert count(connect, "transactions") == 0
