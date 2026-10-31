"""Integration tests run on their own database so they never wipe the demo/dashboard data."""

import os

import psycopg
import pytest

from pipeline.config import Settings

TEST_DB = "pipeline_test"


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database():
    settings = Settings.from_env()
    with psycopg.connect(
        host=settings.host,
        port=settings.port,
        user=settings.user,
        password=settings.password,
        dbname="postgres",
        autocommit=True,
    ) as admin:
        exists = admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,))
        if exists.fetchone() is None:
            admin.execute(f'CREATE DATABASE "{TEST_DB}"')

    previous = os.environ.get("POSTGRES_DB")
    os.environ["POSTGRES_DB"] = TEST_DB  # takes precedence over .env in Settings.from_env()
    yield
    if previous is None:
        del os.environ["POSTGRES_DB"]
    else:
        os.environ["POSTGRES_DB"] = previous
