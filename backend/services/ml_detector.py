"""ML-based anomaly detection using Isolation Forest for SAIA V4."""

import logging
import math
import pickle
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import median, stdev
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
import asyncpg

from .feature_extractor import extract_features, FEATURE_NAMES

logger = logging.getLogger(__name__)

# Baseline maturity threshold (sample count)
BASELINE_MATURITY_THRESHOLD = 50

# Domain-specific configuration (from architecture spec)
DOMAIN_CONFIG = {
    "vpn": {
        "weight_if": 0.6,
        "weight_baseline": 0.4,
        "anomaly_threshold": 0.7,
    },
    "firewall": {
        "weight_if": 0.5,
        "weight_baseline": 0.5,
        "anomaly_threshold": 0.65,
    },
    "cloud": {
        "weight_if": 0.7,
        "weight_baseline": 0.3,
        "anomaly_threshold": 0.75,
    },
    "default": {
        "weight_if": 0.6,
        "weight_baseline": 0.4,
        "anomaly_threshold": 0.7,
    },
}


def load_models() -> dict:
    """
    Load Isolation Forest models from disk.

    Looks for .joblib files in backend/ml_models/ directory.
    If files don't exist, creates default untrained models.

    Returns:
        Dictionary keyed by domain with loaded models
    """
    models = {}
    ml_models_dir = Path(__file__).parent.parent / "ml_models"

    for domain in ["vpn", "firewall", "cloud", "default"]:
        model_path = ml_models_dir / f"{domain}_if_model.joblib"

        if model_path.exists():
            try:
                with open(model_path, "rb") as f:
                    models[domain] = pickle.load(f)
                logger.info(f"Loaded IF model for domain: {domain}")
            except Exception as e:
                logger.warning(f"Failed to load IF model for {domain}: {e}")
                models[domain] = None
        else:
            logger.warning(f"IF model not found for {domain}, will use default")
            models[domain] = None

    return models


def normalize_if_score(raw_score: float) -> float:
    """
    Normalize Isolation Forest anomaly score to [0, 1] range.

    IF returns scores in range (-1, 1) where negative = inlier, positive = outlier.
    We map to [0, 1] where 0 = normal, 1 = anomalous.

    Args:
        raw_score: Raw IF anomaly score

    Returns:
        Normalized score in [0, 1]
    """
    # Clamp to [-1, 1] and shift to [0, 2], then divide by 2
    clamped = max(-1.0, min(1.0, raw_score))
    normalized = (clamped + 1.0) / 2.0

    return normalized


def compute_combined_score(
    if_score_normalized: float, max_baseline_deviation: float, domain: str
) -> float:
    """
    Compute combined anomaly score using IF and baseline deviations.

    Uses domain-specific weights and sigmoid normalization as specified in arch doc.

    Args:
        if_score_normalized: Normalized IF score [0, 1]
        max_baseline_deviation: Maximum baseline deviation (z-score) across features
        domain: Domain (vpn, firewall, cloud, etc.)

    Returns:
        Combined anomaly score [0, 1]
    """
    config = DOMAIN_CONFIG.get(domain, DOMAIN_CONFIG["default"])
    weight_if = config["weight_if"]
    weight_baseline = config["weight_baseline"]

    # Normalize baseline deviation using sigmoid
    baseline_normalized = 1.0 / (1.0 + math.exp(-max_baseline_deviation / 3.0))

    # Weighted combination
    combined = (weight_if * if_score_normalized) + (
        weight_baseline * baseline_normalized
    )

    # Clamp to [0, 1]
    return max(0.0, min(1.0, combined))


def compute_severity(anomaly_score: float) -> str:
    """
    Map anomaly score to severity level.

    As specified in architecture:
    - score >= 0.85: Critical
    - score >= 0.70: High
    - score >= 0.50: Medium
    - score < 0.50: Low

    Args:
        anomaly_score: Computed anomaly score [0, 1]

    Returns:
        Severity string: Critical, High, Medium, or Low
    """
    if anomaly_score >= 0.85:
        return "Critical"
    elif anomaly_score >= 0.70:
        return "High"
    elif anomaly_score >= 0.50:
        return "Medium"
    else:
        return "Low"


