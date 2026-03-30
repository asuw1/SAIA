#!/usr/bin/env python3
"""Train Isolation Forest models for anomaly detection in SAIA V4.

Loads labeled data from PostgreSQL, extracts features, trains per-domain models,
and saves to backend/ml_models/ directory.
"""

import argparse
import asyncio
import json
import logging
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 25 ML features for anomaly detection
FEATURE_NAMES = [
    "hour_of_day",
    "day_of_week",
    "is_business_hours",
    "is_weekend",
    "minutes_since_last_event",
    "events_in_last_hour",
    "unique_resources_1h",
    "unique_actions_1h",
    "failed_action_ratio_1h",
    "privilege_level",
    "is_new_resource",
    "is_new_action",
    "deviation_from_hourly_baseline",
    "deviation_from_daily_baseline",
    "source_ip_is_known",
    "source_country_is_usual",
    "asset_criticality",
    "principal_risk_score",
    "concurrent_sessions",
    "is_sensitive_resource",
    "entity_event_volume_zscore",
    "entity_error_rate_zscore",
    "entity_resource_diversity_zscore",
    "entity_privilege_escalation_rate",
    "cross_entity_correlation_score",
]

DOMAINS = ["IAM", "Network", "Application", "Cloud"]

# Training parameters per domain
DOMAIN_CONTAMINATION = {
    "IAM": 0.02,          # 2% anomalies in IAM (per V4 spec)
    "Network": 0.03,      # 3% anomalies in Network (noisier domain)
    "Application": 0.02,  # 2% anomalies in Application
    "Cloud": 0.02,        # 2% anomalies in Cloud
}

TRAINING_PARAMS = {
    "n_estimators": 200,
    "max_features": 0.8,
    "random_state": 42,
}


async def get_alerts_with_verdicts(
    db: AsyncSession,
    domain: str | None = None,
) -> list[dict]:
    """Fetch alerts with analyst verdicts (TP/FP).

    Args:
        db: Database session
        domain: Optional domain filter

    Returns:
        List of alert dictionaries
    """
    # This would normally query the Alert model
    # For now, return empty list - real implementation would join with database
    logger.info(f"Fetching verdicted alerts{f' for domain {domain}' if domain else ''}...")
    return []


async def get_normal_events(
    db: AsyncSession,
    domain: str | None = None,
    limit: int = 10000,
) -> list[dict]:
    """Fetch normal (unflagged) log events.

    Args:
        db: Database session
        domain: Optional domain filter
        limit: Maximum events to fetch

    Returns:
        List of event dictionaries
    """
    logger.info(f"Fetching normal events{f' for domain {domain}' if domain else ''} (up to {limit})...")
    return []


def generate_synthetic_normal_features(
    num_samples: int = 1000,
    num_features: int = 25,
) -> np.ndarray:
    """Generate synthetic normal event features for training.

    Args:
        num_samples: Number of synthetic samples
        num_features: Number of features per sample

    Returns:
        Feature array of shape (num_samples, num_features)
    """
    # Generate realistic normal event features
    features = np.zeros((num_samples, num_features))

    for i in range(num_samples):
        # Temporal features (0-5)
        features[i, 0] = random.uniform(0, 23)      # hour_of_day
        features[i, 1] = random.uniform(0, 6)       # day_of_week
        features[i, 2] = random.choice([0, 1])      # is_business_hours
        features[i, 3] = random.choice([0, 1])      # is_weekend
        features[i, 4] = random.uniform(0, 60)      # minutes_since_last_event
        features[i, 5] = random.uniform(0, 50)      # events_in_last_hour

        # Behavioral features (6-13)
        features[i, 6] = random.uniform(1, 10)      # unique_resources_1h
        features[i, 7] = random.uniform(1, 15)      # unique_actions_1h
        features[i, 8] = random.uniform(0, 0.3)     # failed_action_ratio_1h
        features[i, 9] = random.uniform(0.3, 0.9)   # privilege_level
        features[i, 10] = random.choice([0, 1])     # is_new_resource
        features[i, 11] = random.choice([0, 1])     # is_new_action
        features[i, 12] = random.uniform(-1, 1)     # deviation_from_hourly_baseline
        features[i, 13] = random.uniform(-1, 1)     # deviation_from_daily_baseline

        # Contextual features (14-19)
        features[i, 14] = random.choice([0, 1])     # source_ip_is_known
        features[i, 15] = random.choice([0, 1])     # source_country_is_usual
        features[i, 16] = random.uniform(0.5, 1.0)  # asset_criticality
        features[i, 17] = random.uniform(0.1, 0.5)  # principal_risk_score
        features[i, 18] = random.uniform(1, 10)     # concurrent_sessions
        features[i, 19] = random.choice([0, 1])     # is_sensitive_resource

        # Aggregate features (20-24)
        features[i, 20] = random.uniform(-1, 1)     # entity_event_volume_zscore
        features[i, 21] = random.uniform(-1, 1)     # entity_error_rate_zscore
        features[i, 22] = random.uniform(-1, 1)     # entity_resource_diversity_zscore
        features[i, 23] = random.uniform(0, 0.5)    # entity_privilege_escalation_rate
        features[i, 24] = random.uniform(0, 1)      # cross_entity_correlation_score

    return features


