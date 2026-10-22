from decimal import Decimal

import pytest

from pipeline.generate import generate_files
from pipeline.loader import file_checksum, load_transactions


def test_generation_is_deterministic(tmp_path):
    first = generate_files(tmp_path / "a")
    second = generate_files(tmp_path / "b")
    assert [p.name for p in first] == [p.name for p in second]
    assert [p.read_bytes() for p in first] == [p.read_bytes() for p in second]


def test_each_file_has_5_to_10_transactions(tmp_path):
    paths = generate_files(tmp_path)
    assert len(paths) >= 2
    for path in paths:
        assert 5 <= len(load_transactions(path)) <= 10


def test_load_first_file(tmp_path):
    path = generate_files(tmp_path)[0]
    transactions = load_transactions(path)
    assert transactions[0].iban_origine == "FR7630001000010000000000A01"
    assert transactions[0].banque_source == "BNP Paribas"
    assert transactions[0].montant == Decimal("1200.00")


def test_checksum_depends_on_content(tmp_path):
    first, second = generate_files(tmp_path)[:2]
    assert file_checksum(first) == file_checksum(first)
    assert file_checksum(first) != file_checksum(second)


def test_load_rejects_unexpected_columns(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError, match="unexpected columns"):
        load_transactions(bad)
