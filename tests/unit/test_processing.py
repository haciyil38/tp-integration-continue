from datetime import datetime
from decimal import Decimal

from pipeline.models import Transaction
from pipeline.processing import (
    flag_transactions,
    process,
    sum_received_by_iban,
    sum_sent_by_bank,
    sum_sent_by_iban,
)


def tx(sender, bank, receiver, amount):
    return Transaction(
        datetime=datetime(2026, 1, 1),
        iban_origine=sender,
        pays_source="FR",
        banque_source=bank,
        iban_destinataire=receiver,
        pays_destinataire="FR",
        montant=Decimal(amount),
    )


TXS = [
    tx("A", "Bank1", "B", "100.00"),
    tx("A", "Bank1", "C", "50.50"),
    tx("B", "Bank2", "A", "5000.00"),
    tx("C", "Bank1", "B", "5000.01"),
]


def test_sum_sent_by_iban():
    assert sum_sent_by_iban(TXS) == {
        "A": Decimal("150.50"),
        "B": Decimal("5000.00"),
        "C": Decimal("5000.01"),
    }


def test_sum_sent_by_bank():
    assert sum_sent_by_bank(TXS) == {"Bank1": Decimal("5150.51"), "Bank2": Decimal("5000.00")}


def test_sum_received_by_iban():
    assert sum_received_by_iban(TXS) == {
        "B": Decimal("5100.01"),
        "C": Decimal("50.50"),
        "A": Decimal("5000.00"),
    }


def test_flag_is_strictly_above_threshold():
    flags = [f.flagged for f in flag_transactions(TXS)]
    assert flags == [False, False, False, True]  # 5000.00 is not flagged, 5000.01 is


def test_flag_custom_threshold():
    flags = [f.flagged for f in flag_transactions(TXS, threshold=Decimal("100"))]
    assert flags == [False, False, True, True]


def test_empty_input():
    result = process([])
    assert result.transactions == ()
    assert result.sent_by_iban == result.sent_by_bank == result.received_by_iban == {}


def test_process_does_not_mutate_input():
    txs = list(TXS)
    process(txs)
    assert txs == TXS
