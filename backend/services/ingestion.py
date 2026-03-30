"""Log ingestion, parsing, normalization, and quality gating for SAIA V4."""

import logging
import csv
import json
from io import StringIO, BytesIO
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Quality thresholds and required fields
REQUIRED_FIELDS = ["timestamp", "action", "domain"]
IMPORTANT_FIELDS = ["principal", "resource", "result", "source_ip", "event_type"]
QUALITY_THRESHOLD = 0.7

# Field name variations for normalization
FIELD_MAPPING = {
    "user": "principal",
    "username": "principal",
    "actor": "principal",
    "src_ip": "source_ip",
    "source_address": "source_ip",
    "ip": "source_ip",
    "status": "result",
    "outcome": "result",
    "command": "action",
    "operation": "action",
    "asset": "resource",
    "object": "resource",
    "target": "resource",
    "log_source": "source",
    "log_type": "event_type",
    "type": "event_type",
}


def compute_quality_score(event: dict) -> float:
    """
    Compute quality score for a log event.

    Formula:
    - 1.0 point for each required field present
    - 0.1 points for each important field present (up to 5 fields = 0.5 max)
    - Divide by (3 required + 0.5 important) = 3.5 max possible

    Args:
        event: Log event dictionary

    Returns:
        Quality score between 0.0 and 1.0
    """
    score = 0.0

    # Check required fields (1.0 each)
    required_present = sum(1 for field in REQUIRED_FIELDS if event.get(field))
    score += min(required_present, len(REQUIRED_FIELDS))

    # Check important fields (0.1 each, up to 0.5)
    important_present = sum(
        1 for field in IMPORTANT_FIELDS if event.get(field)
    )
    score += min(important_present * 0.1, 0.5)

    # Normalize to 0-1 range
    max_score = len(REQUIRED_FIELDS) + 0.5
    normalized_score = min(score / max_score, 1.0)

    return normalized_score


