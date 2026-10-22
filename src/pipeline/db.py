import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

import psycopg
from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from pipeline.config import Settings
from pipeline.models import ProcessingResult

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

ConnectFn = Callable[[], AbstractContextManager[psycopg.Connection]]
InsertFn = Callable[[psycopg.Connection, str, str, ProcessingResult], bool]


def connect(settings: Settings) -> psycopg.Connection:
    return psycopg.connect(
        host=settings.host,
        port=settings.port,
        user=settings.user,
        password=settings.password,
        dbname=settings.dbname,
    )


def init_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def insert_file_results(
    conn: psycopg.Connection, file_key: str, checksum: str, result: ProcessingResult
) -> bool:
    """Insert every result of one file in a single transaction.

    Returns False when the file was already processed (same name or same content): nothing is
    written. The marker row and the results commit or roll back together, which is what makes
    a retry safe.
    """
    with conn.transaction():
        marker = conn.execute(
            "INSERT INTO processed_files (file_key, checksum) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING RETURNING file_key",
            (file_key, checksum),
        ).fetchone()
        if marker is None:
            return False

        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO transactions (file_key, transaction_datetime, iban_origine, "
                "pays_source, banque_source, iban_destinataire, pays_destinataire, montant, "
                "flagged) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    (
                        file_key,
                        f.transaction.datetime,
                        f.transaction.iban_origine,
                        f.transaction.pays_source,
                        f.transaction.banque_source,
                        f.transaction.iban_destinataire,
                        f.transaction.pays_destinataire,
                        f.transaction.montant,
                        f.flagged,
                    )
                    for f in result.transactions
                ],
            )
            for table, column, totals in (
                ("sent_by_iban", "iban", result.sent_by_iban),
                ("sent_by_bank", "bank", result.sent_by_bank),
                ("received_by_iban", "iban", result.received_by_iban),
            ):
                cur.executemany(
                    f"INSERT INTO {table} (file_key, {column}, total) VALUES (%s, %s, %s)",
                    [(file_key, key, total) for key, total in totals.items()],
                )
    return True


def insert_with_retry(
    connect_fn: ConnectFn,
    file_key: str,
    checksum: str,
    result: ProcessingResult,
    *,
    insert: InsertFn = insert_file_results,
    attempts: int = 3,
    wait_seconds: float = 1.0,
) -> bool:
    """Retry the insertion on connection-level errors, with exponential backoff.

    Only psycopg.OperationalError is retried (database down, connection lost...): data errors
    would fail the same way every time.
    """
    for attempt in Retrying(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=wait_seconds),
        retry=retry_if_exception_type(psycopg.OperationalError),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    ):
        with attempt, connect_fn() as conn:
            return insert(conn, file_key, checksum, result)
    raise AssertionError("unreachable")  # pragma: no cover
