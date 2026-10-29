
from datetime import date
from pathlib import Path
from uuid import uuid4
import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from src.executor import execute_backfill, DATABASE_PATH
from src.storage import initialize_database, get_connection


# Initialize database tables when the API starts
initialize_database(DATABASE_PATH)


app = FastAPI(
    title="Historical Backfill Engine API",
    description="API for executing historical data backfills.",
    version="1.0.0",
)


class BackfillRequest(BaseModel):
    input_file: str = "sample_data/events_100k.csv"
    start_date: date
    end_date: date
    run_id: str | None = None


# Redirect homepage to Swagger documentation
@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse(url="/docs")


# Execute historical backfill
@app.post("/backfill")
def start_backfill(request: BackfillRequest):

    # Validate date range
    if request.start_date > request.end_date:
        raise HTTPException(
            status_code=400,
            detail="Start date cannot be after end date.",
        )

    # Validate input file
    input_path = Path(request.input_file)

    if not input_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Input file not found: {request.input_file}",
        )

    # Generate run ID if not provided
    run_id = request.run_id or str(uuid4())

    try:
        execute_backfill(
            input_file=input_path,
            start_date=request.start_date.isoformat(),
            end_date=request.end_date.isoformat(),
            run_id=run_id,
        )

        return {
            "message": "Backfill execution completed.",
            "run_id": run_id,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# Get backfill run and partition details
@app.get("/backfill/{run_id}")
def get_backfill_status(run_id: str):

    connection = get_connection(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    try:
        cursor = connection.cursor()

        # Get backfill run details
        cursor.execute(
            """
            SELECT *
            FROM backfill_runs
            WHERE run_id = ?
            """,
            (run_id,),
        )

        run = cursor.fetchone()

        if run is None:
            raise HTTPException(
                status_code=404,
                detail=f"Backfill run not found: {run_id}",
            )

        # Get daily partition details
        cursor.execute(
            """
            SELECT
                partition_date,
                status,
                input_count,
                accepted_count,
                rejected_count,
                error_message
            FROM backfill_partitions
            WHERE run_id = ?
            ORDER BY partition_date
            """,
            (run_id,),
        )

        partitions = cursor.fetchall()

        return {
            "run": dict(run),
            "partitions": [
                dict(partition)
                for partition in partitions
            ],
        }

    finally:
        connection.close()