def get_top_contributing_features(
    features: list[float],
    feature_names: list[str],
    model,
    top_k: int = 3,
) -> list[dict]:
    """
    Get top contributing features to anomaly detection.

    Uses feature importance or deviation from expected values.

    Args:
        features: Feature vector for the event
        feature_names: Names of features
        model: Trained IF model (can be None)
        top_k: Number of top features to return

    Returns:
        List of dicts with feature name, value, and deviation
    """
    # If no model, return features with highest absolute values
    if model is None:
        scored_features = [
            {
                "name": feature_names[i],
                "value": features[i],
                "deviation_sigma": features[i],
            }
            for i in range(min(top_k * 2, len(features)))
        ]
        # Sort by absolute value
        scored_features.sort(key=lambda x: abs(x["deviation_sigma"]), reverse=True)
        return scored_features[:top_k]

    # With model, try to use feature importances if available
    try:
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
        else:
            # Fallback: use feature values
            importances = [abs(f) for f in features]

        scored_features = [
            {
                "name": feature_names[i],
                "value": features[i],
                "deviation_sigma": importances[i],
            }
            for i in range(len(features))
        ]
        scored_features.sort(key=lambda x: x["deviation_sigma"], reverse=True)
        return scored_features[:top_k]

    except Exception as e:
        logger.warning(f"Error getting top features: {e}")
        return []


async def should_apply_ml(db: AsyncSession, principal: str, domain: str) -> bool:
    """
    Check if ML detection should be applied.

    Returns True if entity has >= BASELINE_MATURITY_THRESHOLD events.

    Args:
        db: Database session
        principal: User/entity principal
        domain: Domain

    Returns:
        True if baseline is mature enough
    """
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
            query = """
                SELECT sample_count FROM entity_baselines
                WHERE principal = $1 AND domain = $2 LIMIT 1
            """
            result = await conn.fetchval(query, principal, domain)
            sample_count = result or 0

            return sample_count >= BASELINE_MATURITY_THRESHOLD

        finally:
            await conn.close()

    except Exception as e:
        logger.warning(f"Error checking baseline maturity: {e}")
        return False


async def detect_anomaly(
    db: AsyncSession,
    event: dict,
    features: list[float],
) -> Optional[dict]:
    """
    Run full anomaly detection pipeline.

    Steps:
    1. Check if baseline is mature for entity
    2. Extract features
    3. Run IF if model available
    4. Compute baseline deviations
    5. Compute combined score
    6. Compare to domain-specific threshold
    7. Return result if flagged

    Args:
        db: Database session
        event: Log event
        features: Pre-extracted features (25-length vector)

    Returns:
        Detection result dict if flagged, None otherwise:
        {
            "anomaly_score": float,
            "severity": str,
            "top_features": list[dict],
            "baseline_deviations": dict,
            "is_flagged": bool,
        }
    """
    principal = event.get("principal", "unknown")
    domain = event.get("domain", "default")

    try:
        # Check baseline maturity
        apply_ml = await should_apply_ml(db, principal, domain)

        if not apply_ml:
            logger.debug(
                f"Baseline not mature for {principal}/{domain}, skipping ML"
            )
            return None

        # Load model
        models = load_models()
        model = models.get(domain)

        # Compute IF score if model available
        if_score = 0.0
        if model is not None:
            try:
                # Model returns anomaly score
                raw_score = model.decision_function([features])[0]
                if_score = normalize_if_score(raw_score)
            except Exception as e:
                logger.warning(f"Error running IF model: {e}")
                if_score = 0.0
        else:
            # Without model, use simple heuristic
            if_score = 0.5

        # Compute baseline deviations
        # Get historical stats for this entity
        import asyncpg

        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="saia",
            password="saia_password",
            database="saia_db",
        )

        try:
            query = """
                SELECT feature_mean, feature_stddev FROM entity_baselines
                WHERE principal = $1 AND domain = $2 LIMIT 1
            """
            result = await conn.fetchrow(query, principal, domain)

            if result:
                feature_mean = result.get("feature_mean", [])
                feature_stddev = result.get("feature_stddev", [])

                # Compute deviations for numeric features
                deviations = []
                for i, (f, mean, std) in enumerate(
                    zip(features, feature_mean or [], feature_stddev or [])
                ):
                    if std and std > 0:
                        deviation = (f - mean) / std
                        deviations.append(abs(deviation))
                    else:
                        deviations.append(0.0)

                max_baseline_deviation = max(deviations) if deviations else 0.0
            else:
                max_baseline_deviation = 0.0

        finally:
            await conn.close()

        # Compute combined score
        combined_score = compute_combined_score(if_score, max_baseline_deviation, domain)
        severity = compute_severity(combined_score)

        # Check threshold
        config = DOMAIN_CONFIG.get(domain, DOMAIN_CONFIG["default"])
        threshold = config["anomaly_threshold"]

        is_flagged = combined_score >= threshold

        if is_flagged:
            top_features = get_top_contributing_features(
                features, FEATURE_NAMES, model, top_k=3
            )

            return {
                "anomaly_score": combined_score,
                "severity": severity,
                "top_features": top_features,
                "baseline_deviations": {
                    "max_deviation": max_baseline_deviation,
                },
                "is_flagged": True,
            }

        return None

    except Exception as e:
        logger.error(f"Error in anomaly detection pipeline: {e}")
        return None


