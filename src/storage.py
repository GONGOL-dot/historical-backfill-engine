
import sqlite3
from pathlib import Path


def get_connection(db_path):
    """
    Create a connection to the SQLite database.
    """

    db_path = Path(db_path)

    # Create the parent directory if it does not exist.
    db_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        str(db_path),
        timeout=30,
    )

    # Enable foreign key support.
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def initialize_database(db_path):
    """
    Create all required database tables.
    """

    connection = get_connection(db_path)

    try:
        cursor = connection.cursor()

        # 1. Customers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY,
                customer_name TEXT NOT NULL
            )
        """)

        # 2. Accepted event records
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS target_events (
                event_id TEXT PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                event_date TEXT NOT NULL,
                event_type TEXT NOT NULL,
                amount REAL NOT NULL,

                FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id)
            )
        """)

        # 3. Rejected event records
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rejected_records (
                reject_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT,
                customer_id TEXT,
                event_date TEXT,
                event_type TEXT,
                amount TEXT,
                rejection_reason TEXT NOT NULL,
                rejected_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 4. Backfill run information
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backfill_runs (
                run_id TEXT PRIMARY KEY,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                status TEXT NOT NULL,
                total_partitions INTEGER DEFAULT 0,
                completed_partitions INTEGER DEFAULT 0,
                failed_partitions INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 5. Daily partition information
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backfill_partitions (
                partition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                partition_date TEXT NOT NULL,
                status TEXT NOT NULL,
                input_count INTEGER DEFAULT 0,
                accepted_count INTEGER DEFAULT 0,
                rejected_count INTEGER DEFAULT 0,
                error_message TEXT,
                started_at TEXT,
                completed_at TEXT,

                FOREIGN KEY (run_id)
                REFERENCES backfill_runs(run_id),

                UNIQUE(run_id, partition_date)
            )
        """)

        connection.commit()

        print("Database initialized successfully!")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_table_names(db_path):
    """
    Return the names of all tables in the database.
    """

    connection = get_connection(db_path)

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
        """)

        return [
            row[0]
            for row in cursor.fetchall()
        ]

    finally:
        connection.close()


if __name__ == "__main__":

    database_path = Path(
        "sample_data/backfill.db"
    )

    initialize_database(database_path)

    print("\nCreated tables:")

    for table in get_table_names(database_path):
        print(table)
