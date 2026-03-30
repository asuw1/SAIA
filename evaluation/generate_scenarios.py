#!/usr/bin/env python3
"""Generate evaluation scenarios for SAIA V4.

Creates 50 evaluation scenarios (30 violation, 10 benign, 5 cold-start, 5 edge-case)
with background normal events and injected test events.

Each scenario is saved as a separate JSON file with event data and ground truth metadata.
Matches the NCA ECC 2:2024 clause reference format (e.g., "2-2-1").
"""

import argparse
import json
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

USERS = [f"user_{i:03d}" for i in range(1, 51)]

RESOURCES = {
    "IAM": [
        "HR_DATABASE", "EMAIL_SERVER", "LDAP_SERVER", "OKTA_INSTANCE",
        "MFA_SERVICE", "PASSWORD_VAULT", "USER_DB", "AUTH_SERVICE",
    ],
    "Network": [
        "VPN_GATEWAY", "FIREWALL_EXT", "FIREWALL_INT", "PROXY_SERVER",
        "DNS_SERVER", "NAT_GATEWAY", "LOAD_BALANCER", "ROUTER_CORE",
    ],
    "Application": [
        "API_GATEWAY", "WEB_APP", "DATABASE_MAIN", "CACHE_SERVER",
        "MESSAGE_QUEUE", "FILE_SERVER", "SEARCH_SERVICE", "CRM_SYSTEM",
    ],
    "Cloud": [
        "S3_BUCKET", "RDS_INSTANCE", "LAMBDA_FUNC", "EC2_INSTANCE",
        "CLOUD_STORAGE", "KMS_SERVICE", "IAM_ROLE", "SECURITY_GROUP",
    ],
}

SOURCES = {
    "IAM": ["okta", "ldap_server", "azure_ad"],
    "Network": ["firewall", "vpn_gateway", "proxy", "ids_system"],
    "Application": ["app_logs", "database_audit", "api_gateway"],
    "Cloud": ["cloudtrail", "cloudwatch", "vpc_flow_logs"],
}

NORMAL_IPS = ["192.168.1.", "10.0.1.", "10.0.2.", "203.0.113."]
ANOMALOUS_IPS = ["198.51.100.", "192.0.2.", "156.34.12."]
SA_IPS = ["203.0.113.", "10.0.1.", "10.0.2."]


def _rand_ip(pool: list[str]) -> str:
    return random.choice(pool) + str(random.randint(1, 254))


def _biz_ts(base: datetime) -> datetime:
    """Return a timestamp during Saudi business hours (Sun-Thu 7-18)."""
    d = base + timedelta(hours=random.randint(0, 23))
    # Ensure Sun-Thu
    while d.weekday() in (4, 5):  # Fri=4, Sat=5 in Python weekday
        d += timedelta(days=1)
    d = d.replace(hour=random.randint(7, 17), minute=random.randint(0, 59),
                  second=random.randint(0, 59))
    return d


def _off_hours_ts(base: datetime) -> datetime:
    """Return an off-hours timestamp (late night or weekend)."""
    d = base + timedelta(days=random.randint(0, 6))
    d = d.replace(hour=random.choice([0, 1, 2, 3, 22, 23]),
                  minute=random.randint(0, 59))
    return d


# ── Event generators ─────────────────────────────────────────────────────────

def normal_event(domain: str, ts: datetime) -> dict:
    """Generate a normal business event for the given domain."""
    return {
        "timestamp": ts.isoformat(),
        "source": random.choice(SOURCES[domain]),
        "event_type": random.choice(["authentication", "access", "query"]),
        "principal": random.choice(USERS),
        "action": random.choice(["login", "read", "write", "list", "view"]),
        "resource": random.choice(RESOURCES[domain]),
        "result": random.choices(["success", "failure"], weights=[0.92, 0.08])[0],
        "source_ip": _rand_ip(SA_IPS),
        "asset_id": random.choice(RESOURCES[domain]),
        "domain": domain,
    }


