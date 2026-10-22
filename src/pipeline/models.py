from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

CSV_COLUMNS = (
    "datetime",
    "iban_origine",
    "pays_source",
    "banque_source",
    "iban_destinataire",
    "pays_destinataire",
    "montant",
)


@dataclass(frozen=True)
class Transaction:
    datetime: datetime
    iban_origine: str
    pays_source: str
    banque_source: str
    iban_destinataire: str
    pays_destinataire: str
    montant: Decimal


@dataclass(frozen=True)
class FlaggedTransaction:
    transaction: Transaction
    flagged: bool


@dataclass(frozen=True)
class ProcessingResult:
    transactions: tuple[FlaggedTransaction, ...]
    sent_by_iban: dict[str, Decimal]
    sent_by_bank: dict[str, Decimal]
    received_by_iban: dict[str, Decimal]
