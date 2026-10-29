from datetime import date
from decimal import Decimal, InvalidOperation


VALID_EVENT_TYPES = {
    "purchase",
    "refund",
    "login",
    "subscription",
}


def validate_event(row, customer_ids):
    """
    Validate one event.

    Returns:
        (True, normalized_event) for valid records
        (False, rejection_reason) for invalid records
    """

    # Validate event ID
    event_id = str(row.get("event_id", "")).strip()

    if not event_id:
        return False, "Missing event_id"

    # Validate customer ID
    customer_id_raw = str(
        row.get("customer_id", "")
    ).strip()

    if not customer_id_raw:
        return False, "Missing customer_id"

    try:
        customer_id = int(customer_id_raw)
    except (ValueError, TypeError):
        return False, "Invalid customer_id"

    if customer_id not in customer_ids:
        return False, "Unknown customer_id"

    # Validate event date
    event_date = str(
        row.get("event_date", "")
    ).strip()

    try:
        parsed_date = date.fromisoformat(event_date)
    except (ValueError, TypeError):
        return False, "Invalid event_date"

    # Validate event type
    event_type = str(
        row.get("event_type", "")
    ).strip().lower()

    if event_type not in VALID_EVENT_TYPES:
        return False, "Unsupported event_type"

    # Validate amount
    amount_raw = str(
        row.get("amount", "")
    ).strip()

    try:
        amount = Decimal(amount_raw)
    except (InvalidOperation, ValueError, TypeError):
        return False, "Non-numeric amount"

    if not amount.is_finite():
        return False, "Amount must be finite"

    if amount < 0:
        return False, "Negative amount"

    # Return normalized event when all validations pass
    normalized_event = {
        "event_id": event_id,
        "customer_id": customer_id,
        "event_date": parsed_date.isoformat(),
        "event_type": event_type,
        "amount": float(amount),
    }

    return True, normalized_event