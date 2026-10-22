"""Deterministic CSV generator: same fixtures, same bytes, every run."""

import argparse
import csv
from pathlib import Path

from pipeline import s3
from pipeline.config import Settings
from pipeline.models import CSV_COLUMNS

# name -> (iban, country, bank). All IBANs are fictitious.
ACCOUNTS = {
    "ALICE": ("FR7630001000010000000000A01", "FR", "BNP Paribas"),
    "BOB": ("FR7630002000020000000000B02", "FR", "Societe Generale"),
    "CARL": ("DE89370400440532013000", "DE", "Deutsche Bank"),
    "DIEGO": ("ES9121000418450200051332", "ES", "Santander"),
    "ELLA": ("GB29NWBK60161331926819", "GB", "NatWest"),
}

# (datetime, sender, receiver, amount). Amounts sit on both sides of the 5000 threshold
# (5000.00 is not flagged, 5000.01 is).
FIXTURES: dict[str, list[tuple[str, str, str, str]]] = {
    "transactions_001.csv": [
        ("2026-01-05T09:00:00", "ALICE", "BOB", "1200.00"),
        ("2026-01-05T10:30:00", "ALICE", "CARL", "300.50"),
        ("2026-01-05T11:15:00", "BOB", "ALICE", "5000.00"),
        ("2026-01-05T14:00:00", "CARL", "DIEGO", "7500.00"),
        ("2026-01-05T16:45:00", "DIEGO", "ELLA", "50.25"),
        ("2026-01-05T18:20:00", "BOB", "ELLA", "5000.01"),
    ],
    "transactions_002.csv": [
        ("2026-01-06T08:00:00", "ELLA", "ALICE", "15000.00"),
        ("2026-01-06T09:10:00", "ALICE", "BOB", "100.00"),
        ("2026-01-06T12:00:00", "CARL", "BOB", "4999.99"),
        ("2026-01-06T15:30:00", "ALICE", "DIEGO", "250.00"),
        ("2026-01-06T17:00:00", "DIEGO", "CARL", "6200.00"),
    ],
    "transactions_003.csv": [
        ("2026-01-07T09:00:00", "BOB", "CARL", "10.00"),
        ("2026-01-07T10:00:00", "BOB", "CARL", "20.00"),
        ("2026-01-07T11:00:00", "ALICE", "ELLA", "5001.00"),
        ("2026-01-07T12:00:00", "ELLA", "DIEGO", "75.50"),
        ("2026-01-07T13:00:00", "CARL", "ALICE", "8800.00"),
    ],
}


def _row(when: str, sender: str, receiver: str, amount: str) -> tuple[str, ...]:
    src_iban, src_country, src_bank = ACCOUNTS[sender]
    dst_iban, dst_country, _ = ACCOUNTS[receiver]
    return (when, src_iban, src_country, src_bank, dst_iban, dst_country, amount)


def generate_files(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, rows in FIXTURES.items():
        path = out_dir / name
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(CSV_COLUMNS)
            writer.writerows(_row(*r) for r in rows)
        paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate the deterministic transaction CSVs")
    parser.add_argument("--out-dir", type=Path, default=Path("data/incoming"))
    parser.add_argument("--s3", action="store_true", help="also upload the files to the S3 bucket")
    parser.add_argument("--prefix", default="incoming/", help="S3 key prefix")
    args = parser.parse_args(argv)

    paths = generate_files(args.out_dir)
    for path in paths:
        print(f"generated {path}")

    if args.s3:
        settings = Settings.from_env()
        keys = s3.upload_files(s3.make_client(settings), settings.s3_bucket, paths, args.prefix)
        for key in keys:
            print(f"uploaded s3://{settings.s3_bucket}/{key}")


if __name__ == "__main__":
    main()
