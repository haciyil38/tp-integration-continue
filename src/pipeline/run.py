"""Pipeline entry point: load each CSV, process it, insert the results."""

import argparse
import logging
from functools import partial
from pathlib import Path

from pipeline import db, s3
from pipeline.config import Settings
from pipeline.faults import flaky_db, flaky_s3
from pipeline.loader import content_checksum, parse_transactions
from pipeline.processing import process
from pipeline.sources import Source, local_source, s3_source

logger = logging.getLogger(__name__)


def run_pipeline(
    source: Source,
    connect_fn: db.ConnectFn,
    *,
    insert: db.InsertFn = db.insert_file_results,
    attempts: int = 3,
    wait_seconds: float = 1.0,
) -> dict[str, bool]:
    """Process every file of the source. Returns {file key: inserted?} (False = already done)."""
    with connect_fn() as conn:
        db.init_schema(conn)

    outcomes: dict[str, bool] = {}
    for file_key, content in source:
        result = process(parse_transactions(content, file_key))
        inserted = db.insert_with_retry(
            connect_fn,
            file_key,
            content_checksum(content),
            result,
            insert=insert,
            attempts=attempts,
            wait_seconds=wait_seconds,
        )
        outcomes[file_key] = inserted
        logger.info("%s: %s", file_key, "inserted" if inserted else "already processed, skipped")
    return outcomes


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the transaction pipeline")
    parser.add_argument("--source", choices=["s3", "local"], default="s3")
    parser.add_argument("--prefix", default="incoming/", help="S3 key prefix")
    parser.add_argument("--data-dir", type=Path, default=Path("data/incoming"), help="local source")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--wait-seconds", type=float, default=1.0)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.from_env()

    insert = db.insert_file_results
    if settings.simulate_db_failures:
        logger.warning("Simulating %d insertion failures", settings.simulate_db_failures)
        insert = flaky_db(insert, settings.simulate_db_failures)

    if args.source == "local":
        source = local_source(args.data_dir)
    else:
        fetch = s3.fetch_object
        if settings.simulate_s3_failures:
            logger.warning("Simulating %d S3 download failures", settings.simulate_s3_failures)
            fetch = flaky_s3(fetch, settings.simulate_s3_failures)
        source = s3_source(
            s3.make_client(settings),
            settings.s3_bucket,
            args.prefix,
            fetch=fetch,
            attempts=args.attempts,
            wait_seconds=args.wait_seconds,
        )

    run_pipeline(
        source,
        partial(db.connect, settings),
        insert=insert,
        attempts=args.attempts,
        wait_seconds=args.wait_seconds,
    )


if __name__ == "__main__":
    main()
