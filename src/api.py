
from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from src.executor import execute_backfill, DATABASE_PATH
from src.storage import initialize_database


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
