import argparse
import json

from app.config import Settings
from app.database import Database
from app.logging import configure_logging, log_event
from app.migrator import migrate
from app.seed import seed_sample_metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Call Center Radar local workflow commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("migrate", help="Create and migrate the local SQLite database")
    seed_parser = subparsers.add_parser("seed", help="Seed metadata from the bundled sample set")
    seed_parser.add_argument(
        "--limit", type=int, default=5, help="Maximum metadata records to seed"
    )
    args = parser.parse_args()

    settings = Settings.from_environment()
    logger = configure_logging(settings.log_level)
    database = Database(settings.database_path)
    applied = migrate(database)

    if args.command == "migrate":
        log_event(logger, "database_migrated", "SQLite migrations completed")
        print(json.dumps({"database": str(settings.database_path), "applied": applied}))
        return

    seeded = seed_sample_metadata(database, settings.sample_data_dir, args.limit)
    log_event(logger, "sample_metadata_seeded", "Sample metadata seed completed")
    print(json.dumps({"database": str(settings.database_path), "seeded": seeded}))


if __name__ == "__main__":
    main()
