"""Feature extraction for ML-based anomaly detection in SAIA V4."""

import logging
from datetime import datetime, timezone, timedelta
from statistics import median, stdev
from sqlalchemy.ext.asyncio import AsyncSession
import asyncpg

logger = logging.getLogger(__name__)

# 25 ML features for anomaly detection
FEATURE_NAMES = [
    # Temporal features (1-6)
    "hour_of_day",
    "day_of_week",
    "is_business_hours",
    "is_weekend",
    "minutes_since_last_event",
    "events_in_last_hour",
    # Behavioral features (7-14)
    "unique_resources_1h",
    "unique_actions_1h",
    "failed_action_ratio_1h",
    "privilege_level",
    "is_new_resource",
    "is_new_action",
    "deviation_from_hourly_baseline",
    "deviation_from_daily_baseline",
    # Contextual features (15-20)
    "source_ip_is_known",
    "source_country_is_usual",
    "asset_criticality",
    "principal_risk_score",
    "concurrent_sessions",
    "is_sensitive_resource",
    # Aggregate features (21-25)
    "entity_event_volume_zscore",
    "entity_error_rate_zscore",
    "entity_resource_diversity_zscore",
    "entity_privilege_escalation_rate",
    "cross_entity_correlation_score",
]

# Saudi Arabia business hours: Sunday-Thursday 7 AM - 6 PM
BUSINESS_HOURS_DAYS = {0, 1, 2, 3, 4}  # Sun=0, Mon=1, Tue=2, Wed=3, Thu=4
BUSINESS_HOURS_START = 7
BUSINESS_HOURS_END = 18


def _compute_mad(values: list[float]) -> float:
    """
    Compute Median Absolute Deviation (MAD).

    Args:
        values: List of numeric values

    Returns:
        MAD value
    """
    if not values:
        return 0.0

    med = median(values)
    deviations = [abs(x - med) for x in values]

    return median(deviations) if deviations else 0.0


def _z_score_mad(value: float, values: list[float]) -> float:
    """
    Compute z-score using MAD.

    Args:
        value: The value to score
        values: Distribution of values

    Returns:
        Z-score using MAD (median-based)
    """
    if not values or len(values) < 2:
        return 0.0

    med = median(values)
    mad = _compute_mad(values)

    if mad == 0:
        return 0.0

    return (value - med) / (1.4826 * mad)


def extract_temporal_features(event: dict) -> list[float]:
    """
    Extract temporal features (1-6).

    Args:
        event: Log event dictionary

    Returns:
        List of 6 temporal features
    """
    timestamp = event.get("timestamp")
    if not timestamp:
        timestamp = datetime.now(timezone.utc)
    elif isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    features = []

    # Feature 1: Hour of day (0-23)
    hour = timestamp.hour
    features.append(float(hour))

    # Feature 2: Day of week (0-6, Sunday=0)
    day_of_week = timestamp.weekday()
    # Convert Python weekday (0=Monday) to ISO (0=Sunday)
    iso_day = (day_of_week + 1) % 7
    features.append(float(iso_day))

    # Feature 3: Is business hours (Saudi: Sun-Thu 7-18)
    is_business = 1.0 if (iso_day in BUSINESS_HOURS_DAYS and
                          BUSINESS_HOURS_START <= hour < BUSINESS_HOURS_END) else 0.0
    features.append(is_business)

    # Feature 4: Is weekend (Fri-Sat)
    is_weekend = 1.0 if iso_day in {5, 6} else 0.0
    features.append(is_weekend)

    # Features 5-6: Minutes since last event and events in last hour
    # Will be filled in by caller with database context
    features.append(0.0)  # minutes_since_last_event (placeholder)
    features.append(0.0)  # events_in_last_hour (placeholder)

    return features