def normalize_event(
    raw_event: dict, source_name: str, domain: str
) -> dict:
    """
    Normalize a raw log event to canonical schema.

    Maps field name variations to canonical names, fills missing fields with defaults,
    parses timestamps, and adds metadata.

    Args:
        raw_event: Raw log event from source
        source_name: Name of the source (e.g., "firewall", "vpn")
        domain: Domain/department identifier

    Returns:
        Normalized event dictionary with canonical field names
    """
    normalized = {
        "source": source_name,
        "domain": domain,
        "raw_log": raw_event,
    }

    # Copy and map field names
    for raw_field, value in raw_event.items():
        # Map field name if it has a variation
        canonical_field = FIELD_MAPPING.get(raw_field.lower(), raw_field.lower())

        # Skip if already normalized
        if canonical_field not in normalized:
            normalized[canonical_field] = value

    # Parse timestamp if string
    if "timestamp" in normalized:
        timestamp_val = normalized["timestamp"]
        if isinstance(timestamp_val, str):
            try:
                # Try ISO format first
                normalized["timestamp"] = datetime.fromisoformat(
                    timestamp_val.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                try:
                    # Try common formats
                    for fmt in [
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%d %H:%M:%S.%f",
                        "%Y-%m-%dT%H:%M:%S",
                        "%d/%m/%Y %H:%M:%S",
                    ]:
                        try:
                            dt = datetime.strptime(timestamp_val, fmt)
                            # Assume UTC if no timezone
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            normalized["timestamp"] = dt
                            break
                        except ValueError:
                            continue
                except Exception as e:
                    logger.warning(
                        f"Failed to parse timestamp '{timestamp_val}': {e}"
                    )
                    normalized["timestamp"] = datetime.now(timezone.utc)
        elif isinstance(timestamp_val, (int, float)):
            # Unix timestamp
            normalized["timestamp"] = datetime.fromtimestamp(
                timestamp_val, tz=timezone.utc
            )
    else:
        normalized["timestamp"] = datetime.now(timezone.utc)

    # Fill missing fields with None
    canonical_fields = [
        "timestamp",
        "source",
        "event_type",
        "principal",
        "action",
        "resource",
        "result",
        "source_ip",
        "asset_id",
        "domain",
    ]

    for field in canonical_fields:
        if field not in normalized:
            normalized[field] = None

    return normalized


def parse_json_upload(file_content: bytes) -> list[dict]:
    """
    Parse JSON array upload.

    Args:
        file_content: Raw file content bytes

    Returns:
        List of parsed log events

    Raises:
        ValueError: If JSON is invalid or not an array
    """
    try:
        text = file_content.decode("utf-8")
        data = json.loads(text)

        if not isinstance(data, list):
            raise ValueError("JSON content must be an array of objects")

        return data

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
    except UnicodeDecodeError as e:
        raise ValueError(f"Invalid file encoding: {e}")


def parse_csv_upload(file_content: bytes) -> list[dict]:
    """
    Parse CSV upload with headers.

    Args:
        file_content: Raw file content bytes

    Returns:
        List of parsed log events as dictionaries

    Raises:
        ValueError: If CSV is invalid
    """
    try:
        text = file_content.decode("utf-8")
        reader = csv.DictReader(StringIO(text))

        if not reader.fieldnames:
            raise ValueError("CSV has no headers")

        events = []
        for row in reader:
            if row and any(row.values()):  # Skip empty rows
                events.append(row)

        return events

    except UnicodeDecodeError as e:
        raise ValueError(f"Invalid file encoding: {e}")
    except Exception as e:
        raise ValueError(f"Error parsing CSV: {e}")


async def process_upload(
    db: AsyncSession,
    file_content: bytes,
    filename: str,
    source_name: str,
    domain: str,
    user_id: UUID,
) -> dict:
    """
    Full ingestion pipeline for file upload.

    Steps:
    1. Parse file (JSON or CSV based on extension)
    2. Normalize all events
    3. Compute quality scores and gate low-quality events
    4. Create upload record
    5. Save events to database

    Args:
        db: AsyncSession database connection
        file_content: Raw file bytes
        filename: Original filename (for format detection)
        source_name: Name of log source
        domain: Domain/department identifier
        user_id: UUID of user performing upload

    Returns:
        Dictionary with upload_id, events_parsed, events_accepted, events_quarantined
    """
    upload_id = uuid4()
    events_parsed = 0
    events_accepted = 0
    events_quarantined = 0

    try:
        # Parse file
        if filename.endswith(".json"):
            raw_events = parse_json_upload(file_content)
        elif filename.endswith(".csv"):
            raw_events = parse_csv_upload(file_content)
        else:
            # Try JSON first, then CSV
            try:
                raw_events = parse_json_upload(file_content)
            except ValueError:
                raw_events = parse_csv_upload(file_content)

        events_parsed = len(raw_events)

        # Normalize and quality gate
        accepted_events = []
        quarantined_events = []

        for raw_event in raw_events:
            try:
                normalized = normalize_event(raw_event, source_name, domain)
                quality_score = compute_quality_score(normalized)

                if quality_score >= QUALITY_THRESHOLD:
                    normalized["quality_score"] = quality_score
                    normalized["is_quarantined"] = False
                    accepted_events.append(normalized)
                    events_accepted += 1
                else:
                    normalized["quality_score"] = quality_score
                    normalized["is_quarantined"] = True
                    quarantined_events.append(normalized)
                    events_quarantined += 1

            except Exception as e:
                logger.warning(f"Error normalizing event: {e}")
                events_quarantined += 1

        # Create upload record
        now = datetime.now(timezone.utc)

        # Insert using raw SQL with asyncpg syntax
        upload_query = """
            INSERT INTO log_upload (
                id, user_id, source_name, domain, filename,
                events_parsed, events_accepted, events_quarantined,
                status, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """

        import asyncpg

        pool = await asyncpg.create_pool(
            host="localhost",
            port=5432,
            user="saia",
            password="saia_password",
            database="saia_db",
        )

        async with pool.acquire() as conn:
            await conn.execute(
                upload_query,
                upload_id,
                user_id,
                source_name,
                domain,
                filename,
                events_parsed,
                events_accepted,
                events_quarantined,
                "completed",
                now,
            )

            # Insert accepted events
            for event in accepted_events:
                event_id = uuid4()
                event_query = """
                    INSERT INTO log_event (
                        id, upload_id, timestamp, source, event_type,
                        principal, action, resource, result, source_ip,
                        asset_id, domain, quality_score, is_quarantined,
                        raw_log, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                """

                import json

                raw_log_json = json.dumps(event.get("raw_log", {}))

                await conn.execute(
                    event_query,
                    event_id,
                    upload_id,
                    event.get("timestamp"),
                    event.get("source"),
                    event.get("event_type"),
                    event.get("principal"),
                    event.get("action"),
                    event.get("resource"),
                    event.get("result"),
                    event.get("source_ip"),
                    event.get("asset_id"),
                    event.get("domain"),
                    event.get("quality_score"),
                    event.get("is_quarantined"),
                    raw_log_json,
                    now,
                )

            # Insert quarantined events
            for event in quarantined_events:
                event_id = uuid4()
                event_query = """
                    INSERT INTO log_event (
                        id, upload_id, timestamp, source, event_type,
                        principal, action, resource, result, source_ip,
                        asset_id, domain, quality_score, is_quarantined,
                        raw_log, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                """

                import json

                raw_log_json = json.dumps(event.get("raw_log", {}))

                await conn.execute(
                    event_query,
                    event_id,
                    upload_id,
                    event.get("timestamp"),
                    event.get("source"),
                    event.get("event_type"),
                    event.get("principal"),
                    event.get("action"),
                    event.get("resource"),
                    event.get("result"),
                    event.get("source_ip"),
                    event.get("asset_id"),
                    event.get("domain"),
                    event.get("quality_score"),
                    event.get("is_quarantined"),
                    raw_log_json,
                    now,
                )

        await pool.close()

    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        raise

    return {
        "upload_id": upload_id,
        "events_parsed": events_parsed,
        "events_accepted": events_accepted,
        "events_quarantined": events_quarantined,
    }


async def process_ingest(
    db: AsyncSession,
    events: list[dict],
    source_name: str,
    domain: str,
    user_id: UUID,
) -> dict:
    """
    Full ingestion pipeline for JSON body ingest.

    Steps:
    1. Normalize all events
    2. Compute quality scores and gate low-quality events
    3. Create upload record
    4. Save events to database

    Args:
        db: AsyncSession database connection
        events: List of raw event dictionaries
        source_name: Name of log source
        domain: Domain/department identifier
        user_id: UUID of user performing ingest

    Returns:
        Dictionary with upload_id, events_parsed, events_accepted, events_quarantined
    """
    upload_id = uuid4()
    events_parsed = len(events)
    events_accepted = 0
    events_quarantined = 0

    try:
        # Normalize and quality gate
        accepted_events = []
        quarantined_events = []

        for raw_event in events:
            try:
                normalized = normalize_event(raw_event, source_name, domain)
                quality_score = compute_quality_score(normalized)

                if quality_score >= QUALITY_THRESHOLD:
                    normalized["quality_score"] = quality_score
                    normalized["is_quarantined"] = False
                    accepted_events.append(normalized)
                    events_accepted += 1
                else:
                    normalized["quality_score"] = quality_score
                    normalized["is_quarantined"] = True
                    quarantined_events.append(normalized)
                    events_quarantined += 1

            except Exception as e:
                logger.warning(f"Error normalizing event: {e}")
                events_quarantined += 1

        # Create upload record
        now = datetime.now(timezone.utc)

        import asyncpg
        import json

        pool = await asyncpg.create_pool(
            host="localhost",
            port=5432,
            user="saia",
            password="saia_password",
            database="saia_db",
        )

        async with pool.acquire() as conn:
            upload_query = """
                INSERT INTO log_upload (
                    id, user_id, source_name, domain, filename,
                    events_parsed, events_accepted, events_quarantined,
                    status, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """

            await conn.execute(
                upload_query,
                upload_id,
                user_id,
                source_name,
                domain,
                "ingest_request",
                events_parsed,
                events_accepted,
                events_quarantined,
                "completed",
                now,
            )

            # Insert all events
            all_events = accepted_events + quarantined_events
            for event in all_events:
                event_id = uuid4()
                event_query = """
                    INSERT INTO log_event (
                        id, upload_id, timestamp, source, event_type,
                        principal, action, resource, result, source_ip,
                        asset_id, domain, quality_score, is_quarantined,
                        raw_log, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                """

                raw_log_json = json.dumps(event.get("raw_log", {}))

                await conn.execute(
                    event_query,
                    event_id,
                    upload_id,
                    event.get("timestamp"),
                    event.get("source"),
                    event.get("event_type"),
                    event.get("principal"),
                    event.get("action"),
                    event.get("resource"),
                    event.get("result"),
                    event.get("source_ip"),
                    event.get("asset_id"),
                    event.get("domain"),
                    event.get("quality_score"),
                    event.get("is_quarantined"),
                    raw_log_json,
                    now,
                )

        await pool.close()

    except Exception as e:
        logger.error(f"Error processing ingest: {e}")
        raise

    return {
        "upload_id": upload_id,
        "events_parsed": events_parsed,
        "events_accepted": events_accepted,
        "events_quarantined": events_quarantined,
    }
