"""Data loading (I/O). Kept apart from the pure processing functions."""

import csv
import hashlib
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pipeline.models import CSV_COLUMNS, Transaction


def load_transactions(path: Path) -> list[Transaction]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != CSV_COLUMNS:
            raise ValueError(f"{path.name}: unexpected columns {reader.fieldnames}")
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


def file_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
