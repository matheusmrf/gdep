import os
from typing import Iterable

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./integration_governance.db")

engine_kwargs = {}

if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def sync_schema():
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    if "users" not in table_names:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY,
                        name VARCHAR NOT NULL,
                        email VARCHAR NOT NULL UNIQUE,
                        password_hash VARCHAR NOT NULL,
                        password_salt VARCHAR NOT NULL,
                        failed_login_attempts INTEGER NOT NULL DEFAULT 0,
                        locked_until DATETIME,
                        cpi_host VARCHAR,
                        cpi_username VARCHAR,
                        cpi_password_encrypted VARCHAR,
                        cpi_tenant_id VARCHAR,
                        settings_updated_at DATETIME,
                        created_at DATETIME NOT NULL
                    )
                    """
                )
            )

    if "user_sessions" not in table_names:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        token_hash VARCHAR NOT NULL UNIQUE,
                        expires_at DATETIME NOT NULL,
                        created_at DATETIME NOT NULL
                    )
                    """
                )
            )

    if "tenants" not in table_names:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS tenants (
                        id INTEGER PRIMARY KEY,
                        name VARCHAR NOT NULL UNIQUE,
                        platform VARCHAR NOT NULL DEFAULT 'CPI',
                        cpi_host VARCHAR,
                        cpi_tenant_id VARCHAR,
                        created_at DATETIME NOT NULL
                    )
                    """
                )
            )

    if "integrations" not in table_names:
        ensure_indexes()
        return

    existing_columns = {column["name"] for column in inspector.get_columns("integrations")}
    alter_statements = []

    if "user_id" not in existing_columns:
        alter_statements.append("ALTER TABLE integrations ADD COLUMN user_id INTEGER")
    if "tenant_id" not in existing_columns:
        alter_statements.append("ALTER TABLE integrations ADD COLUMN tenant_id INTEGER")
    if "external_id" not in existing_columns:
        alter_statements.append("ALTER TABLE integrations ADD COLUMN external_id VARCHAR")
    if "external_source" not in existing_columns:
        alter_statements.append("ALTER TABLE integrations ADD COLUMN external_source VARCHAR")
    if "last_synced" not in existing_columns:
        alter_statements.append("ALTER TABLE integrations ADD COLUMN last_synced DATETIME")
    if "department" not in existing_columns:
        alter_statements.append("ALTER TABLE integrations ADD COLUMN department VARCHAR DEFAULT 'Operações'")

    if alter_statements:
        with engine.begin() as connection:
            for statement in alter_statements:
                connection.execute(text(statement))

    ensure_indexes()


def ensure_indexes():
    statements: Iterable[str] = (
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)",
        "CREATE INDEX IF NOT EXISTS idx_user_sessions_token_hash ON user_sessions (token_hash)",
        "CREATE INDEX IF NOT EXISTS idx_integrations_external_source_platform ON integrations (external_source, platform)",
        "CREATE INDEX IF NOT EXISTS idx_integrations_tenant_score ON integrations (tenant_id, score)",
        "CREATE INDEX IF NOT EXISTS idx_integrations_user_score ON integrations (user_id, score)",
    )
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
