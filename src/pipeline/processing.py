"""Pure processing functions: no I/O, no clock, no randomness."""

from collections.abc import Callable, Iterable
from decimal import Decimal

from pipeline.models import FlaggedTransaction, ProcessingResult, Transaction

LARGE_AMOUNT_THRESHOLD = Decimal("5000")


def _sum_by(
    transactions: Iterable[Transaction], key: Callable[[Transaction], str]
) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for transaction in transactions:
        k = key(transaction)
        totals[k] = totals.get(k, Decimal("0")) + transaction.montant
    return totals


def sum_sent_by_iban(transactions: Iterable[Transaction]) -> dict[str, Decimal]:
    return _sum_by(transactions, lambda t: t.iban_origine)


def sum_sent_by_bank(transactions: Iterable[Transaction]) -> dict[str, Decimal]:
    return _sum_by(transactions, lambda t: t.banque_source)


def sum_received_by_iban(transactions: Iterable[Transaction]) -> dict[str, Decimal]:
    return _sum_by(transactions, lambda t: t.iban_destinataire)


def flag_transactions(
    transactions: Iterable[Transaction], threshold: Decimal = LARGE_AMOUNT_THRESHOLD
) -> tuple[FlaggedTransaction, ...]:
    """Flag every transaction whose amount is strictly above the threshold."""
    return tuple(FlaggedTransaction(t, t.montant > threshold) for t in transactions)


def process(
    transactions: Iterable[Transaction], threshold: Decimal = LARGE_AMOUNT_THRESHOLD
) -> ProcessingResult:
    transactions = tuple(transactions)
    return ProcessingResult(
        transactions=flag_transactions(transactions, threshold),
        sent_by_iban=sum_sent_by_iban(transactions),
        sent_by_bank=sum_sent_by_bank(transactions),
        received_by_iban=sum_received_by_iban(transactions),
    )
