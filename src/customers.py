
from pathlib import Path

from src.storage import get_connection


DATABASE_PATH = Path("sample_data/benchmark_4worker.db")


def load_customers():
    """Load 100 sample customers into the database."""

    connection = get_connection(DATABASE_PATH)

    try:
        cursor = connection.cursor()

        for customer_id in range(1, 101):
            cursor.execute(
                """
                INSERT OR IGNORE INTO customers (
                    customer_id,
                    customer_name
                )
                VALUES (?, ?)
                """,
                (
                    customer_id,
                    f"Customer {customer_id}",
                ),
            )

        connection.commit()

        print("Customer records loaded successfully!")

        cursor.execute(
            "SELECT COUNT(*) FROM customers"
        )

        total_customers = cursor.fetchone()[0]

        print(f"Total customers in database: {total_customers}")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    load_customers()
