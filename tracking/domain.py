"""Validation and calculations without framework or network dependencies."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

METRICS = ("weight", "waist", "chest", "hip", "arm", "thigh", "calf")
SIDED_METRICS = ("arm", "thigh", "calf")
FIELDS = {"metric", "value", "unit", "side", "location", "local_date", "observed_at",
          "source_timezone", "notes", "synthetic"}


class InvalidMeasurement(ValueError):
    pass


def parse_day(value):
    if isinstance(value, datetime):
        raise InvalidMeasurement("Use a calendar date, not a timestamp.")
    if isinstance(value, date):
        return value
    try:
        if not isinstance(value, str) or len(value) != 10:
            raise ValueError
        result = date.fromisoformat(value)
        if result.isoformat() != value:
            raise ValueError
        return result
    except (ValueError, TypeError):
        raise InvalidMeasurement("Dates must use YYYY-MM-DD.") from None


def bounded_range(start, end):
    first, last = parse_day(start), parse_day(end)
    if last < first or (last - first).days >= 366:
        raise InvalidMeasurement("Use an ordered range of at most 366 inclusive days.")
    return first, last


def request_uuid(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise InvalidMeasurement("A stable UUID request_id is required.") from None


def decimal_value(value):
    if isinstance(value, bool):
        raise InvalidMeasurement("A numeric value is required.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise InvalidMeasurement("A numeric value is required.") from None
    if not result.is_finite():
        raise InvalidMeasurement("Values must be finite.")
    return result


def validate_measurement(payload):
    if not isinstance(payload, dict) or set(payload) - FIELDS:
        raise InvalidMeasurement("Unsupported measurement fields.")
    for key in ("metric", "value", "unit", "local_date"):
        if key not in payload:
            raise InvalidMeasurement(f"{key} is required.")
    metric = payload["metric"]
    if metric not in METRICS:
        raise InvalidMeasurement("Unsupported measurement type.")
    unit = payload["unit"]
    if unit not in (("kg", "lb") if metric == "weight" else ("cm", "in")):
        raise InvalidMeasurement("The unit is incompatible with this measurement.")
    value = decimal_value(payload["value"])
    if value <= 0 or value > Decimal("99999.999"):
        raise InvalidMeasurement("Measurement must be positive and below 100000.")
    if value != value.quantize(Decimal("0.001")):
        raise InvalidMeasurement("Use at most three decimal places.")
    value = value.quantize(Decimal("0.001"))
    side = payload.get("side", "")
    if metric in SIDED_METRICS and side not in ("left", "right"):
        raise InvalidMeasurement("Choose left or right for this measurement.")
    if metric not in SIDED_METRICS and side != "":
        raise InvalidMeasurement("This measurement does not have a left or right side.")
    notes = payload.get("notes", "")
    location = payload.get("location", "")
    if not isinstance(notes, str) or len(notes) > 2000:
        raise InvalidMeasurement("Notes must contain at most 2000 characters.")
    if not isinstance(location, str) or len(location) > 120:
        raise InvalidMeasurement("Location must contain at most 120 characters.")
    if metric != "weight" and not location.strip():
        raise InvalidMeasurement("Record the measurement location for repeatability.")
    synthetic = payload.get("synthetic", False)
    if type(synthetic) is not bool:
        raise InvalidMeasurement("synthetic must be true or false.")
    tz_name = payload.get("source_timezone", "America/Chicago")
    try:
        if not isinstance(tz_name, str) or len(tz_name) > 64:
            raise ValueError
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise InvalidMeasurement("Use a valid IANA source timezone.") from None
    local_date = parse_day(payload["local_date"])
    observed_at = payload.get("observed_at")
    if observed_at:
        try:
            if isinstance(observed_at, str):
                observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            if not isinstance(observed_at, datetime) or observed_at.utcoffset() is None:
                raise ValueError
        except (ValueError, TypeError):
            raise InvalidMeasurement("observed_at must include a UTC offset.") from None
        if observed_at.astimezone(tz).date() != local_date:
            raise InvalidMeasurement("Timestamp and local date disagree in the source timezone.")
    else:
        observed_at = None
    return {"metric": metric, "value": value, "unit": unit, "side": side,
            "location": location.strip(), "local_date": local_date,
            "observed_at": observed_at, "source_timezone": tz_name,
            "notes": notes, "synthetic": synthetic}


def net_carbohydrates(total_carbohydrates, fiber):
    """Keep source values; never clamp an inconsistent negative result to zero."""
    if total_carbohydrates is None or fiber is None:
        return {"value": None, "status": "unknown", "method": "total_carbohydrates - fiber"}
    total, dietary_fiber = decimal_value(total_carbohydrates), decimal_value(fiber)
    if total < 0 or dietary_fiber < 0 or dietary_fiber > total:
        return {"value": None, "status": "inconsistent", "method": "total_carbohydrates - fiber"}
    return {"value": total - dietary_fiber, "status": "calculated", "method": "total_carbohydrates - fiber"}
