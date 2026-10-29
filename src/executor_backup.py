
import argparse
import csv
import uuid

from datetime import date, datetime
from pathlib import Path

from src.storage import get_connection
from src.validation import validate_event


DATABASE_PATH = Path("sample_data/backfill.db")


def read_events(input_file):
    """Read events from CSV."""

    with input_file.open(
        mode="r",
        newline="",
        encoding="utf-8",
    ) as file:
        return list(csv.DictReader(file))


def execute_backfill(
    input_file,
    start_date,
    end_date,
    run_id,
):
    events = read_events(input_file)

    connection = get_connection(DATABASE_PATH)
    cursor = connection.cursor()

    try:
        # Load valid customer IDs.
        cursor.execute(
            "SELECT customer_id FROM customers"
        )

        customer_ids = {
            row[0] for row in cursor.fetchall()
        }

        # Create backfill run if it does not exist.
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

        connection.commit()

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

        total_accepted = 0
        total_rejected = 0
        completed_partitions = 0
        failed_partitions = 0

        # Store malformed-date records in quarantine.
        # Avoid inserting the same malformed event repeatedly.
        for event in invalid_date_events:

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
                    "Invalid event_date; cannot assign daily partition",
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
                    "Invalid event_date; cannot assign daily partition",
                ),
            )

        connection.commit()

        # Execute daily partitions.
        for partition_date in sorted(partitions):

            partition_events = partitions[partition_date]

            # Skip already completed partitions.
            cursor.execute(
                """
                SELECT status
                FROM backfill_partitions
                WHERE run_id = ?
                  AND partition_date = ?
                """,
                (
                    run_id,
                    partition_date,
                ),
            )

            existing_partition = cursor.fetchone()

            if (
                existing_partition
                and existing_partition[0] == "COMPLETED"
            ):
                print(
                    f"Skipping completed partition: "
                    f"{partition_date}"
                )

                completed_partitions += 1
                continue

            partition_accepted = 0
            partition_rejected = 0

            try:
                # Create or reset partition tracking.
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

                connection.commit()

                # Process events in the partition.
                for event in partition_events:

                    is_valid, result = validate_event(
                        event,
                        customer_ids,
                    )

                    # Invalid event -> quarantine.
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

                        partition_rejected += 1
                        continue

                    normalized = result

                    # Check duplicate event ID.
                    cursor.execute(
                        """
                        SELECT 1
                        FROM target_events
                        WHERE event_id = ?
                        """,
                        (
                            normalized["event_id"],
                        ),
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

                        partition_rejected += 1
                        continue

                    # Insert valid event into target.
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

                    partition_accepted += 1

                connection.commit()

                # Mark partition as completed.
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
                        partition_accepted,
                        partition_rejected,
                        datetime.now().isoformat(),
                        run_id,
                        partition_date,
                    ),
                )

                connection.commit()

                total_accepted += partition_accepted
                total_rejected += partition_rejected
                completed_partitions += 1

                print(
                    f"{partition_date}: "
                    f"accepted={partition_accepted}, "
                    f"rejected={partition_rejected}"
                )

            except Exception as error:

                connection.rollback()

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

                failed_partitions += 1

                print(
                    f"Partition failed: {partition_date} "
                    f"-> {error}"
                )

        # Update final run status.
        final_status = (
            "FAILED"
            if failed_partitions
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
                len(partitions),
                completed_partitions,
                failed_partitions,
                datetime.now().isoformat(),
                run_id,
            ),
        )

        connection.commit()

        # Print summary.
        print("\n========== BACKFILL SUMMARY ==========")

        print(f"Run ID             : {run_id}")
        print(f"Status             : {final_status}")
        print(f"Partitions         : {len(partitions)}")
        print(f"Completed          : {completed_partitions}")
        print(f"Failed             : {failed_partitions}")
        print(f"Accepted           : {total_accepted}")
        print(f"Rejected           : {total_rejected}")

        print(
            f"Invalid date rows  : "
            f"{len(invalid_date_events)}"
        )

    finally:
        connection.close()


def main():

    parser = argparse.ArgumentParser(
        description="Execute historical backfill."
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=Path("sample_data/events.csv"),
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