async def extract_behavioral_features(db: AsyncSession, event: dict) -> list[float]:
    """
    Extract behavioral features (7-14).

    Args:
        db: Database session
        event: Log event dictionary

    Returns:
        List of 8 behavioral features
    """
    features = []
    principal = event.get("principal", "unknown")
    timestamp = event.get("timestamp", datetime.now(timezone.utc))

    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    one_hour_ago = timestamp - timedelta(hours=1)

    try:
        # Connect to database for queries
        import asyncpg

        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="saia",
            password="saia_password",
            database="saia_db",
        )

        try:
            # Feature 7: Unique resources in last hour
            query7 = """
                SELECT COUNT(DISTINCT resource) FROM log_event
                WHERE principal = $1 AND timestamp >= $2 AND timestamp < $3
            """
            result = await conn.fetchval(query7, principal, one_hour_ago, timestamp)
            features.append(float(result or 0))

            # Feature 8: Unique actions in last hour
            query8 = """
                SELECT COUNT(DISTINCT action) FROM log_event
                WHERE principal = $1 AND timestamp >= $2 AND timestamp < $3
            """
            result = await conn.fetchval(query8, principal, one_hour_ago, timestamp)
            features.append(float(result or 0))

            # Feature 9: Failed action ratio in last hour
            query9 = """
                SELECT
                    COALESCE(SUM(CASE WHEN result != 'success' THEN 1 ELSE 0 END), 0)::float /
                    NULLIF(COUNT(*), 0) as fail_ratio
                FROM log_event
                WHERE principal = $1 AND timestamp >= $2 AND timestamp < $3
            """
            result = await conn.fetchval(query9, principal, one_hour_ago, timestamp)
            features.append(float(result or 0.0))

            # Feature 10: Privilege level (default 1)
            query10 = """
                SELECT privilege_level FROM action_privilege_levels
                WHERE action = $1 LIMIT 1
            """
            result = await conn.fetchval(query10, event.get("action", "unknown"))
            features.append(float(result or 1))

            # Feature 11: Is new resource (binary)
            query11 = """
                SELECT COUNT(*) FROM log_event
                WHERE principal = $1 AND resource = $2 AND timestamp < $3
            """
            count = await conn.fetchval(
                query11, principal, event.get("resource"), timestamp
            )
            features.append(0.0 if count and count > 0 else 1.0)

            # Feature 12: Is new action (binary)
            query12 = """
                SELECT COUNT(*) FROM log_event
                WHERE principal = $1 AND action = $2 AND timestamp < $3
            """
            count = await conn.fetchval(
                query12, principal, event.get("action"), timestamp
            )
            features.append(0.0 if count and count > 0 else 1.0)

            # Feature 13: Deviation from hourly baseline
            query13 = """
                SELECT COUNT(*) FROM log_event
                WHERE principal = $1 AND timestamp >= $2 AND timestamp < $3
            """
            current_hour_events = await conn.fetchval(
                query13,
                principal,
                timestamp.replace(minute=0, second=0, microsecond=0),
                timestamp.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1),
            )

            # Get historical hourly baseline (last 7 days, same hour)
            query14 = """
                SELECT COUNT(*) FROM log_event
                WHERE principal = $1 AND EXTRACT(HOUR FROM timestamp) = $2
                    AND timestamp >= $3 AND timestamp < $4
            """
            seven_days_ago = timestamp - timedelta(days=7)
            historical = await conn.fetch(
                query14,
                principal,
                timestamp.hour,
                seven_days_ago,
                timestamp,
            )

            historical_counts = [row[0] for row in historical] if historical else []
            if historical_counts:
                z_score = _z_score_mad(float(current_hour_events or 0),
                                       [float(x) for x in historical_counts])
                features.append(z_score)
            else:
                features.append(0.0)

            # Feature 14: Deviation from daily baseline
            query15 = """
                SELECT COUNT(*) FROM log_event
                WHERE principal = $1 AND DATE(timestamp) = DATE($2)
            """
            current_day_events = await conn.fetchval(query15, principal, timestamp)

            # Get historical daily baseline (last 30 days)
            query16 = """
                SELECT COUNT(*) FROM log_event
                WHERE principal = $1 AND DATE(timestamp) BETWEEN DATE($2) - 30 AND DATE($3) - 1
                GROUP BY DATE(timestamp)
            """
            thirty_days_ago = timestamp - timedelta(days=30)
            historical = await conn.fetch(query16, principal, timestamp, timestamp)

            historical_counts = [row[0] for row in historical] if historical else []
            if historical_counts:
                z_score = _z_score_mad(float(current_day_events or 0),
                                       [float(x) for x in historical_counts])
                features.append(z_score)
            else:
                features.append(0.0)

        finally:
            await conn.close()

    except Exception as e:
        logger.warning(f"Error extracting behavioral features: {e}")
        # Return safe defaults
        features = [0.0] * 8

    return features