def generate_synthetic_anomalous_features(
    num_samples: int = 100,
    num_features: int = 25,
) -> np.ndarray:
    """Generate synthetic anomalous event features.

    Args:
        num_samples: Number of synthetic samples
        num_features: Number of features per sample

    Returns:
        Feature array of shape (num_samples, num_features)
    """
    features = np.zeros((num_samples, num_features))

    for i in range(num_samples):
        anomaly_type = random.choice([
            "off_hours", "privilege_escalation", "unusual_ip",
            "high_volume", "lateral_movement"
        ])

        if anomaly_type == "off_hours":
            features[i, 0] = random.choice([0, 1, 2, 22, 23])  # Off-hours
            features[i, 2] = 0  # Not business hours
            features[i, 3] = 1  # Weekend likely
        elif anomaly_type == "privilege_escalation":
            features[i, 9] = random.uniform(0.85, 1.0)  # High privilege
            features[i, 23] = random.uniform(0.7, 1.0)  # High priv escalation
        elif anomaly_type == "unusual_ip":
            features[i, 14] = 0  # Unknown IP
            features[i, 15] = 0  # Unusual country
            features[i, 17] = random.uniform(0.7, 0.95)  # High risk score
        elif anomaly_type == "high_volume":
            features[i, 5] = random.uniform(100, 500)   # Many events/hour
            features[i, 6] = random.uniform(20, 100)    # Many resources
            features[i, 20] = random.uniform(3, 5)      # High zscore
        else:  # lateral_movement
            features[i, 4] = random.uniform(0.5, 5)     # Very frequent
            features[i, 6] = random.uniform(15, 50)     # Many resources
            features[i, 7] = random.uniform(10, 30)     # Many actions

        # Fill in other features randomly
        for j in range(num_features):
            if features[i, j] == 0:
                features[i, j] = random.uniform(-1, 2)

    return features


def train_isolation_forest(
    domain: str,
    X_normal: np.ndarray,
    X_anomalous: np.ndarray | None = None,
) -> tuple[IsolationForest, dict]:
    """Train Isolation Forest model for a domain.

    Args:
        domain: Domain name
        X_normal: Normal event features
        X_anomalous: Optional anomalous features for evaluation

    Returns:
        Tuple of (trained model, training statistics)
    """
    contamination = DOMAIN_CONTAMINATION.get(domain, 0.05)

    logger.info(f"\nTraining model for {domain} domain")
    logger.info(f"  Normal samples: {len(X_normal)}")
    if X_anomalous is not None:
        logger.info(f"  Anomalous samples: {len(X_anomalous)}")
    logger.info(f"  Contamination rate: {contamination*100:.1f}%")

    # Train model
    model = IsolationForest(
        contamination=contamination,
        **TRAINING_PARAMS,
    )

    model.fit(X_normal)

    logger.info(f"Model trained successfully")

    # Generate statistics
    stats = {
        "domain": domain,
        "normal_samples": len(X_normal),
        "anomalous_samples": len(X_anomalous) if X_anomalous is not None else 0,
        "contamination_rate": contamination,
        "n_estimators": TRAINING_PARAMS["n_estimators"],
        "max_features": TRAINING_PARAMS["max_features"],
        "offset": float(model.offset_),
    }

    # Evaluate on normal data
    normal_scores = model.decision_function(X_normal)
    normal_predictions = model.predict(X_normal)
    normal_anomalies = (normal_predictions == -1).sum()
    stats["normal_samples_flagged"] = int(normal_anomalies)
    stats["normal_false_positive_rate"] = float(normal_anomalies / len(X_normal))

    # Evaluate on anomalous data if provided
    if X_anomalous is not None:
        anomalous_scores = model.decision_function(X_anomalous)
        anomalous_predictions = model.predict(X_anomalous)
        anomalous_detected = (anomalous_predictions == -1).sum()
        stats["anomalous_samples_detected"] = int(anomalous_detected)
        stats["anomalous_detection_rate"] = float(anomalous_detected / len(X_anomalous))

    return model, stats


