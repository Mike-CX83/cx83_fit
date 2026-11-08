"""Bounded parsing for the app's reviewed measurement CSV format.

This is not a provider adapter. Parsing performs no file, database or network
operations. The caller owns preview, consent, source namespace and persistence.
"""
import csv
import io
import re

from .domain import InvalidMeasurement, validate_measurement


MAX_BYTES = 65536
MAX_ROWS = 200
_REQUIRED = ("source_record_id", "metric", "value", "unit", "local_date",
             "source_timezone", "synthetic")
HEADER = _REQUIRED + ("side", "location", "notes", "observed_at")
_SOURCE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}", re.ASCII)


def parse_measurement_csv(content: bytes) -> list[dict]:
    """Return canonical JSON-safe rows, or reject the entire input.

    Row numbers identify logical CSV records, including header row 1. Required
    column names are exact; optional columns may be omitted and order may vary.
    Empty optional timestamps stay absent. Original units and timezone remain.
    """
    if not isinstance(content, bytes):
        raise InvalidMeasurement("CSV input must be bytes.")
    if len(content) > MAX_BYTES:
        raise InvalidMeasurement("CSV input exceeds the 64 KiB limit.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InvalidMeasurement("CSV input must use UTF-8 encoding.") from None
    if "\0" in text:
        raise InvalidMeasurement("CSV input cannot contain NUL characters.")

    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    row_number = 1
    try:
        header = next(reader, None)
        if not header:
            raise InvalidMeasurement("CSV row 1: a header is required.")
        if len(header) != len(set(header)):
            raise InvalidMeasurement("CSV row 1: duplicate column names are not allowed.")
        if set(header) - set(HEADER):
            raise InvalidMeasurement("CSV row 1: unknown column names are not allowed.")
        if set(_REQUIRED) - set(header):
            raise InvalidMeasurement("CSV row 1: required columns are missing.")

        rows = []
        seen_ids = set()
        while True:
            row_number = len(rows) + 2
            fields = next(reader, None)
            if fields is None:
                break
            if len(rows) >= MAX_ROWS:
                raise InvalidMeasurement(f"CSV row {row_number}: at most {MAX_ROWS} measurements are allowed.")
            if len(fields) != len(header):
                raise InvalidMeasurement(f"CSV row {row_number}: column count does not match the header.")
            values = dict(zip(header, fields))
            source_id = values.pop("source_record_id")
            if not _SOURCE_ID.fullmatch(source_id):
                raise InvalidMeasurement(f"CSV row {row_number}: source_record_id must use 1 to 120 allowed characters.")
            if source_id in seen_ids:
                raise InvalidMeasurement(f"CSV row {row_number}: duplicate source_record_id in this file.")
            if values["synthetic"] not in {"true", "false"}:
                raise InvalidMeasurement(f"CSV row {row_number}: synthetic must be lowercase true or false.")
            values["synthetic"] = values["synthetic"] == "true"
            try:
                clean = validate_measurement(values)
            except InvalidMeasurement as exc:
                # Domain errors are fixed validation messages, not input echoes.
                raise InvalidMeasurement(f"CSV row {row_number}: {exc}") from None
            except (ArithmeticError, ValueError, TypeError):
                # Out-of-range date arithmetic and numeric conversion details
                # must not leak submitted values or escape as server errors.
                raise InvalidMeasurement(f"CSV row {row_number}: invalid numeric or date value.") from None
            canonical = {**clean, "value": format(clean["value"], ".3f"),
                         "local_date": clean["local_date"].isoformat(),
                         "observed_at": (clean["observed_at"].isoformat()
                                         if clean["observed_at"] is not None else None)}
            rows.append({"source_record_id": source_id, "measurement": canonical})
            seen_ids.add(source_id)
    except csv.Error:
        raise InvalidMeasurement(f"CSV row {row_number}: malformed CSV structure.") from None

    if not rows:
        raise InvalidMeasurement("CSV row 2: at least one measurement is required.")
    return rows