async def extract_contextual_features(db: AsyncSession, event: dict) -> list[float]:
    """
    Extract contextual features (15-20).

    Args:
        db: Database session
        event: Log event dictionary

    Returns:
        List of 6 contextual features
    """
    features = []

    try:
        import asyncpg

        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="saia",
            password="saia_password",
            database="saia_db",
        )

        try:
            # Feature 15: Source IP is known (binary)
            source_ip = event.get("source_ip", "unknown")
            query15 = """
                SELECT COUNT(*) FROM log_event WHERE source_ip = $1 LIMIT 1
            """
            count = await conn.fetchval(query15, source_ip)
            features.append(1.0 if count and count > 0 else 0.0)

            # Feature 16: Source country is usual (default SA)
            # Simplified: assume SA by default
            features.append(1.0)

            # Feature 17: Asset criticality (from asset_registry, default 3)
            asset_id = event.get("asset_id")
            query17 = """
                SELECT criticality FROM asset_registry WHERE asset_id = $1 LIMIT 1
            """
            criticality = await conn.fetchval(query17, asset_id)
            features.append(float(criticality or 3))

            # Feature 18: Principal risk score (from entity_baselines, default 0.0)
            principal = event.get("principal", "unknown")
            query18 = """
                SELECT risk_score FROM entity_baselines WHERE principal = $1 LIMIT 1
            """
            risk_score = await conn.fetchval(query18, principal)
            features.append(float(risk_score or 0.0))

            # Feature 19: Concurrent sessions
            timestamp = event.get("timestamp", datetime.now(timezone.utc))
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

            query19 = """
                SELECT COUNT(DISTINCT source_ip) FROM log_event
                WHERE principal = $1 AND timestamp >= $2 - INTERVAL '1 hour'
                    AND timestamp < $2
            """
            sessions = await conn.fetchval(query19, principal, timestamp)
            features.append(float(sessions or 0))

            # Feature 20: Is sensitive resource (from asset_registry, binary)
            resource = event.get("resource", "unknown")
            query20 = """
                SELECT is_sensitive FROM asset_registry WHERE asset_id = $1 LIMIT 1
            """
            is_sensitive = await conn.fetchval(query20, resource)
            features.append(1.0 if is_sensitive else 0.0)

        finally:
            await conn.close()

    except Exception as e:
        logger.warning(f"Error extracting contextual features: {e}")
        features = [0.0] * 6

    return features


