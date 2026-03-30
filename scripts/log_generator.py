#!/usr/bin/env python3
"""Demo synthetic log generator for SAIA V4.

Generates realistic security log events and sends them to POST /api/v1/logs/ingest.
Includes both normal business events and synthetic anomalies for testing.
"""

import argparse
import asyncio
import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Entity names
USERS = [f"user_{i:03d}" for i in range(1, 51)]

# Domain-specific resources
RESOURCES = {
    "IAM": [
        "ldap_server", "okta_instance", "oauth_provider",
        "mfa_service", "password_vault", "user_db", "auth_service"
    ],
    "Network": [
        "vpn_gateway", "firewall_external", "firewall_internal",
        "proxy_server", "dns_server", "nat_gateway", "load_balancer",
        "router_core", "switch_access", "wlan_controller"
    ],
    "Application": [
        "api_gateway", "web_app", "database", "cache_server",
        "message_queue", "file_server", "search_service",
        "report_engine", "crm_system", "erp_system"
    ],
    "Cloud": [
        "s3_bucket", "rds_instance", "lambda_function",
        "ec2_instance", "cloud_storage", "kms_service",
        "iam_role", "security_group", "vpc"
    ]
}

# Action types per domain
ACTIONS = {
    "IAM": [
        "login", "logout", "mfa_challenge", "password_reset",
        "permission_grant", "permission_revoke", "account_unlock",
        "role_assignment", "group_membership_change"
    ],
    "Network": [
        "connection_establish", "connection_close", "dns_query",
        "traffic_block", "port_scan", "packet_drop", "bandwidth_limit"
    ],
    "Application": [
        "api_request", "data_access", "file_read", "file_write",
        "query_execution", "cache_hit", "cache_miss", "error_occurred"
    ],
    "Cloud": [
        "bucket_access", "instance_launch", "instance_terminate",
        "volume_attach", "volume_detach", "security_group_update",
        "role_assumption", "api_call", "config_change"
    ]
}

# Source systems per domain
SOURCES = {
    "IAM": ["okta", "ldap_server", "azure_ad"],
    "Network": ["firewall", "vpn_gateway", "proxy", "ids_system"],
    "Application": ["app_logs", "database_audit", "api_gateway"],
    "Cloud": ["cloudtrail", "cloudwatch", "vpc_flow_logs"]
}

# Result values
RESULTS = ["success", "failure", "blocked", "denied", "error"]

# Saudi Arabia business hours: Sunday-Thursday 7 AM - 6 PM
BUSINESS_HOURS_DAYS = {0, 1, 2, 3, 4}  # Sun=0 in Python's weekday
BUSINESS_HOURS_START = 7
BUSINESS_HOURS_END = 18

# IP address pools
NORMAL_IP_POOLS = [
    "192.168.1.0/24",   # Corporate network
    "10.0.0.0/8",       # VPN range
    "203.0.113.0/24",   # Saudi corporate ISP
]

ANOMALOUS_IP_POOLS = [
    "198.51.100.0/24",  # Unusual external ISP
    "192.0.2.0/24",     # Another external provider
    "156.0.0.0/8",      # Rare source country
]


def ip_from_pool(pool_cidr: str) -> str:
    """Generate random IP from CIDR pool."""
    parts = pool_cidr.split("/")[0].split(".")
    base = ".".join(parts[:3])
    host = random.randint(1, 254)
    return f"{base}.{host}"


def is_business_hours(dt: datetime) -> bool:
    """Check if datetime is during Saudi business hours."""
    iso_day = (dt.weekday() + 1) % 7  # Convert to ISO (Sun=0)
    return (iso_day in BUSINESS_HOURS_DAYS and
            BUSINESS_HOURS_START <= dt.hour < BUSINESS_HOURS_END)


