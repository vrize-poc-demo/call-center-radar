from importlib.resources import files

from app.database import Database


def migrate(database: Database) -> list[str]:
    """Apply every unapplied SQL migration in lexical version order."""
    applied: list[str] = []
    migration_files = sorted(
        (
            migration
            for migration in files("app").joinpath("migrations").iterdir()
            if migration.name.endswith(".sql")
        ),
        key=lambda migration: migration.name,
    )

    with database.connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        existing_versions = {
            row["version"] for row in connection.execute("SELECT version FROM schema_migrations")
        }

        for migration in migration_files:
            if migration.name in existing_versions:
                continue

            connection.executescript(migration.read_text())
            connection.execute(
                "INSERT INTO schema_migrations(version) VALUES (?)", (migration.name,)
            )
            applied.append(migration.name)

    return applied
