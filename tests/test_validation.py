
from src.validation import validate_event


VALID_CUSTOMERS = {10, 20, 30}


def valid_event():
    return {
        "event_id": "EVT000001",
        "customer_id": "10",
        "event_date": "2026-01-15",
        "event_type": "purchase",
        "amount": "250.50",
    }


def test_valid_event():
    row = valid_event()

    is_valid, result = validate_event(
        row,
        VALID_CUSTOMERS,
    )

    assert is_valid is True
    assert result["customer_id"] == 10
    assert result["amount"] == 250.50


def test_missing_customer_id():
    row = valid_event()
    row["customer_id"] = ""

    is_valid, reason = validate_event(
        row,
        VALID_CUSTOMERS,
    )

    assert is_valid is False
    assert reason == "Missing customer_id"


def test_invalid_date():
    row = valid_event()
    row["event_date"] = "invalid-date"

    is_valid, reason = validate_event(
        row,
        VALID_CUSTOMERS,
    )

    assert is_valid is False
    assert reason == "Invalid event_date"


def test_negative_amount():
    row = valid_event()
    row["amount"] = "-100"

    is_valid, reason = validate_event(
        row,
        VALID_CUSTOMERS,
    )

    assert is_valid is False
    assert reason == "Negative amount"


def test_invalid_event_type():
    row = valid_event()
    row["event_type"] = "invalid_event"

    is_valid, reason = validate_event(
        row,
        VALID_CUSTOMERS,
    )

    assert is_valid is False
    assert reason == "Unsupported event_type"


def test_unknown_customer():
    row = valid_event()
    row["customer_id"] = "9999"

    is_valid, reason = validate_event(
        row,
        VALID_CUSTOMERS,
    )

    assert is_valid is False
    assert reason == "Unknown customer_id"


def test_non_numeric_amount():
    row = valid_event()
    row["amount"] = "not_a_number"

    is_valid, reason = validate_event(
        row,
        VALID_CUSTOMERS,
    )

    assert is_valid is False
    assert reason == "Non-numeric amount"
