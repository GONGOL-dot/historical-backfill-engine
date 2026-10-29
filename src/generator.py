
import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path


def generate_events(
    records: int,
    start_date: date,
    end_date: date,
    output: Path,
    seed: int = 42,
):
    if records < 1:
        raise ValueError("Records must be greater than zero.")

    if start_date > end_date:
        raise ValueError("Start date cannot be after end date.")

    random.seed(seed)

    output.parent.mkdir(parents=True, exist_ok=True)

    date_range = (end_date - start_date).days

    rows = []

    for i in range(records):
        event_date = start_date + timedelta(
            days=random.randint(0, date_range)
        )

        row = {
            "event_id": f"EVT{i + 1:06d}",
            "customer_id": random.randint(1, 100),
            "event_date": event_date.isoformat(),
            "event_type": random.choice(
                ["purchase", "refund", "login", "subscription"]
            ),
            "amount": round(random.uniform(10, 5000), 2),
        }

        rows.append(row)

    # Inject data-quality examples for testing.
    # These are applied only when the corresponding rows exist.

    if records >= 1:
        rows[0]["customer_id"] = ""

    if records >= 2:
        rows[1]["amount"] = -100

    if records >= 3:
        rows[2]["event_type"] = "invalid_event"

    if records >= 4:
        rows[3]["amount"] = "not_a_number"

    if records >= 5:
        rows[4]["customer_id"] = 9999

    if records >= 6:
        rows[5]["event_date"] = "invalid-date"

    # Inject a duplicate event ID.
    if records >= 7:
        rows[6]["event_id"] = rows[5]["event_id"]

    fieldnames = [
        "event_id",
        "customer_id",
        "event_date",
        "event_type",
        "amount",
    ]

    with output.open(
        mode="w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)

    print("Sample data generated successfully!")
    print(f"Total records: {records}")
    print(f"Output file: {output}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate sample historical event data."
    )

    parser.add_argument(
        "--records",
        type=int,
        default=1000,
        help="Number of records to generate.",
    )

    parser.add_argument(
        "--start-date",
        type=date.fromisoformat,
        default=date(2026, 1, 1),
        help="Start date in YYYY-MM-DD format.",
    )

    parser.add_argument(
        "--end-date",
        type=date.fromisoformat,
        default=date(2026, 1, 30),
        help="End date in YYYY-MM-DD format.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("sample_data/events.csv"),
        help="Output CSV file path.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )

    args = parser.parse_args()

    generate_events(
        records=args.records,
        start_date=args.start_date,
        end_date=args.end_date,
        output=args.output,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
