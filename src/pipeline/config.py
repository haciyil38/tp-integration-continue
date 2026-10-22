import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    user: str
    password: str
    dbname: str
    # Fault injection for the retry demo: number of insertion attempts that fail on purpose.
    simulate_db_failures: int

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        return cls(
            host=env.get("POSTGRES_HOST", "localhost"),
            port=int(env.get("POSTGRES_PORT", "5433")),
            user=env.get("POSTGRES_USER", "pipeline"),
            password=env.get("POSTGRES_PASSWORD", "pipeline"),
            dbname=env.get("POSTGRES_DB", "pipeline"),
            simulate_db_failures=int(env.get("SIMULATE_DB_FAILURES", "0")),
        )