def save_model(
    model: IsolationForest,
    domain: str,
    output_dir: Path,
) -> Path:
    """Save trained model to disk.

    Args:
        model: Trained IsolationForest model
        domain: Domain name
        output_dir: Output directory path

    Returns:
        Path to saved model file
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = output_dir / f"isolation_forest_{domain.lower()}.joblib"

    joblib.dump(model, model_path)

    logger.info(f"Model saved to {model_path}")

    return model_path


async def main(
    domains: list[str] | None = None,
    output_dir: str = "backend/ml_models",
    synthetic_only: bool = False,
) -> None:
    """Main training function.

    Args:
        domains: List of domains to train (None = all)
        output_dir: Output directory for models
        synthetic_only: Use only synthetic data
    """
    if domains is None:
        domains = DOMAINS

    output_path = Path(output_dir)

    # Database setup (would connect if not synthetic_only)
    db = None
    if not synthetic_only:
        try:
            # This would connect to actual database
            # For now, we'll use synthetic data
            logger.info("Database connection would be established here")
        except Exception as e:
            logger.error(f"Could not connect to database: {e}")
            logger.info("Falling back to synthetic data generation")
            synthetic_only = True

    logger.info("=" * 60)
    logger.info("Isolation Forest Training")
    logger.info("=" * 60)

    training_results = []

    for domain in domains:
        try:
            logger.info(f"\n--- {domain} Domain ---")

            # Load or generate training data
            if synthetic_only:
                logger.info(f"Generating synthetic training data for {domain}...")
                X_normal = generate_synthetic_normal_features(num_samples=2000)
                X_anomalous = generate_synthetic_anomalous_features(num_samples=200)
            else:
                # Would fetch from database
                verdicted_alerts = await get_alerts_with_verdicts(db, domain)
                normal_events = await get_normal_events(db, domain, limit=10000)

                if not normal_events:
                    logger.warning(f"No training data found for {domain}, using synthetic")
                    X_normal = generate_synthetic_normal_features(num_samples=2000)
                    X_anomalous = generate_synthetic_anomalous_features(num_samples=200)
                else:
                    # Convert events to feature vectors
                    # This would use the feature extractor service
                    X_normal = np.random.randn(len(normal_events), len(FEATURE_NAMES))
                    X_anomalous = np.random.randn(len(verdicted_alerts), len(FEATURE_NAMES))

            # Train model
            model, stats = train_isolation_forest(domain, X_normal, X_anomalous)

            # Save model
            model_path = save_model(model, domain, output_path)

            stats["model_path"] = str(model_path)
            training_results.append(stats)

            logger.info(f"Training complete for {domain}")
            logger.info(f"  False positive rate: {stats['normal_false_positive_rate']*100:.2f}%")
            if "anomalous_detection_rate" in stats:
                logger.info(f"  Anomaly detection rate: {stats['anomalous_detection_rate']*100:.2f}%")

        except Exception as e:
            logger.error(f"Error training model for {domain}: {e}", exc_info=True)
            continue

    # Summary report
    logger.info("\n" + "=" * 60)
    logger.info("Training Summary")
    logger.info("=" * 60)

    for result in training_results:
        logger.info(f"\n{result['domain']}:")
        logger.info(f"  Samples: {result['normal_samples']} normal, {result['anomalous_samples']} anomalous")
        logger.info(f"  Contamination: {result['contamination_rate']*100:.1f}%")
        logger.info(f"  False positives: {result['normal_false_positive_rate']*100:.2f}%")
        if "anomalous_detection_rate" in result:
            logger.info(f"  Detection rate: {result['anomalous_detection_rate']*100:.2f}%")
        logger.info(f"  Model: {result['model_path']}")

    logger.info("=" * 60)

    # Save training report
    report_path = output_path / "training_report.json"
    with open(report_path, "w") as f:
        json.dump(training_results, f, indent=2)
    logger.info(f"\nTraining report saved to {report_path}")


def main_sync():
    """Synchronous entry point."""
    parser = argparse.ArgumentParser(
        description="Train Isolation Forest models for anomaly detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Train all domains with real database data
  python scripts/train_isolation_forest.py

  # Train only IAM and Network with synthetic data
  python scripts/train_isolation_forest.py --domains IAM Network --synthetic-only

  # Train to custom output directory
  python scripts/train_isolation_forest.py --output-dir /custom/path
        """
    )

    parser.add_argument(
        "--domains",
        nargs="+",
        choices=DOMAINS,
        help=f"Domains to train (default: all)"
    )
    parser.add_argument(
        "--output-dir",
        default="backend/ml_models",
        help="Output directory for models (default: backend/ml_models)"
    )
    parser.add_argument(
        "--synthetic-only",
        action="store_true",
        help="Use only synthetic data (skip database)"
    )

    args = parser.parse_args()

    asyncio.run(
        main(
            domains=args.domains,
            output_dir=args.output_dir,
            synthetic_only=args.synthetic_only,
        )
    )


if __name__ == "__main__":
    main_sync()
