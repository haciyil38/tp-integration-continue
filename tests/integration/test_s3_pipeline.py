"""Needs Postgres and Garage: docker compose up -d postgres garage && ./scripts/init_garage.sh"""

import uuid
from decimal import Decimal
from functools import partial

import pytest
from botocore.exceptions import EndpointConnectionError

from pipeline import db, s3
from pipeline.config import Settings
from pipeline.faults import flaky_s3
from pipeline.generate import generate_files
from pipeline.run import run_pipeline
from pipeline.sources import s3_source

pytestmark = pytest.mark.integration

NAMES = ["transactions_001.csv", "transactions_002.csv", "transactions_003.csv"]


@pytest.fixture
def settings():
    s = Settings.from_env()
    assert s.s3_access_key, "S3 keys missing: run ./scripts/init_garage.sh"
    return s


@pytest.fixture
def connect():
    connect_fn = partial(db.connect, Settings.from_env())
    with connect_fn() as conn:
        db.init_schema(conn)
        conn.execute("TRUNCATE processed_files CASCADE")
    return connect_fn


@pytest.fixture
def bucket_files(settings, tmp_path):
    """Upload the generated CSVs under a unique prefix, remove them afterwards."""
    client = s3.make_client(settings)
    prefix = f"test-{uuid.uuid4().hex}/"
    keys = s3.upload_files(client, settings.s3_bucket, generate_files(tmp_path), prefix)
    yield client, settings.s3_bucket, prefix, keys
    for key in keys:
        client.delete_object(Bucket=settings.s3_bucket, Key=key)


def count(connect, table):
    with connect() as conn:
        return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def test_files_are_read_from_s3_and_inserted(connect, bucket_files):
    client, bucket, prefix, keys = bucket_files

    outcomes = run_pipeline(s3_source(client, bucket, prefix, wait_seconds=0), connect)

    assert outcomes == dict.fromkeys(keys, True)
    assert count(connect, "processed_files") == 3
    assert count(connect, "transactions") == 16
    with connect() as conn:
        total = conn.execute(
            "SELECT sum(total) FROM sent_by_iban WHERE file_key = %s", (keys[0],)
        ).fetchone()[0]
    assert total == Decimal("19050.76")  # 1500.50 + 10000.01 + 7500.00 + 50.25


def test_rerun_does_not_process_s3_files_twice(connect, bucket_files):
    client, bucket, prefix, keys = bucket_files
    run_pipeline(s3_source(client, bucket, prefix, wait_seconds=0), connect)

    outcomes = run_pipeline(s3_source(client, bucket, prefix, wait_seconds=0), connect)

    assert outcomes == dict.fromkeys(keys, False)
    assert count(connect, "transactions") == 16


def test_download_retry_recovers_from_s3_failures(connect, bucket_files):
    client, bucket, prefix, keys = bucket_files
    fetch = flaky_s3(s3.fetch_object, failures=2)

    source = s3_source(client, bucket, prefix, fetch=fetch, attempts=3, wait_seconds=0)
    outcomes = run_pipeline(source, connect)

    assert outcomes == dict.fromkeys(keys, True)
    assert count(connect, "transactions") == 16


def test_download_failure_beyond_retries_inserts_nothing(connect, bucket_files):
    client, bucket, prefix, _ = bucket_files
    fetch = flaky_s3(s3.fetch_object, failures=10)

    source = s3_source(client, bucket, prefix, fetch=fetch, attempts=2, wait_seconds=0)
    with pytest.raises(EndpointConnectionError):
        run_pipeline(source, connect)

    assert count(connect, "processed_files") == 0
