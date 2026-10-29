# Historical Backfill Engine

A Python-based historical data backfill engine designed to process large volumes of CSV event data, validate records, and load valid data into a SQLite database using partition-based processing.

## Project Overview

The Historical Backfill Engine supports reliable processing of historical event data. It reads CSV records, validates them, processes records by date-based partitions, and stores accepted and rejected records separately.

The project also supports multi-worker execution and tracks the status of each backfill run and partition.

## Features

- CSV-based historical data processing
- Date-based partitioning
- Data validation
- SQLite database integration
- Rejected-record tracking
- Duplicate event handling
- Backfill run and partition status tracking
- Multi-worker processing using `ThreadPoolExecutor`
- Partition-level transaction handling
- Automated tests using `pytest`
- Performance benchmarking for different worker counts

## Tech Stack

- Python
- SQLite
- CSV
- ThreadPoolExecutor
- Pytest

## Project Structure

```text
historical-backfill-engine/
│
├── src/
│   ├── executor.py
│   ├── storage.py
│   ├── validation.py
│   └── customers.py
│
├── scripts/
│   └── generate_data.py
│
├── sample_data/
│   └── events.csv
│
├── tests/
│
├── benchmark_results.csv
├── README.md
└── requirements.txt
```

## How It Works

1. Reads historical event records from a CSV file.
2. Validates each record.
3. Identifies invalid records and stores their rejection reasons.
4. Divides valid records into date-based partitions.
5. Processes partitions using configurable worker threads.
6. Stores accepted records in SQLite.
7. Tracks backfill run and partition status.
8. Generates a processing summary.

## Performance Benchmark

## Performance Benchmark

A benchmark was conducted using 100,000 records.

| Workers | Records | Execution Time | Throughput |
|---:|---:|---:|---:|
| 1 | 100,000 | 4.82 sec | 20,735.88 records/sec |
| 4 | 100,000 | 2.08 sec | 48,186.39 records/sec |

The four-worker run showed approximately **2.32x speedup** compared with the one-worker run in this benchmark.

*Note: Performance depends on hardware, database configuration, and workload. SQLite serializes database writes, so results may vary.*

## Testing

Run the test suite using:

```powershell
python -m pytest -v
```

## Future Improvements

- FastAPI-based REST API
- Web dashboard for monitoring backfill runs
- Configurable input files and worker counts
- Retry handling for failed partitions
- PostgreSQL support
- Cloud deployment

## Author

Developed as a Python data engineering project to demonstrate historical data processing, validation, partitioning, concurrency, and database management.