async def update_entity_baselines(
    db: AsyncSession, principal: str, domain: str
) -> None:
    """
    Recompute entity baselines from last 30 days of events.

    Updates entity_baselines table with:
    - sample_count: Total events in period
    - feature_mean: Mean of each feature
    - feature_stddev: Standard deviation of each feature
    - risk_score: Risk assessment (0-1)

    Args:
        db: Database session
        principal: User/entity principal
        domain: Domain
    """
    try:
        import asyncpg
        import json

        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="saia",
            password="saia_password",
            database="saia_db",
        )

        try:
            # Get events from last 30 days
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

            query = """
                SELECT id, timestamp, source, event_type, principal, action,
                       resource, result, source_ip, asset_id, domain, raw_log
                FROM log_event
                WHERE principal = $1 AND domain = $2 AND timestamp >= $3
                ORDER BY timestamp DESC
                LIMIT 10000
            """

            events = await conn.fetch(query, principal, domain, thirty_days_ago)
            sample_count = len(events)

            if sample_count < 10:
                logger.warning(
                    f"Not enough samples for {principal}/{domain}: {sample_count}"
                )
                return

            # Extract features for all events
            feature_matrix = []
            for event_row in events:
                event = {
                    "timestamp": event_row["timestamp"],
                    "source": event_row["source"],
                    "event_type": event_row["event_type"],
                    "principal": event_row["principal"],
                    "action": event_row["action"],
                    "resource": event_row["resource"],
                    "result": event_row["result"],
                    "source_ip": event_row["source_ip"],
                    "asset_id": event_row["asset_id"],
                    "domain": event_row["domain"],
                    "raw_log": event_row["raw_log"] or {},
                }

                try:
                    features = await extract_features(db, event)
                    feature_matrix.append(features)
                except Exception as e:
                    logger.warning(f"Error extracting features: {e}")
                    continue

            if not feature_matrix:
                logger.warning(f"No features extracted for {principal}/{domain}")
                return

            # Compute statistics
            from statistics import mean, stdev

            num_features = len(feature_matrix[0])
            feature_mean = []
            feature_stddev = []

            for i in range(num_features):
                values = [fm[i] for fm in feature_matrix]
                feature_mean.append(mean(values) if values else 0.0)

                if len(values) > 1:
                    feature_stddev.append(stdev(values))
                else:
                    feature_stddev.append(0.0)

            # Compute simple risk score
            # Higher variance = potentially more risky
            avg_stddev = mean(feature_stddev) if feature_stddev else 0.0
            risk_score = min(avg_stddev / 2.0, 1.0)  # Normalize

            # Upsert baseline
            upsert_query = """
                INSERT INTO entity_baselines
                    (principal, domain, sample_count, feature_mean,
                     feature_stddev, risk_score, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (principal, domain)
                DO UPDATE SET
                    sample_count = $3,
                    feature_mean = $4,
                    feature_stddev = $5,
                    risk_score = $6,
                    updated_at = $7
            """

            now = datetime.now(timezone.utc)

            await conn.execute(
                upsert_query,
                principal,
                domain,
                sample_count,
                json.dumps(feature_mean),
                json.dumps(feature_stddev),
                risk_score,
                now,
            )

            logger.info(
                f"Updated baseline for {principal}/{domain}: {sample_count} samples"
            )

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"Error updating entity baselines: {e}")