def generate_normal_event(domain: str, base_time: datetime) -> dict:
    """Generate a realistic normal business event."""
    if domain == "IAM":
        return {
            "timestamp": base_time.isoformat(),
            "source": random.choice(SOURCES[domain]),
            "event_type": "authentication",
            "principal": random.choice(USERS),
            "action": random.choice(ACTIONS[domain]),
            "resource": random.choice(RESOURCES[domain]),
            "result": random.choice(["success", "success", "failure"]),
            "source_ip": ip_from_pool(random.choice(NORMAL_IP_POOLS)),
            "asset_id": "auth_cluster_001",
            "domain": domain,
        }
    elif domain == "Network":
        return {
            "timestamp": base_time.isoformat(),
            "source": random.choice(SOURCES[domain]),
            "event_type": "network_flow",
            "principal": random.choice(USERS),
            "action": random.choice(ACTIONS[domain]),
            "resource": random.choice(RESOURCES[domain]),
            "result": random.choice(["success", "success", "blocked"]),
            "source_ip": ip_from_pool(random.choice(NORMAL_IP_POOLS)),
            "asset_id": random.choice(["fw_001", "fw_002", "vpn_001"]),
            "domain": domain,
        }
    elif domain == "Application":
        return {
            "timestamp": base_time.isoformat(),
            "source": random.choice(SOURCES[domain]),
            "event_type": "application_event",
            "principal": random.choice(USERS),
            "action": random.choice(ACTIONS[domain]),
            "resource": random.choice(RESOURCES[domain]),
            "result": random.choice(["success", "success", "error"]),
            "source_ip": ip_from_pool(random.choice(NORMAL_IP_POOLS)),
            "asset_id": random.choice(["app_01", "app_02", "app_03"]),
            "domain": domain,
        }
    else:  # Cloud
        return {
            "timestamp": base_time.isoformat(),
            "source": random.choice(SOURCES[domain]),
            "event_type": "cloud_api_call",
            "principal": random.choice(USERS),
            "action": random.choice(ACTIONS[domain]),
            "resource": random.choice(RESOURCES[domain]),
            "result": random.choice(["success", "success", "denied"]),
            "source_ip": ip_from_pool(random.choice(NORMAL_IP_POOLS)),
            "asset_id": random.choice(["account_001", "account_002"]),
            "domain": domain,
        }


def generate_anomalous_event(domain: str, base_time: datetime) -> dict:
    """Generate a synthetic anomalous event."""
    anomaly_type = random.choice([
        "brute_force", "privilege_escalation", "off_hours_access",
        "unusual_ip", "lateral_movement", "suspicious_resource_access"
    ])

    if anomaly_type == "brute_force":
        return {
            "timestamp": base_time.isoformat(),
            "source": random.choice(SOURCES[domain]),
            "event_type": "failed_login_attempt",
            "principal": random.choice(USERS),
            "action": "login",
            "resource": "ldap_server",
            "result": "failure",
            "source_ip": ip_from_pool(random.choice(ANOMALOUS_IP_POOLS)),
            "asset_id": "auth_cluster_001",
            "domain": domain,
        }
    elif anomaly_type == "privilege_escalation":
        return {
            "timestamp": base_time.isoformat(),
            "source": random.choice(SOURCES[domain]),
            "event_type": "privilege_change",
            "principal": random.choice(USERS),
            "action": "permission_grant",
            "resource": random.choice(RESOURCES[domain]),
            "result": "success",
            "source_ip": ip_from_pool(random.choice(NORMAL_IP_POOLS)),
            "asset_id": "auth_cluster_001",
            "domain": domain,
        }
    elif anomaly_type == "off_hours_access":
        # Generate an off-hours timestamp
        off_hours_time = base_time.replace(hour=random.choice([0, 1, 2, 23, 22]))
        off_hours_day = random.choice([5, 6])  # Friday or Saturday
        off_hours_time = off_hours_time.replace(
            day=off_hours_time.day + (off_hours_day - ((off_hours_time.weekday() + 1) % 7))
        )
        return {
            "timestamp": off_hours_time.isoformat(),
            "source": random.choice(SOURCES[domain]),
            "event_type": random.choice(["authentication", "data_access"]),
            "principal": random.choice(USERS),
            "action": random.choice(ACTIONS[domain]),
            "resource": random.choice(RESOURCES[domain]),
            "result": "success",
            "source_ip": ip_from_pool(random.choice(NORMAL_IP_POOLS)),
            "asset_id": random.choice(RESOURCES[domain]),
            "domain": domain,
        }
    elif anomaly_type == "unusual_ip":
        return {
            "timestamp": base_time.isoformat(),
            "source": random.choice(SOURCES[domain]),
            "event_type": "authentication",
            "principal": random.choice(USERS),
            "action": "login",
            "resource": random.choice(RESOURCES[domain]),
            "result": "success",
            "source_ip": ip_from_pool(random.choice(ANOMALOUS_IP_POOLS)),
            "asset_id": "auth_cluster_001",
            "domain": domain,
        }
    elif anomaly_type == "lateral_movement":
        return {
            "timestamp": base_time.isoformat(),
            "source": random.choice(SOURCES[domain]),
            "event_type": "network_flow",
            "principal": random.choice(USERS),
            "action": "connection_establish",
            "resource": random.choice(RESOURCES[domain]),
            "result": "success",
            "source_ip": ip_from_pool(random.choice(ANOMALOUS_IP_POOLS)),
            "asset_id": random.choice(["fw_001", "fw_002"]),
            "domain": domain,
        }
    else:  # suspicious_resource_access
        return {
            "timestamp": base_time.isoformat(),
            "source": random.choice(SOURCES[domain]),
            "event_type": "data_access",
            "principal": random.choice(USERS),
            "action": "file_read",
            "resource": "password_vault",
            "result": "success",
            "source_ip": ip_from_pool(random.choice(ANOMALOUS_IP_POOLS)),
            "asset_id": "sensitive_001",
            "domain": domain,
        }


