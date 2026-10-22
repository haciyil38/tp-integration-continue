import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from pipeline.faults import flaky_s3
from pipeline.s3 import call_with_retry, is_transient
from pipeline.sources import s3_source


def client_error(status: int, code: str = "Err") -> ClientError:
    return ClientError(
        {"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}}, "GetObject"
    )


def test_network_errors_and_5xx_are_transient():
    assert is_transient(EndpointConnectionError(endpoint_url="http://x"))
    assert is_transient(client_error(503))


def test_missing_key_and_auth_errors_are_not_transient():
    assert not is_transient(client_error(404, "NoSuchKey"))
    assert not is_transient(client_error(403, "AccessDenied"))
    assert not is_transient(ValueError("boom"))


def test_call_succeeds_after_transient_failures():
    fetch = flaky_s3(lambda: b"data", failures=2)
    assert call_with_retry(fetch, attempts=3, wait_seconds=0) == b"data"


def test_call_raises_when_attempts_are_exhausted():
    fetch = flaky_s3(lambda: b"data", failures=5)
    with pytest.raises(EndpointConnectionError):
        call_with_retry(fetch, attempts=3, wait_seconds=0)


def test_call_does_not_retry_a_missing_key():
    calls = []

    def missing():
        calls.append(1)
        raise client_error(404, "NoSuchKey")

    with pytest.raises(ClientError):
        call_with_retry(missing, attempts=3, wait_seconds=0)
    assert len(calls) == 1


class FakeClient:
    """Just enough of the boto3 client for s3_source: one page of keys."""

    def __init__(self, keys):
        self.keys = keys

    def get_paginator(self, _name):
        return self

    def paginate(self, **_kwargs):
        return [{"Contents": [{"Key": k} for k in self.keys]}]


def test_s3_source_yields_csv_keys_in_order_and_retries_downloads():
    client = FakeClient(["in/b.csv", "in/a.csv", "in/readme.txt"])
    fetch = flaky_s3(lambda _client, _bucket, key: key.encode(), failures=2)

    files = list(s3_source(client, "bucket", "in/", fetch=fetch, attempts=3, wait_seconds=0))

    assert files == [("in/a.csv", b"in/a.csv"), ("in/b.csv", b"in/b.csv")]
