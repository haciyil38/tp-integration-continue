"""Pipeline entry point: load each CSV, process it, insert the results."""

import argparse
import logging
from functools import partial
from pathlib import Path

from pipeline import db
from pipeline.config import Settings
from pipeline.faults import flaky
from pipeline.loader import file_checksum, load_transactions
from pipeline.processing import process

logger = logging.getLogger(__name__)


def run_pipeline(
    data_dir: Path,
    connect_fn: db.ConnectFn,
    *,
    insert: db.InsertFn = db.insert_file_results,
    attempts: int = 3,
    wait_seconds: float = 1.0,
) -> dict[str, bool]:
    """Process every CSV of data_dir. Returns {file name: inserted?} (False = already done)."""
    with connect_fn() as conn:
        db.init_schema(conn)

    outcomes: dict[str, bool] = {}
    for path in sorted(data_dir.glob("*.csv")):
        result = process(load_transactions(path))
        inserted = db.insert_with_retry(
            connect_fn,
            path.name,
            file_checksum(path),
            result,
            insert=insert,
            attempts=attempts,
            wait_seconds=wait_seconds,
        )
        outcomes[path.name] = inserted
        logger.info("%s: %s", path.name, "inserted" if inserted else "already processed, skipped")
    return outcomes


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the transaction pipeline")
    parser.add_argument("--data-dir", type=Path, default=Path("data/incoming"))
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--wait-seconds", type=float, default=1.0)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.from_env()
    insert = db.insert_file_results
    if settings.simulate_db_failures:
        logger.warning("Simulating %d insertion failures", settings.simulate_db_failures)
        insert = flaky(insert, settings.simulate_db_failures)

    run_pipeline(
        args.data_dir,
        partial(db.connect, settings),
        insert=insert,
        attempts=args.attempts,
        wait_seconds=args.wait_seconds,
    )


if __name__ == "__main__":
    main()