def generate_batch(
    min_events: int = 10,
    max_events: int = 30,
    domains: list[str] | None = None,
    anomaly_ratio: float = 0.05,
) -> dict:
    """Generate a batch of log events.

    Args:
        min_events: Minimum events in batch
        max_events: Maximum events in batch
        domains: List of domains to include
        anomaly_ratio: Percentage of anomalous events (0.0-1.0)

    Returns:
        Dictionary with source_name, domain, and events list
    """
    if domains is None:
        domains = ["IAM", "Network", "Application", "Cloud"]

    num_events = random.randint(min_events, max_events)
    domain = random.choice(domains)

    events = []
    now = datetime.now(timezone.utc)

    for _ in range(num_events):
        # Vary timestamp within last 5 minutes
        offset_seconds = random.randint(0, 300)
        event_time = now - timedelta(seconds=offset_seconds)

        if random.random() < anomaly_ratio:
            event = generate_anomalous_event(domain, event_time)
        else:
            event = generate_normal_event(domain, event_time)

        events.append(event)

    return {
        "source_name": f"synthetic_log_source_{domain.lower()}",
        "domain": domain,
        "events": events,
    }


async def send_batch(
    client: httpx.AsyncClient,
    batch: dict,
    url: str,
    token: str,
) -> bool:
    """Send a batch of events to the API.

    Args:
        client: HTTP client
        batch: Batch dictionary from generate_batch()
        url: API URL (base URL without path)
        token: JWT authentication token

    Returns:
        True if successful, False otherwise
    """
    endpoint = f"{url.rstrip('/')}/api/v1/logs/ingest"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        response = await client.post(
            endpoint,
            json=batch,
            headers=headers,
            timeout=30.0,
        )

        if response.status_code in (200, 201):
            data = response.json()
            logger.info(
                f"Batch sent: {data.get('events_accepted', 0)} accepted, "
                f"{data.get('events_quarantined', 0)} quarantined from "
                f"{data.get('events_parsed', 0)} parsed"
            )
            return True
        else:
            logger.error(
                f"Failed to send batch: {response.status_code} - {response.text}"
            )
            return False

    except Exception as e:
        logger.error(f"Error sending batch: {e}")
        return False


