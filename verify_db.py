import sqlite3

db_path = "sample_data/backfill.db"

connection = sqlite3.connect(db_path)
cursor = connection.cursor()

target_count = cursor.execute(
    "SELECT COUNT(*) FROM target_events"
).fetchone()[0]

rejected_count = cursor.execute(
    "SELECT COUNT(*) FROM rejected_records"
).fetchone()[0]

completed_partitions = cursor.execute(
    "SELECT COUNT(*) FROM backfill_partitions WHERE status = 'COMPLETED'"
).fetchone()[0]

print("Target records:", target_count)
print("Rejected records:", rejected_count)
print("Completed partitions:", completed_partitions)

connection.close()