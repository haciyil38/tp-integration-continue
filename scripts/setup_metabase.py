#!/usr/bin/env python3
"""Provision Metabase: admin account, Postgres connection, questions and the dashboard.

Idempotent: safe to run again, existing objects are kept. Standard library only.

    docker compose --profile dashboard up -d
    python scripts/setup_metabase.py
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

URL = os.environ.get("METABASE_URL", "http://localhost:3000").rstrip("/")
EMAIL = os.environ.get("METABASE_ADMIN_EMAIL", "admin@example.com")
PASSWORD = os.environ.get("METABASE_ADMIN_PASSWORD", "Pipeline-Passw0rd!")

# Seen from the Metabase container, i.e. inside the compose network (not localhost:5433).
DB_DETAILS = {
    "host": os.environ.get("METABASE_DB_HOST", "postgres"),
    "port": int(os.environ.get("METABASE_DB_PORT", "5432")),
    "dbname": os.environ.get("POSTGRES_DB", "pipeline"),
    "user": os.environ.get("POSTGRES_USER", "pipeline"),
    "password": os.environ.get("POSTGRES_PASSWORD", "pipeline"),
    "ssl": False,
}
DB_NAME = "Pipeline"
DASHBOARD_NAME = "Pipeline transactions"

BAR_IBAN = {"graph.dimensions": ["iban"], "graph.metrics": ["total"]}

# (name, display, sql, visualization_settings)
CARDS = [
    ("Transactions traitées", "scalar", "SELECT count(*) AS transactions FROM transactions", {}),
    (
        "Transactions flaggées (> 5000)",
        "scalar",
        "SELECT count(*) AS flaggees FROM transactions WHERE flagged",
        {},
    ),
    ("Montant total", "scalar", "SELECT sum(montant) AS montant_total FROM transactions", {}),
    (
        "Total envoyé par IBAN origine",
        "bar",
        "SELECT iban, sum(total) AS total FROM sent_by_iban GROUP BY iban ORDER BY total DESC",
        BAR_IBAN,
    ),
    (
        "Total envoyé par banque source",
        "pie",
        "SELECT bank, sum(total) AS total FROM sent_by_bank GROUP BY bank ORDER BY total DESC",
        {"pie.dimension": "bank", "pie.metric": "total"},
    ),
    (
        "Total reçu par IBAN",
        "bar",
        "SELECT iban, sum(total) AS total FROM received_by_iban GROUP BY iban ORDER BY total DESC",
        BAR_IBAN,
    ),
    (
        "Fichiers traités",
        "table",
        "SELECT file_key AS fichier, processed_at AS traite_le, left(checksum, 12) AS checksum "
        "FROM processed_files ORDER BY file_key",
        {},
    ),
    (
        "Transactions flaggées",
        "table",
        "SELECT transaction_datetime AS date, iban_origine, banque_source, iban_destinataire, "
        "montant, file_key AS fichier FROM transactions WHERE flagged ORDER BY montant DESC",
        {},
    ),
]

# card name -> (col, row, width, height) on Metabase's 24-column grid
LAYOUT = {
    "Transactions traitées": (0, 0, 8, 3),
    "Transactions flaggées (> 5000)": (8, 0, 8, 3),
    "Montant total": (16, 0, 8, 3),
    "Total envoyé par IBAN origine": (0, 3, 12, 7),
    "Total envoyé par banque source": (12, 3, 12, 7),
    "Total reçu par IBAN": (0, 10, 12, 7),
    "Fichiers traités": (12, 10, 12, 7),
    "Transactions flaggées": (0, 17, 24, 8),
}


def api(method: str, path: str, body=None, session: str | None = None):
    headers = {"Content-Type": "application/json"}
    if session:
        headers["X-Metabase-Session"] = session
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(f"{URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        sys.exit(f"{method} {path} -> HTTP {error.code}: {error.read().decode()[:500]}")


def wait_until_up(timeout: int = 300) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{URL}/api/health", timeout=5) as response:
                if json.loads(response.read()).get("status") == "ok":
                    return
        except (urllib.error.URLError, OSError, ValueError):
            pass
        time.sleep(3)
    sys.exit(f"Metabase not reachable at {URL} after {timeout}s (docker compose logs metabase)")


def get_session() -> str:
    properties = api("GET", "/api/session/properties")
    if not properties.get("has-user-setup"):
        token = properties["setup-token"]
        print("First start: creating the admin account")
        api(
            "POST",
            "/api/setup",
            {
                "token": token,
                "user": {
                    "first_name": "Admin",
                    "last_name": "Pipeline",
                    "email": EMAIL,
                    "password": PASSWORD,
                },
                "prefs": {"site_name": "Pipeline transactions", "allow_tracking": False},
            },
        )
    return api("POST", "/api/session", {"username": EMAIL, "password": PASSWORD})["id"]


def items(payload) -> list:
    return payload["data"] if isinstance(payload, dict) else payload


def ensure_database(session: str) -> int:
    for db in items(api("GET", "/api/database", session=session)):
        if db["name"] == DB_NAME:
            return db["id"]
    created = api(
        "POST",
        "/api/database",
        {"engine": "postgres", "name": DB_NAME, "details": DB_DETAILS, "is_full_sync": True},
        session,
    )
    print(f"Database '{DB_NAME}' connected")
    return created["id"]


def ensure_cards(session: str, database_id: int) -> dict[str, int]:
    existing = {c["name"]: c["id"] for c in api("GET", "/api/card", session=session)}
    ids = {}
    for name, display, sql, settings in CARDS:
        if name in existing:
            ids[name] = existing[name]
            continue
        card = api(
            "POST",
            "/api/card",
            {
                "name": name,
                "display": display,
                "visualization_settings": settings,
                "dataset_query": {
                    "type": "native",
                    "database": database_id,
                    "native": {"query": sql},
                },
            },
            session,
        )
        ids[name] = card["id"]
        print(f"Question created: {name}")
    return ids


def ensure_dashboard(session: str, card_ids: dict[str, int]) -> int:
    for dashboard in items(api("GET", "/api/dashboard", session=session)):
        if dashboard["name"] == DASHBOARD_NAME:
            return dashboard["id"]
    dashboard = api(
        "POST",
        "/api/dashboard",
        {"name": DASHBOARD_NAME, "description": "Résultats de la pipeline CSV -> S3 -> Postgres"},
        session,
    )
    dashcards = [
        {
            "id": -(i + 1),
            "card_id": card_ids[name],
            "col": col,
            "row": row,
            "size_x": width,
            "size_y": height,
            "parameter_mappings": [],
            "visualization_settings": {},
        }
        for i, (name, (col, row, width, height)) in enumerate(LAYOUT.items())
    ]
    api("PUT", f"/api/dashboard/{dashboard['id']}", {"dashcards": dashcards}, session)
    print(f"Dashboard '{DASHBOARD_NAME}' created")
    return dashboard["id"]


def main() -> None:
    wait_until_up()
    session = get_session()
    database_id = ensure_database(session)
    dashboard_id = ensure_dashboard(session, ensure_cards(session, database_id))
    print(f"\nDashboard ready: {URL}/dashboard/{dashboard_id}")
    print(f"Login: {EMAIL} / {PASSWORD}")


if __name__ == "__main__":
    main()