async def extract_aggregate_features(db: AsyncSession, event: dict) -> list[float]:
    """
    Extract aggregate features (21-25).

    Args:
        db: Database session
        event: Log event dictionary

    Returns:
        List of 5 aggregate features
    """
    features = []

    try:
        import asyncpg

        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="saia",
            password="saia_password",
            database="saia_db",
        )

        try:
            principal = event.get("principal", "unknown")
            timestamp = event.get("timestamp", datetime.now(timezone.utc))

            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

            # Feature 21: Entity event volume z-score
            query21 = """
                SELECT COUNT(*) FROM log_event
                WHERE principal = $1 AND timestamp >= $2 - INTERVAL '1 hour'
            """
            current_volume = await conn.fetchval(query21, principal, timestamp)

            # Get historical volumes
            query22 = """
                SELECT COUNT(*) FROM log_event
                WHERE principal = $1 AND timestamp >= $2 - INTERVAL '7 days'
                    AND timestamp < $2
                GROUP BY DATE_TRUNC('hour', timestamp)
            """
            historical = await conn.fetch(query22, principal, timestamp)
            historical_volumes = [row[0] for row in historical] if historical else []

            if historical_volumes:
                z_score = _z_score_mad(float(current_volume or 0),
                                       [float(x) for x in historical_volumes])
                features.append(z_score)
            else:
                features.append(0.0)

            # Feature 22: Entity error rate z-score
            query23 = """
                SELECT COALESCE(SUM(CASE WHEN result != 'success' THEN 1 ELSE 0 END), 0)::float /
                       NULLIF(COUNT(*), 0)
                FROM log_event
                WHERE principal = $1 AND timestamp >= $2 - INTERVAL '1 hour'
            """
            current_error_rate = await conn.fetchval(query23, principal, timestamp)

            # Historical error rates
            query24 = """
                SELECT COALESCE(SUM(CASE WHEN result != 'success' THEN 1 ELSE 0 END), 0)::float /
                       NULLIF(COUNT(*), 0)
                FROM log_event
                WHERE principal = $1 AND timestamp >= $2 - INTERVAL '7 days'
                GROUP BY DATE_TRUNC('hour', timestamp)
            """
            historical = await conn.fetch(query24, principal, timestamp)
            historical_error_rates = [row[0] for row in historical if row[0] is not None]

            if historical_error_rates:
                z_score = _z_score_mad(float(current_error_rate or 0),
                                       historical_error_rates)
                features.append(z_score)
            else:
                features.append(0.0)

            # Feature 23: Entity resource diversity z-score
            query25 = """
                SELECT COUNT(DISTINCT resource) FROM log_event
                WHERE principal = $1 AND timestamp >= $2 - INTERVAL '1 hour'
            """
            current_diversity = await conn.fetchval(query25, principal, timestamp)

            # Historical diversity
            query26 = """
                SELECT COUNT(DISTINCT resource) FROM log_event
                WHERE principal = $1 AND timestamp >= $2 - INTERVAL '7 days'
                GROUP BY DATE_TRUNC('hour', timestamp)
            """
            historical = await conn.fetch(query26, principal, timestamp)
            historical_diversity = [row[0] for row in historical] if historical else []

            if historical_diversity:
                z_score = _z_score_mad(float(current_diversity or 0),
                                       [float(x) for x in historical_diversity])
                features.append(z_score)
            else:
                features.append(0.0)

            # Feature 24: Entity privilege escalation rate
            query27 = """
                SELECT COUNT(*) FROM log_event
                WHERE principal = $1 AND timestamp >= $2 - INTERVAL '1 hour'
                    AND action LIKE '%privilege%' OR action LIKE '%escalat%'
            """
            escalations = await conn.fetchval(query27, principal, timestamp)

            query28 = """
                SELECT COUNT(*) FROM log_event
                WHERE principal = $1 AND timestamp >= $2 - INTERVAL '1 hour'
            """
            total = await conn.fetchval(query28, principal, timestamp)

            escalation_rate = (float(escalations or 0) / float(total)) if total else 0.0
            features.append(escalation_rate)

            # Feature 25: Cross-entity correlation score
            # Simplified: check if other entities accessed same resources in same timeframe
            query29 = """
                SELECT COUNT(DISTINCT principal) FROM log_event
                WHERE resource IN (
                    SELECT resource FROM log_event
                    WHERE principal = $1 AND timestamp >= $2 - INTERVAL '1 hour'
                ) AND timestamp >= $3 - INTERVAL '1 hour'
            """
            correlated_entities = await conn.fetchval(query29, principal, timestamp, timestamp)
            features.append(float(correlated_entities or 1) / 100.0)  # Normalize

        finally:
            await conn.close()

    except Exception as e:
        logger.warning(f"Error extracting aggregate features: {e}")
        features = [0.0] * 5

    return features


async def extract_features(db: AsyncSession, event: dict) -> list[float]:
    """
    Extract all 25 ML features for a log event.

    Args:
        db: Database session
        event: Log event dictionary

    Returns:
        List of 25 features in order
    """
    features = []

    # Extract each feature group
    temporal = extract_temporal_features(event)
    behavioral = await extract_behavioral_features(db, event)
    contextual = await extract_contextual_features(db, event)
    aggregate = await extract_aggregate_features(db, event)

    # Combine all features
    features.extend(temporal)
    features.extend(behavioral)
    features.extend(contextual)
    features.extend(aggregate)

    # Ensure we have exactly 25 features
    while len(features) < 25:
        features.append(0.0)

    return features[:25]
