
import argparse
import csv
import uuid
import sqlite3

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

from src.storage import get_connection
from src.validation import validate_event
from src.customers import load_customers


DATABASE_PATH = Path("sample_data/benchmark_4worker.db")
MAX_WORKERS = 4


def read_events(input_file):
    """Read events from CSV."""

    with input_file.open(
        mode="r",
        newline="",
        encoding="utf-8",
    ) as file:
        return list(csv.DictReader(file))


def process_partition(
    partition_date,
    partition_events,
    run_id,
    customer_ids,
):
    """Process one daily partition using its own SQLite connection."""

    connection = get_connection(DATABASE_PATH)
    cursor = connection.cursor()

    accepted_count = 0
    rejected_count = 0

    try:
        connection.execute("BEGIN IMMEDIATE")

        cursor.execute(
            """
            SELECT status
            FROM backfill_partitions
            WHERE run_id = ?
              AND partition_date = ?
            """,
            (run_id, partition_date),
        )

        existing_partition = cursor.fetchone()

        if existing_partition and existing_partition[0] == "COMPLETED":
            connection.rollback()

            return {
                "partition_date": partition_date,
                "status": "SKIPPED",
                "accepted": 0,
                "rejected": 0,
            }

        cursor.execute(
            """
            INSERT INTO backfill_partitions (
                run_id,
                partition_date,
                status,
                input_count,
                accepted_count,
                rejected_count,
                started_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(run_id, partition_date)
            DO UPDATE SET
                status = excluded.status,
                input_count = excluded.input_count,
                accepted_count = 0,
                rejected_count = 0,
                error_message = NULL,
                started_at = excluded.started_at,
                completed_at = NULL
            """,
            (
                run_id,
                partition_date,
                "RUNNING",
                len(partition_events),
                0,
                0,
                datetime.now().isoformat(),
            ),
        )

        for event in partition_events:
            is_valid, result = validate_event(
                event,
                customer_ids,
            )

            if not is_valid:
                reason = result

                cursor.execute(
                    """
                    INSERT INTO rejected_records (
                        event_id,
                        customer_id,
                        event_date,
                        event_type,
                        amount,
                        rejection_reason
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.get("event_id"),
                        event.get("customer_id"),
                        event.get("event_date"),
                        event.get("event_type"),
                        event.get("amount"),
                        reason,
                    ),
                )

                rejected_count += 1
                continue

            normalized = result

            cursor.execute(
                """
                SELECT 1
                FROM target_events
                WHERE event_id = ?
                """,
                (normalized["event_id"],),
            )

            if cursor.fetchone():
                cursor.execute(
                    """
                    INSERT INTO rejected_records (
                        event_id,
                        customer_id,
                        event_date,
                        event_type,
                        amount,
                        rejection_reason
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.get("event_id"),
                        event.get("customer_id"),
                        event.get("event_date"),
                        event.get("event_type"),
                        event.get("amount"),
                        "Duplicate event_id",
                    ),
                )

                rejected_count += 1
                continue

            cursor.execute(
                """
                INSERT INTO target_events (
                    event_id,
                    customer_id,
                    event_date,
                    event_type,
                    amount
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    normalized["event_id"],
                    normalized["customer_id"],
                    normalized["event_date"],
                    normalized["event_type"],
                    normalized["amount"],
                ),
            )

            accepted_count += 1

        cursor.execute(
            """
            UPDATE backfill_partitions
            SET status = ?,
                accepted_count = ?,
                rejected_count = ?,
                completed_at = ?
            WHERE run_id = ?
              AND partition_date = ?
            """,
            (
                "COMPLETED",
                accepted_count,
                rejected_count,
                datetime.now().isoformat(),
                run_id,
                partition_date,
            ),
        )

        connection.commit()

        print(
            f"{partition_date}: "
            f"accepted={accepted_count}, "
            f"rejected={rejected_count}"
        )

        return {
            "partition_date": partition_date,
            "status": "COMPLETED",
            "accepted": accepted_count,
            "rejected": rejected_count,
        }

    except Exception as error:
        connection.rollback()

        try:
            cursor.execute(
                """
                UPDATE backfill_partitions
                SET status = ?,
                    error_message = ?,
                    completed_at = ?
                WHERE run_id = ?
                  AND partition_date = ?
                """,
                (
                    "FAILED",
                    str(error),
                    datetime.now().isoformat(),
                    run_id,
                    partition_date,
                ),
            )

            connection.commit()

        except sqlite3.Error:
            connection.rollback()

        print(
            f"Partition failed: {partition_date} "
            f"-> {error}"
        )

        return {
            "partition_date": partition_date,
            "status": "FAILED",
            "accepted": 0,
            "rejected": 0,
        }

    finally:
        connection.close()


def execute_backfill(
    input_file,
    start_date,
    end_date,
    run_id,
):
    """Execute historical backfill with bounded concurrency."""

    events = read_events(input_file)

    # FIX: Load customers before validating event records.
    load_customers()

    # Create the run and load customer IDs.
    connection = get_connection(DATABASE_PATH)
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT OR IGNORE INTO backfill_runs (
                run_id,
                start_date,
                end_date,
                status
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                run_id,
                start_date,
                end_date,
                "RUNNING",
            ),
        )

        cursor.execute(
            """
            SELECT customer_id
            FROM customers
            """
        )

        customer_ids = {
            row[0]
            for row in cursor.fetchall()
        }

        connection.commit()

    finally:
        connection.close()

    # Create daily partitions.
    partitions = {}
    invalid_date_events = []

    for event in events:
        event_date = event.get("event_date", "")

        try:
            parsed_date = date.fromisoformat(
                event_date.strip()
            )

        except (ValueError, AttributeError):
            invalid_date_events.append(event)
            continue

        partition_date = parsed_date.isoformat()

        if start_date <= partition_date <= end_date:
            partitions.setdefault(
                partition_date,
                [],
            ).append(event)

    # Store invalid-date records.
    connection = get_connection(DATABASE_PATH)
    cursor = connection.cursor()

    try:
        for event in invalid_date_events:
            reason = (
                "Invalid event_date; "
                "cannot assign daily partition"
            )

            cursor.execute(
                """
                SELECT 1
                FROM rejected_records
                WHERE event_id = ?
                  AND rejection_reason = ?
                LIMIT 1
                """,
                (
                    event.get("event_id"),
                    reason,
                ),
            )

            if cursor.fetchone():
                continue

            cursor.execute(
                """
                INSERT INTO rejected_records (
                    event_id,
                    customer_id,
                    event_date,
                    event_type,
                    amount,
                    rejection_reason
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.get("event_id"),
                    event.get("customer_id"),
                    event.get("event_date"),
                    event.get("event_type"),
                    event.get("amount"),
                    reason,
                ),
            )

        # Create partition tracking rows.
        for partition_date, partition_events in partitions.items():
            cursor.execute(
                """
                INSERT OR IGNORE INTO backfill_partitions (
                    run_id,
                    partition_date,
                    status,
                    input_count,
                    accepted_count,
                    rejected_count
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    partition_date,
                    "PENDING",
                    len(partition_events),
                    0,
                    0,
                ),
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    # Execute partitions concurrently.
    results = []

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:
        futures = {
            executor.submit(
                process_partition,
                partition_date,
                partition_events,
                run_id,
                customer_ids,
            ): partition_date
            for partition_date, partition_events
            in sorted(partitions.items())
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

    # Get final partition counts.
    connection = get_connection(DATABASE_PATH)
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                COUNT(*),
                SUM(
                    CASE
                        WHEN status = 'COMPLETED'
                        THEN 1
                        ELSE 0
                    END
                ),
                SUM(
                    CASE
                        WHEN status = 'FAILED'
                        THEN 1
                        ELSE 0
                    END
                ),
                COALESCE(SUM(accepted_count), 0),
                COALESCE(SUM(rejected_count), 0)
            FROM backfill_partitions
            WHERE run_id = ?
            """,
            (run_id,),
        )

        (
            total_partitions,
            completed_partitions,
            failed_partitions,
            total_accepted,
            total_rejected,
        ) = cursor.fetchone()

        completed_partitions = completed_partitions or 0
        failed_partitions = failed_partitions or 0

        final_status = (
            "FAILED"
            if failed_partitions > 0
            else "COMPLETED"
        )

        cursor.execute(
            """
            UPDATE backfill_runs
            SET status = ?,
                total_partitions = ?,
                completed_partitions = ?,
                failed_partitions = ?,
                updated_at = ?
            WHERE run_id = ?
            """,
            (
                final_status,
                total_partitions or 0,
                completed_partitions,
                failed_partitions,
                datetime.now().isoformat(),
                run_id,
            ),
        )

        connection.commit()

    finally:
        connection.close()

    # Print summary.
    print("\n========== BACKFILL SUMMARY ==========")

    print(f"Run ID             : {run_id}")
    print(f"Status             : {final_status}")
    print(f"Workers            : {MAX_WORKERS}")
    print(f"Partitions         : {total_partitions or 0}")
    print(f"Completed          : {completed_partitions}")
    print(f"Failed             : {failed_partitions}")
    print(f"Accepted           : {total_accepted}")
    print(f"Rejected           : {total_rejected}")
    print(
        f"Invalid date rows  : "
        f"{len(invalid_date_events)}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Execute historical backfill."
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=Path("sample_data/events_100k.csv"),
    )

    parser.add_argument(
        "--start-date",
        type=date.fromisoformat,
        required=True,
    )

    parser.add_argument(
        "--end-date",
        type=date.fromisoformat,
        required=True,
    )

    parser.add_argument(
        "--run-id",
        default=None,
    )

    args = parser.parse_args()

    if args.start_date > args.end_date:
        parser.error(
            "Start date cannot be after end date."
        )

    run_id = args.run_id or str(uuid.uuid4())

    execute_backfill(
        input_file=args.input,
        start_date=args.start_date.isoformat(),
        end_date=args.end_date.isoformat(),
        run_id=run_id,
    )


if __name__ == "__main__":
    main()
