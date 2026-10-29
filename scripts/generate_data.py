
import csv
import random
from datetime import date, timedelta
from pathlib import Path

TOTAL_RECORDS = 100_000
START_DATE = date(2026, 1, 1)

OUTPUT_PATH = Path("sample_data/events_100k.csv")

CUSTOMER_IDS = list(range(1, 101))
EVENT_TYPES = ["purchase", "refund", "login", "subscription"]

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=[
            "event_id",
            "customer_id",
            "event_type",
            "amount",
            "event_date",
        ],
    )
    writer.writeheader()

    for i in range(1, TOTAL_RECORDS + 1):
        event_date = START_DATE + timedelta(days=random.randint(0, 89))

        writer.writerow(
            {
                "event_id": f"EVT-{i:06d}",
                "customer_id": random.choice(CUSTOMER_IDS),
                "event_type": random.choice(EVENT_TYPES),
                "amount": round(random.uniform(10, 5000), 2),
                "event_date": event_date.isoformat(),
            }
        )

print(f"Generated {TOTAL_RECORDS:,} records")
print(f"File: {OUTPUT_PATH}")