def _background(domain: str, base: datetime, count: int = 1000) -> list[dict]:
    """Generate *count* background normal events spread over 24 h."""
    events = []
    for i in range(count):
        ts = _biz_ts(base + timedelta(seconds=random.randint(0, 86400)))
        events.append(normal_event(domain, ts))
    return events


# ── Scenario definitions (matching arch doc §12.1 exactly) ───────────────────

def _eval_iam_001(base: datetime) -> dict:
    """Brute-force: 20 failed logins in 5 min from single IP, then 1 success."""
    attack_user = "user_eval_target"
    attack_ip = "198.51.100.42"
    bg = _background("IAM", base)
    gt_ids = []
    for i in range(20):
        eid = str(uuid.uuid4())
        gt_ids.append(eid)
        bg.append({
            "timestamp": (base + timedelta(seconds=i * 15)).isoformat(),
            "source": "okta", "event_type": "authentication",
            "principal": attack_user, "action": "login",
            "resource": "HR_DATABASE", "result": "failure",
            "source_ip": attack_ip, "asset_id": "HR_DATABASE",
            "domain": "IAM", "_ground_truth_id": eid,
        })
    eid = str(uuid.uuid4())
    gt_ids.append(eid)
    bg.append({
        "timestamp": (base + timedelta(minutes=5, seconds=10)).isoformat(),
        "source": "okta", "event_type": "authentication",
        "principal": attack_user, "action": "login",
        "resource": "HR_DATABASE", "result": "success",
        "source_ip": attack_ip, "asset_id": "HR_DATABASE",
        "domain": "IAM", "_ground_truth_id": eid,
    })
    return {
        "metadata": {
            "scenario_id": "EVAL-IAM-001",
            "type": "violation",
            "domain": "IAM",
            "description": "20 failed logins in 5 min from single IP, then 1 success",
            "expected_clause": "2-2-1",
            "expected_severity": "High",
            "ground_truth_event_ids": gt_ids,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "events": bg,
    }


def _eval_iam_002(base: datetime) -> dict:
    """Admin login at 3 AM Saturday from non-KSA IP."""
    bg = _background("IAM", base)
    ts = base.replace(hour=3)
    while ts.weekday() != 5:  # Saturday
        ts += timedelta(days=1)
    eid = str(uuid.uuid4())
    bg.append({
        "timestamp": ts.isoformat(),
        "source": "azure_ad", "event_type": "authentication",
        "principal": "admin_001", "action": "admin_login",
        "resource": "HR_DATABASE", "result": "success",
        "source_ip": "156.34.12.88", "asset_id": "HR_DATABASE",
        "domain": "IAM", "_ground_truth_id": eid,
    })
    return {
        "metadata": {
            "scenario_id": "EVAL-IAM-002",
            "type": "violation", "domain": "IAM",
            "description": "Admin login at 3 AM Saturday from non-KSA IP",
            "expected_clause": "2-2-1", "expected_severity": "Critical",
            "ground_truth_event_ids": [eid],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "events": bg,
    }


def _eval_iam_003(base: datetime) -> dict:
    """Impossible travel: Riyadh → London in 30 min."""
    bg = _background("IAM", base)
    user = "user_012"
    ts1 = _biz_ts(base)
    ts2 = ts1 + timedelta(minutes=30)
    ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    bg.append({
        "timestamp": ts1.isoformat(), "source": "okta",
        "event_type": "authentication", "principal": user,
        "action": "login", "resource": "EMAIL_SERVER", "result": "success",
        "source_ip": "203.0.113.10", "asset_id": "EMAIL_SERVER",
        "domain": "IAM", "_ground_truth_id": ids[0],
    })
    bg.append({
        "timestamp": ts2.isoformat(), "source": "okta",
        "event_type": "authentication", "principal": user,
        "action": "login", "resource": "EMAIL_SERVER", "result": "success",
        "source_ip": "156.34.12.55", "asset_id": "EMAIL_SERVER",
        "domain": "IAM", "_ground_truth_id": ids[1],
    })
    return {
        "metadata": {
            "scenario_id": "EVAL-IAM-003",
            "type": "violation", "domain": "IAM",
            "description": "Login from Riyadh, then London 30 min later (same user)",
            "expected_clause": "2-2-1", "expected_severity": "Critical",
            "ground_truth_event_ids": ids,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "events": bg,
    }


def _eval_iam_004(base: datetime) -> dict:
    """Dormant account reactivation: inactive 90 days, accesses 15 resources in 1 h."""
    bg = _background("IAM", base)
    dormant_user = "user_dormant_099"
    ts0 = _biz_ts(base)
    ids = []
    for i in range(15):
        eid = str(uuid.uuid4())
        ids.append(eid)
        bg.append({
            "timestamp": (ts0 + timedelta(minutes=i * 4)).isoformat(),
            "source": "okta", "event_type": "access",
            "principal": dormant_user, "action": "read",
            "resource": random.choice(RESOURCES["IAM"]), "result": "success",
            "source_ip": "203.0.113.77", "asset_id": "HR_DATABASE",
            "domain": "IAM", "_ground_truth_id": eid,
        })
    return {
        "metadata": {
            "scenario_id": "EVAL-IAM-004",
            "type": "violation", "domain": "IAM",
            "description": "Account inactive 90 days, suddenly accesses 15 resources in 1 h",
            "expected_clause": "2-2-4", "expected_severity": "High",
            "ground_truth_event_ids": ids,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "events": bg,
    }


def _eval_iam_005(base: datetime) -> dict:
    """Privilege escalation: user role elevated to admin without change ticket."""
    bg = _background("IAM", base)
    eid = str(uuid.uuid4())
    ts = _biz_ts(base)
    bg.append({
        "timestamp": ts.isoformat(), "source": "okta",
        "event_type": "privilege_change", "principal": "user_025",
        "action": "role_change", "resource": "AUTH_SERVICE", "result": "success",
        "source_ip": "10.0.1.50", "asset_id": "AUTH_SERVICE",
        "domain": "IAM", "_ground_truth_id": eid,
    })
    return {
        "metadata": {
            "scenario_id": "EVAL-IAM-005",
            "type": "violation", "domain": "IAM",
            "description": "User role escalated to admin without corresponding change ticket",
            "expected_clause": "2-2-4", "expected_severity": "Critical",
            "ground_truth_event_ids": [eid],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "events": bg,
    }


def _eval_net_001(base: datetime) -> dict:
    """10× normal outbound traffic to external IP over 2 h."""
    bg = _background("Network", base)
    user = "user_030"
    ts0 = _biz_ts(base)
    ids = []
    for i in range(50):
        eid = str(uuid.uuid4())
        ids.append(eid)
        bg.append({
            "timestamp": (ts0 + timedelta(minutes=i * 2)).isoformat(),
            "source": "firewall", "event_type": "network_flow",
            "principal": user, "action": "connection_establish",
            "resource": "FIREWALL_EXT", "result": "success",
            "source_ip": "10.0.1.30",
            "asset_id": "FIREWALL_EXT", "domain": "Network",
            "_ground_truth_id": eid,
        })
    return {
        "metadata": {
            "scenario_id": "EVAL-NET-001",
            "type": "violation", "domain": "Network",
            "description": "10x normal outbound traffic to external IP over 2 hours",
            "expected_clause": "2-7-3", "expected_severity": "High",
            "ground_truth_event_ids": ids,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "events": bg,
    }


def _eval_net_002(base: datetime) -> dict:
    """Port scan: connection attempts to 50+ ports on single host."""
    bg = _background("Network", base)
    ts0 = _biz_ts(base)
    ids = []
    for i in range(55):
        eid = str(uuid.uuid4())
        ids.append(eid)
        bg.append({
            "timestamp": (ts0 + timedelta(seconds=i * 2)).isoformat(),
            "source": "ids_system", "event_type": "network_flow",
            "principal": "user_040", "action": "connection_establish",
            "resource": f"port_{1000 + i}", "result": "failure",
            "source_ip": "198.51.100.99",
            "asset_id": "ROUTER_CORE", "domain": "Network",
            "_ground_truth_id": eid,
        })
    return {
        "metadata": {
            "scenario_id": "EVAL-NET-002",
            "type": "violation", "domain": "Network",
            "description": "Port scan pattern: connection attempts to 50+ ports on single host",
            "expected_clause": "2-7-1", "expected_severity": "High",
            "ground_truth_event_ids": ids,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "events": bg,
    }


def _eval_log_001(base: datetime) -> dict:
    """Log volume drops 90 % from a source for 18 hours."""
    bg = _background("Application", base, count=200)  # sparse background
    return {
        "metadata": {
            "scenario_id": "EVAL-LOG-001",
            "type": "violation", "domain": "Application",
            "description": "Log volume drops 90% from a source for 18 hours",
            "expected_clause": "2-13-1", "expected_severity": "Medium",
            "ground_truth_event_ids": [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "events": bg,
    }


def _eval_log_002(base: datetime) -> dict:
    """Audit log entries deleted (gap in sequential IDs)."""
    bg = _background("Application", base)
    eid = str(uuid.uuid4())
    ts = _biz_ts(base)
    bg.append({
        "timestamp": ts.isoformat(), "source": "database_audit",
        "event_type": "audit_modification", "principal": "user_admin_001",
        "action": "delete", "resource": "DATABASE_MAIN", "result": "success",
        "source_ip": "10.0.1.5", "asset_id": "DATABASE_MAIN",
        "domain": "Application", "_ground_truth_id": eid,
    })
    return {
        "metadata": {
            "scenario_id": "EVAL-LOG-002",
            "type": "violation", "domain": "Application",
            "description": "Audit log entries deleted (gap in sequential IDs)",
            "expected_clause": "2-9-1", "expected_severity": "Critical",
            "ground_truth_event_ids": [eid],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "events": bg,
    }


def _eval_benign_001(base: datetime) -> dict:
    """5 failed logins during known password-reset campaign (FP test)."""
    bg = _background("IAM", base)
    ts0 = _biz_ts(base)
    for i in range(5):
        bg.append({
            "timestamp": (ts0 + timedelta(minutes=i)).isoformat(),
            "source": "okta", "event_type": "authentication",
            "principal": f"user_{10+i:03d}", "action": "login",
            "resource": "AUTH_SERVICE", "result": "failure",
            "source_ip": "10.0.1.20", "asset_id": "AUTH_SERVICE",
            "domain": "IAM",
        })
    return {
        "metadata": {
            "scenario_id": "EVAL-BENIGN-001",
            "type": "benign", "domain": "IAM",
            "description": "5 failed logins during known password reset campaign (false positive test)",
            "expected_clause": None, "expected_severity": None,
            "ground_truth_event_ids": [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "events": bg,
    }


def _eval_benign_002(base: datetime) -> dict:
    """High traffic during scheduled backup window (FP test)."""
    bg = _background("Network", base)
    ts0 = base.replace(hour=2)  # 2 AM backup window
    for i in range(40):
        bg.append({
            "timestamp": (ts0 + timedelta(seconds=i * 30)).isoformat(),
            "source": "firewall", "event_type": "network_flow",
            "principal": "backup_svc", "action": "connection_establish",
            "resource": "LOAD_BALANCER", "result": "success",
            "source_ip": "10.0.2.100", "asset_id": "LOAD_BALANCER",
            "domain": "Network",
        })
    return {
        "metadata": {
            "scenario_id": "EVAL-BENIGN-002",
            "type": "benign", "domain": "Network",
            "description": "High traffic during scheduled backup window (false positive test)",
            "expected_clause": None, "expected_severity": None,
            "ground_truth_event_ids": [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "events": bg,
    }


def _eval_cold_001(base: datetime) -> dict:
    """New entity performs normal login during business hours — should NOT be flagged by ML."""
    bg = _background("IAM", base)
    ts = _biz_ts(base)
    bg.append({
        "timestamp": ts.isoformat(), "source": "okta",
        "event_type": "authentication", "principal": "new_hire_001",
        "action": "login", "resource": "EMAIL_SERVER", "result": "success",
        "source_ip": "203.0.113.50", "asset_id": "EMAIL_SERVER",
        "domain": "IAM",
    })
    return {
        "metadata": {
            "scenario_id": "EVAL-COLD-001",
            "type": "cold_start", "domain": "IAM",
            "description": "New entity performs normal login during business hours — should NOT be flagged by ML",
            "expected_clause": None, "expected_severity": None,
            "ground_truth_event_ids": [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "events": bg,
    }


def _eval_cold_002(base: datetime) -> dict:
    """New entity performs suspicious admin login at 3 AM — should be caught by rules."""
    bg = _background("IAM", base)
    ts = base.replace(hour=3)
    eid = str(uuid.uuid4())
    bg.append({
        "timestamp": ts.isoformat(), "source": "azure_ad",
        "event_type": "authentication", "principal": "new_hire_002",
        "action": "admin_login", "resource": "HR_DATABASE", "result": "success",
        "source_ip": "156.34.12.99", "asset_id": "HR_DATABASE",
        "domain": "IAM", "_ground_truth_id": eid,
    })
    return {
        "metadata": {
            "scenario_id": "EVAL-COLD-002",
            "type": "cold_start", "domain": "IAM",
            "description": "New entity performs genuinely suspicious activity (admin login at 3 AM) — should be caught by rules even though ML is suppressed",
            "expected_clause": "2-2-1", "expected_severity": "High",
            "ground_truth_event_ids": [eid],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "events": bg,
    }


# ── Generic scenario builder for remaining slots ─────────────────────────────

def _generic_violation(sid: str, domain: str, clause: str, severity: str,
                       desc: str, base: datetime) -> dict:
    bg = _background(domain, base)
    ts = _off_hours_ts(base) if "off-hours" in desc.lower() else _biz_ts(base)
    ids = []
    n = random.randint(3, 12)
    for i in range(n):
        eid = str(uuid.uuid4())
        ids.append(eid)
        bg.append({
            "timestamp": (ts + timedelta(minutes=i * 2)).isoformat(),
            "source": random.choice(SOURCES[domain]),
            "event_type": random.choice(["authentication", "access", "network_flow",
                                          "cloud_api_call", "privilege_change"]),
            "principal": random.choice(USERS),
            "action": random.choice(["login", "read", "write", "delete",
                                      "config_change", "role_change"]),
            "resource": random.choice(RESOURCES[domain]),
            "result": random.choice(["success", "failure"]),
            "source_ip": _rand_ip(ANOMALOUS_IPS),
            "asset_id": random.choice(RESOURCES[domain]),
            "domain": domain, "_ground_truth_id": eid,
        })
    return {
        "metadata": {
            "scenario_id": sid, "type": "violation", "domain": domain,
            "description": desc, "expected_clause": clause,
            "expected_severity": severity,
            "ground_truth_event_ids": ids,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "events": bg,
    }


def _generic_benign(sid: str, domain: str, desc: str, base: datetime) -> dict:
    bg = _background(domain, base, count=1200)
    return {
        "metadata": {
            "scenario_id": sid, "type": "benign", "domain": domain,
            "description": desc, "expected_clause": None,
            "expected_severity": None, "ground_truth_event_ids": [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "events": bg,
    }


def _generic_cold(sid: str, domain: str, desc: str, base: datetime) -> dict:
    bg = _background(domain, base)
    ts = _biz_ts(base)
    bg.append({
        "timestamp": ts.isoformat(), "source": random.choice(SOURCES[domain]),
        "event_type": "authentication",
        "principal": f"new_entity_{random.randint(100, 999)}",
        "action": "login", "resource": random.choice(RESOURCES[domain]),
        "result": "success", "source_ip": _rand_ip(SA_IPS),
        "asset_id": random.choice(RESOURCES[domain]), "domain": domain,
    })
    return {
        "metadata": {
            "scenario_id": sid, "type": "cold_start", "domain": domain,
            "description": desc, "expected_clause": None,
            "expected_severity": None, "ground_truth_event_ids": [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "events": bg,
    }


def _generic_edge(sid: str, domain: str, desc: str, base: datetime) -> dict:
    bg = _background(domain, base)
    ts = _biz_ts(base)
    eid = str(uuid.uuid4())
    bg.append({
        "timestamp": ts.isoformat(), "source": random.choice(SOURCES[domain]),
        "event_type": "access", "principal": random.choice(USERS),
        "action": "read",
        "resource": random.choice(RESOURCES[domain]),
        "result": "success",
        "source_ip": _rand_ip(random.choice([NORMAL_IPS, ANOMALOUS_IPS])),
        "asset_id": random.choice(RESOURCES[domain]),
        "domain": domain, "_ground_truth_id": eid,
    })
    return {
        "metadata": {
            "scenario_id": sid, "type": "edge_case", "domain": domain,
            "description": desc,
            "expected_clause": None, "expected_severity": None,
            "ground_truth_event_ids": [eid],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "events": bg,
    }


# ── Master list ──────────────────────────────────────────────────────────────

EXTRA_VIOLATIONS = [
    # IAM extras
    ("EVAL-IAM-006", "IAM", "2-2-3", "High",
     "Multiple concurrent sessions from geographically distant IPs"),
    ("EVAL-IAM-007", "IAM", "2-2-1", "High",
     "Service account used interactively during off-hours"),
    ("EVAL-IAM-008", "IAM", "2-2-4", "Critical",
     "Mass permission grants to single user within minutes"),
    # Network extras
    ("EVAL-NET-003", "Network", "2-7-3", "High",
     "Large data transfer to external IP at 2 AM"),
    ("EVAL-NET-004", "Network", "2-7-1", "High",
     "DNS tunneling pattern: high-frequency TXT queries to unusual domain"),
    ("EVAL-NET-005", "Network", "2-5-1", "Medium",
     "Unauthorized VLAN hop detected between segmented networks"),
    ("EVAL-NET-006", "Network", "2-7-3", "High",
     "Unusual outbound traffic spike to foreign IP range"),
    # Application extras
    ("EVAL-APP-001", "Application", "2-3-1", "High",
     "Unauthorized configuration change on production database"),
    ("EVAL-APP-002", "Application", "2-9-1", "Critical",
     "Backup deletion by non-admin user"),
    ("EVAL-APP-003", "Application", "2-13-1", "Medium",
     "Sudden spike in application error rate (5x baseline)"),
    ("EVAL-APP-004", "Application", "2-3-1", "High",
     "SQL injection pattern detected in API gateway logs"),
    # Cloud extras
    ("EVAL-CLD-001", "Cloud", "2-7-3", "High",
     "Unauthorized cross-region API calls from service account"),
    ("EVAL-CLD-002", "Cloud", "2-8-1", "Critical",
     "KMS key exported to external account"),
    ("EVAL-CLD-003", "Cloud", "2-3-1", "High",
     "Security group opened to 0.0.0.0/0 on sensitive port"),
    ("EVAL-CLD-004", "Cloud", "2-7-3", "High",
     "Unusual S3 bucket data download volume (10x baseline)"),
    ("EVAL-CLD-005", "Cloud", "2-14-1", "Medium",
     "Third-party integration accessing resources outside agreed scope"),
    # Additional IAM
    ("EVAL-IAM-009", "IAM", "2-2-1", "High",
     "Credential stuffing pattern: many users, same IP, sequential failures"),
    ("EVAL-IAM-010", "IAM", "2-2-4", "Critical",
     "Shadow admin: user gains admin privileges through nested group membership"),
]

EXTRA_BENIGN = [
    ("EVAL-BENIGN-003", "IAM", "Normal user password change during business hours"),
    ("EVAL-BENIGN-004", "Network", "Scheduled vulnerability scan from known scanner IP"),
    ("EVAL-BENIGN-005", "Application", "Batch job producing high log volume at midnight (scheduled)"),
    ("EVAL-BENIGN-006", "Cloud", "Auto-scaling event creating multiple EC2 instances"),
    ("EVAL-BENIGN-007", "IAM", "Multiple logins during company all-hands meeting"),
    ("EVAL-BENIGN-008", "Network", "CDN cache purge causing traffic spike"),
    ("EVAL-BENIGN-009", "Application", "Database migration producing elevated query rate"),
    ("EVAL-BENIGN-010", "Cloud", "CI/CD pipeline deploying across multiple regions"),
]

EXTRA_COLD = [
    ("EVAL-COLD-003", "Network", "New network device joins and starts normal discovery"),
    ("EVAL-COLD-004", "Application", "New microservice instance registers and starts healthchecks"),
    ("EVAL-COLD-005", "Cloud", "New IAM role created and used for first time"),
]

EXTRA_EDGE = [
    ("EVAL-EDGE-001", "IAM", "Borderline: 4 failed logins (threshold is 5)"),
    ("EVAL-EDGE-002", "Network", "Borderline: traffic at exactly 1.5x baseline"),
    ("EVAL-EDGE-003", "Application", "Partial event data: missing source_ip and result fields"),
    ("EVAL-EDGE-004", "Cloud", "Timestamp in unusual timezone format"),
    ("EVAL-EDGE-005", "IAM", "Event with quality score exactly at 0.7 threshold"),
]


def generate_all_scenarios(output_dir: str = "evaluation/scenarios") -> None:
    """Generate all 50 evaluation scenarios."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    base = datetime(2025, 3, 10, 8, 0, 0, tzinfo=timezone.utc)

    logger.info("=" * 60)
    logger.info("Generating SAIA V4 Evaluation Scenarios")
    logger.info("=" * 60)

    scenarios = []

    # Named scenarios from the spec
    named_builders = [
        _eval_iam_001, _eval_iam_002, _eval_iam_003,
        _eval_iam_004, _eval_iam_005,
        _eval_net_001, _eval_net_002,
        _eval_log_001, _eval_log_002,
        _eval_benign_001, _eval_benign_002,
        _eval_cold_001, _eval_cold_002,
    ]
    for builder in named_builders:
        scenarios.append(builder(base))

    # Extra violation scenarios to reach 30 total
    for sid, dom, clause, sev, desc in EXTRA_VIOLATIONS:
        scenarios.append(_generic_violation(sid, dom, clause, sev, desc, base))

    # Extra benign scenarios to reach 10 total
    for sid, dom, desc in EXTRA_BENIGN:
        scenarios.append(_generic_benign(sid, dom, desc, base))

    # Extra cold-start to reach 5 total
    for sid, dom, desc in EXTRA_COLD:
        scenarios.append(_generic_cold(sid, dom, desc, base))

    # Edge cases (5 total)
    for sid, dom, desc in EXTRA_EDGE:
        scenarios.append(_generic_edge(sid, dom, desc, base))

    # Write files
    for scenario in scenarios:
        sid = scenario["metadata"]["scenario_id"]
        fname = output_path / f"{sid}.json"
        with open(fname, "w") as f:
            json.dump(scenario, f, indent=2, default=str)
        logger.info(f"  {sid} → {fname.name}  ({len(scenario['events'])} events)")

    # Summary
    types = {}
    for s in scenarios:
        t = s["metadata"]["type"]
        types[t] = types.get(t, 0) + 1

    logger.info("\n" + "=" * 60)
    logger.info("Scenario Generation Summary")
    logger.info("=" * 60)
    logger.info(f"Total scenarios: {len(scenarios)}")
    for t, c in sorted(types.items()):
        logger.info(f"  {t}: {c}")
    logger.info(f"Output: {output_path.absolute()}")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Generate evaluation scenarios for SAIA V4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python evaluation/generate_scenarios.py
  python evaluation/generate_scenarios.py --output /data/eval/scenarios
        """,
    )
    parser.add_argument(
        "--output", default="evaluation/scenarios",
        help="Output directory (default: evaluation/scenarios)",
    )
    args = parser.parse_args()
    generate_all_scenarios(output_dir=args.output)


if __name__ == "__main__":
    main()
