"""Data loading. Kept apart from the pure processing functions."""

import csv
import hashlib
import io
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pipeline.models import CSV_COLUMNS, Transaction


def parse_transactions(content: bytes, name: str) -> list[Transaction]:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8"), newline=""))
    if tuple(reader.fieldnames or ()) != CSV_COLUMNS:
        raise ValueError(f"{name}: unexpected columns {reader.fieldnames}")
    return [
        Transaction(
            datetime=datetime.fromisoformat(row["datetime"]),
            iban_origine=row["iban_origine"],
            pays_source=row["pays_source"],
            banque_source=row["banque_source"],
            iban_destinataire=row["iban_destinataire"],
            pays_destinataire=row["pays_destinataire"],
            montant=Decimal(row["montant"]),
        )
        for row in reader
    ]


def content_checksum(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def load_transactions(path: Path) -> list[Transaction]:
    return parse_transactions(path.read_bytes(), path.name)


def file_checksum(path: Path) -> str:
    return content_checksum(path.read_bytes())