async def run_generator(
    url: str,
    token: str,
    duration_seconds: int = 0,
    interval_seconds: int = 5,
    min_events: int = 10,
    max_events: int = 30,
    domains: list[str] | None = None,
    anomaly_ratio: float = 0.05,
) -> None:
    """Run the log generator.

    Args:
        url: Target API base URL
        token: JWT authentication token
        duration_seconds: How long to run (0 = infinite)
        interval_seconds: Seconds between batches
        min_events: Minimum events per batch
        max_events: Maximum events per batch
        domains: List of domains to generate events for
        anomaly_ratio: Percentage of anomalous events (0.0-1.0)
    """
    if domains is None:
        domains = ["IAM", "Network", "Application", "Cloud"]

    logger.info(
        f"Starting log generator for domains: {', '.join(domains)}"
    )
    logger.info(f"Sending batches every {interval_seconds} seconds")
    logger.info(f"Anomaly ratio: {anomaly_ratio*100:.1f}%")

    start_time = datetime.now(timezone.utc)
    batch_count = 0
    event_count = 0
    success_count = 0
    failed_count = 0

    async with httpx.AsyncClient() as client:
        while True:
            # Check duration
            if duration_seconds > 0:
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                if elapsed >= duration_seconds:
                    logger.info(
                        f"Duration ({duration_seconds}s) reached. Stopping."
                    )
                    break

            # Generate and send batch
            batch = generate_batch(
                min_events=min_events,
                max_events=max_events,
                domains=domains,
                anomaly_ratio=anomaly_ratio,
            )

            success = await send_batch(client, batch, url, token)

            batch_count += 1
            event_count += len(batch["events"])
            if success:
                success_count += 1
            else:
                failed_count += 1

            # Print statistics every 10 batches
            if batch_count % 10 == 0:
                logger.info(
                    f"Progress: {batch_count} batches, "
                    f"{event_count} events, "
                    f"{success_count} successful, "
                    f"{failed_count} failed"
                )

            # Wait before next batch
            await asyncio.sleep(interval_seconds)

    # Final statistics
    logger.info("\n" + "=" * 60)
    logger.info("Generator Summary")
    logger.info("=" * 60)
    logger.info(f"Total batches sent: {batch_count}")
    logger.info(f"Total events generated: {event_count}")
    logger.info(f"Successful batches: {success_count}")
    logger.info(f"Failed batches: {failed_count}")
    logger.info(f"Success rate: {(success_count/batch_count*100):.1f}%")
    logger.info("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic security logs for SAIA V4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Send logs to localhost:8000 every 5 seconds
  python scripts/log_generator.py --url http://localhost:8000 --token YOUR_JWT_TOKEN

  # Send to production for 1 hour with custom batch sizes
  python scripts/log_generator.py \\
    --url https://saia.example.com \\
    --token YOUR_JWT_TOKEN \\
    --duration 3600 \\
    --interval 10 \\
    --min-events 20 \\
    --max-events 50

  # Generate only Cloud and Network events with 10% anomaly ratio
  python scripts/log_generator.py \\
    --url http://localhost:8000 \\
    --token YOUR_JWT_TOKEN \\
    --domains Cloud Network \\
    --anomaly-ratio 0.10
        """
    )

    parser.add_argument(
        "--url",
        required=True,
        help="Target API URL (e.g., http://localhost:8000)"
    )
    parser.add_argument(
        "--token",
        required=True,
        help="JWT authentication token"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=0,
        help="Duration in seconds (0 = infinite, default: 0)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Seconds between batches (default: 5)"
    )
    parser.add_argument(
        "--min-events",
        type=int,
        default=10,
        help="Minimum events per batch (default: 10)"
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=30,
        help="Maximum events per batch (default: 30)"
    )
    parser.add_argument(
        "--domains",
        nargs="+",
        choices=["IAM", "Network", "Application", "Cloud"],
        default=["IAM", "Network", "Application", "Cloud"],
        help="Domains to generate events for (default: all)"
    )
    parser.add_argument(
        "--anomaly-ratio",
        type=float,
        default=0.05,
        help="Ratio of anomalous events (0.0-1.0, default: 0.05)"
    )

    args = parser.parse_args()

    # Validate anomaly ratio
    if not 0.0 <= args.anomaly_ratio <= 1.0:
        parser.error("--anomaly-ratio must be between 0.0 and 1.0")

    # Run generator
    asyncio.run(
        run_generator(
            url=args.url,
            token=args.token,
            duration_seconds=args.duration,
            interval_seconds=args.interval,
            min_events=args.min_events,
            max_events=args.max_events,
            domains=args.domains,
            anomaly_ratio=args.anomaly_ratio,
        )
    )


if __name__ == "__main__":
    main()
