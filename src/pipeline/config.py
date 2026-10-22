import os
from dataclasses import dataclass
from pathlib import Path


def _read_dotenv(path: Path) -> dict[str, str]:
    """Minimal .env reader (KEY=VALUE lines). Real environment variables take precedence."""
    if not path.is_file():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    user: str
    password: str
    dbname: str
    s3_endpoint: str
    s3_region: str
    s3_bucket: str
    s3_access_key: str
    s3_secret_key: str
    # Fault injection for the retry demos: number of attempts that fail on purpose.
    simulate_db_failures: int
    simulate_s3_failures: int

    @classmethod
    def from_env(cls) -> "Settings":
        env = {**_read_dotenv(Path(".env")), **os.environ}
        return cls(
            host=env.get("POSTGRES_HOST", "localhost"),
            port=int(env.get("POSTGRES_PORT", "5433")),
            user=env.get("POSTGRES_USER", "pipeline"),
            password=env.get("POSTGRES_PASSWORD", "pipeline"),
            dbname=env.get("POSTGRES_DB", "pipeline"),
            s3_endpoint=env.get("S3_ENDPOINT", "http://localhost:3900"),
            s3_region=env.get("S3_REGION", "garage"),
            s3_bucket=env.get("S3_BUCKET", "transactions"),
            s3_access_key=env.get("S3_ACCESS_KEY", ""),
            s3_secret_key=env.get("S3_SECRET_KEY", ""),
            simulate_db_failures=int(env.get("SIMULATE_DB_FAILURES", "0")),
            simulate_s3_failures=int(env.get("SIMULATE_S3_FAILURES", "0")),
        )
