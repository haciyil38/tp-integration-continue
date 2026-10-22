-- One row per CSV file already handled. Inserted in the same transaction as the results,
-- so a failed insertion leaves no marker and can be retried safely.
CREATE TABLE IF NOT EXISTS processed_files (
    file_key     TEXT PRIMARY KEY,
    checksum     TEXT NOT NULL UNIQUE,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS transactions (
    id                   BIGSERIAL PRIMARY KEY,
    file_key             TEXT NOT NULL REFERENCES processed_files(file_key) ON DELETE CASCADE,
    transaction_datetime TIMESTAMP NOT NULL,
    iban_origine         TEXT NOT NULL,
    pays_source          TEXT NOT NULL,
    banque_source        TEXT NOT NULL,
    iban_destinataire    TEXT NOT NULL,
    pays_destinataire    TEXT NOT NULL,
    montant              NUMERIC(14, 2) NOT NULL,
    flagged              BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS sent_by_iban (
    file_key TEXT NOT NULL REFERENCES processed_files(file_key) ON DELETE CASCADE,
    iban     TEXT NOT NULL,
    total    NUMERIC(16, 2) NOT NULL,
    PRIMARY KEY (file_key, iban)
);

CREATE TABLE IF NOT EXISTS sent_by_bank (
    file_key TEXT NOT NULL REFERENCES processed_files(file_key) ON DELETE CASCADE,
    bank     TEXT NOT NULL,
    total    NUMERIC(16, 2) NOT NULL,
    PRIMARY KEY (file_key, bank)
);

CREATE TABLE IF NOT EXISTS received_by_iban (
    file_key TEXT NOT NULL REFERENCES processed_files(file_key) ON DELETE CASCADE,
    iban     TEXT NOT NULL,
    total    NUMERIC(16, 2) NOT NULL,
    PRIMARY KEY (file_key, iban)
);
