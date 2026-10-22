"""S3 access (Garage locally). Every call that can fail transiently goes through call_with_retry."""

import logging
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TypeVar

import boto3
from botocore.config import Config
from botocore.exceptions import (
    ClientError,
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)
from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from pipeline.config import Settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

_NETWORK_ERRORS = (
    EndpointConnectionError,
    ConnectionClosedError,
    ConnectTimeoutError,
    ReadTimeoutError,
)


def make_client(settings: Settings):
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        # boto3's own hidden retries are disabled: retrying is done (and logged) by us.
        config=Config(
            s3={"addressing_style": "path"},
            retries={"max_attempts": 1},
            connect_timeout=5,
            read_timeout=10,
        ),
    )


def is_transient(error: BaseException) -> bool:
    """Network problems and 5xx are worth retrying; a missing key or bad credentials are not."""
    if isinstance(error, _NETWORK_ERRORS):
        return True
    if isinstance(error, ClientError):
        return error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0) >= 500
    return False


def call_with_retry(fn: Callable[[], T], *, attempts: int = 3, wait_seconds: float = 1.0) -> T:
    for attempt in Retrying(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=wait_seconds),
        retry=retry_if_exception(is_transient),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    ):
        with attempt:
            return fn()
    raise AssertionError("unreachable")  # pragma: no cover


def upload_files(client, bucket: str, paths: Iterable[Path], prefix: str = "") -> list[str]:
    keys = []
    for path in paths:
        key = f"{prefix}{path.name}"
        client.put_object(Bucket=bucket, Key=key, Body=path.read_bytes())
        keys.append(key)
    return keys


def list_csv_keys(client, bucket: str, prefix: str = "") -> list[str]:
    keys = []
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))
    return sorted(k for k in keys if k.endswith(".csv"))


def fetch_object(client, bucket: str, key: str) -> bytes:
    return client.get_object(Bucket=bucket, Key=key)["Body"].read()
