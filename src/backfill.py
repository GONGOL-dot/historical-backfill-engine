
import argparse
import csv
from collections import Counter
from datetime import date
from pathlib import Path


def load_events(input_file):
    """Read events from a CSV file."""

    with input_file.open(
        mode="r",
        newline="",
        encoding="utf-8",
    ) as file:
        reader = csv.DictReader(file)
        return list(reader)


def create_daily_partitions(events):
    """Group events by event date."""

    partitions = {}

    for event in events:
        event_date = event.get("event_date", "").strip()

        try:
            parsed_date = date.fromisoformat(event_date)
        except (ValueError, TypeError):
            # Invalid dates cannot be assigned to a daily partition.
            continue

        partition_date = parsed_date.isoformat()

        if partition_date not in partitions:
            partitions[partition_date] = []

        partitions[partition_date].append(event)

    return partitions


def run_dry_run(input_file, start_date, end_date):
    """Estimate backfill workload without writing to the database."""

    events = load_events(input_file)

    partitions = create_daily_partitions(events)

    selected_partitions = {
        partition_date: partition_events
        for partition_date, partition_events in partitions.items()
        if start_date <= partition_date <= end_date
    }

    total_records = sum(
        len(partition_events)
        for partition_events in selected_partitions.values()
    )

    print("\n========== BACKFILL DRY RUN ==========")
    print(f"Input file       : {input_file}")
    print(f"Date range       : {start_date} to {end_date}")
    print(f"Total CSV records: {len(events)}")
    print(f"Selected records : {total_records}")
    print(f"Daily partitions : {len(selected_partitions)}")

    print("\nPartition details:")

    for partition_date in sorted(selected_partitions):
        count = len(selected_partitions[partition_date])

        print(
            f"{partition_date} -> {count} records"
        )

    print("\nDry run completed.")
    print("No database records were modified.")


def main():
    parser = argparse.ArgumentParser(
        description="Historical Backfill Engine"
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

    args = parser.parse_args()

    if args.start_date > args.end_date:
        parser.error("Start date cannot be after end date.")

    run_dry_run(
        input_file=args.input,
        start_date=args.start_date.isoformat(),
        end_date=args.end_date.isoformat(),
    )


if __name__ == "__main__":
    main()
