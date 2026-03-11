"""
Ingestion Service
Pair 2 (Rakan + Faisal) — responsible for this module.

Handles CSV/JSON file parsing, calls normalization, persists LogEvents to DB.
After persistence it hands events to the Rule Engine and AI service.
"""

import json
import csv
import io
from sqlalchemy.orm import Session
from models.log_event import LogEvent
from services.normalization_service import normalize


def parse_json_logs(content: bytes) -> list[dict]:
    """Parse a JSON file — supports both a JSON array and newline-delimited JSON."""
    text = content.decode("utf-8")
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        # Try newline-delimited JSON (NDJSON)
        return [json.loads(line) for line in text.splitlines() if line.strip()]


def parse_csv_logs(content: bytes) -> list[dict]:
    """Parse a CSV file into a list of dicts."""
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def ingest_logs(
    raw_entries: list[dict],
    source: str,
    db: Session,
) -> dict:
    """
    Normalize and persist a batch of raw log entries.
    Returns a summary dict for the API response.
    """
    normalized_count = 0
    quarantined_count = 0
    saved_events = []

    for entry in raw_entries:
        canonical = normalize(entry, source)

        event = LogEvent(**{
            k: v for k, v in canonical.items()
            if hasattr(LogEvent, k)
        })
        db.add(event)
        db.flush()  # get the ID before committing

        if canonical.get("is_quarantined"):
            quarantined_count += 1
        else:
            normalized_count += 1
            saved_events.append(event)

    db.commit()

    return {
        "total_received": len(raw_entries),
        "normalized": normalized_count,
        "quarantined": quarantined_count,
        "saved_events": saved_events,
    }
