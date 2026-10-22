"""Where the CSV files come from. A source yields (file_key, content) one file at a time."""

from collections.abc import Callable, Iterator
from pathlib import Path

from pipeline import s3

Source = Iterator[tuple[str, bytes]]
FetchFn = Callable[[object, str, str], bytes]


def local_source(data_dir: Path) -> Source:
    for path in sorted(data_dir.glob("*.csv")):
        yield path.name, path.read_bytes()


def s3_source(
    client,
    bucket: str,
    prefix: str = "",
    *,
    fetch: FetchFn = s3.fetch_object,
    attempts: int = 3,
    wait_seconds: float = 1.0,
) -> Source:
    """Download the CSVs of a bucket, retrying listing and downloads on transient errors.

    The S3 key is the file key, so the same object is never processed twice (see db.py).
    """

    def retrying(fn):
        return s3.call_with_retry(fn, attempts=attempts, wait_seconds=wait_seconds)

    for key in retrying(lambda: s3.list_csv_keys(client, bucket, prefix)):
        yield key, retrying(lambda key=key: fetch(client, bucket, key))
