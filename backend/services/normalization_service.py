"""
Normalization Service
Pair 2 (Rakan + Faisal) — responsible for this module.

Converts raw log entries from any source into the agreed canonical schema:
  timestamp, source, event_type, principal, action,
  resource, result, source_ip, asset_id, session_id, domain, raw_log

raw_log is stored as JSONB in PostgreSQL — always pass a dict, never a string.
"""

from datetime import datetime
from typing import Optional


# ── Canonical schema builder ──────────────────────────────────────────────────

def build_canonical(
    timestamp:  datetime,
    source:     str,
    event_type: str,
    principal:  Optional[str]  = None,
    action:     Optional[str]  = None,
    resource:   Optional[str]  = None,
    result:     Optional[str]  = None,
    source_ip:  Optional[str]  = None,
    asset_id:   Optional[str]  = None,
    session_id: Optional[str]  = None,
    domain:     Optional[str]  = None,
    raw_log:    Optional[dict] = None,   # JSONB — always a dict, never json.dumps()
) -> dict:
    return {
        "timestamp":      timestamp,
        "source":         source,
        "event_type":     event_type,
        "principal":      principal,
        "action":         action,
        "resource":       resource,
        "result":         result,
        "source_ip":      source_ip,
        "asset_id":       asset_id,
        "session_id":     session_id,
        "domain":         domain,
        "raw_log":        raw_log,        # dict goes directly to JSONB column
        "is_normalized":  True,
        "is_quarantined": False,
    }


# ── Per-source normalizers ────────────────────────────────────────────────────

def normalize_auth_log(entry: dict) -> dict:
    """Normalize authentication / VPN / IdP log entries."""
    try:
        return build_canonical(
            timestamp  = datetime.fromisoformat(entry["timestamp"].replace("Z", "")),
            source     = entry.get("source", "auth"),
            event_type = entry.get("event_type", "authentication"),
            principal  = entry.get("user") or entry.get("username") or entry.get("principal"),
            action     = entry.get("action", "login_attempt"),
            resource   = entry.get("resource") or entry.get("service"),
            result     = entry.get("result") or entry.get("status"),
            source_ip  = entry.get("source_ip") or entry.get("ip_address") or entry.get("ip"),
            asset_id   = entry.get("asset_id"),
            session_id = entry.get("session_id"),
            domain     = entry.get("domain"),
            raw_log    = entry,           # pass dict directly — SQLAlchemy handles JSONB serialization
        )
    except (KeyError, ValueError):
        return _quarantine(entry)


def normalize_firewall_log(entry: dict) -> dict:
    """Normalize firewall / network log entries."""
    try:
        return build_canonical(
            timestamp  = datetime.fromisoformat(entry["timestamp"].replace("Z", "")),
            source     = entry.get("source", "firewall"),
            event_type = entry.get("event_type", "network"),
            principal  = entry.get("src_user") or entry.get("principal"),
            action     = entry.get("action", "connection"),
            resource   = f"{entry.get('dst_ip', '')}:{entry.get('dst_port', '')}",
            result     = entry.get("result") or entry.get("disposition"),
            source_ip  = entry.get("source_ip") or entry.get("src_ip"),
            asset_id   = entry.get("asset_id"),
            session_id = entry.get("session_id"),
            domain     = entry.get("domain"),
            raw_log    = entry,
        )
    except (KeyError, ValueError):
        return _quarantine(entry)


def normalize_app_log(entry: dict) -> dict:
    """Normalize application-level log entries."""
    try:
        return build_canonical(
            timestamp  = datetime.fromisoformat(entry["timestamp"].replace("Z", "")),
            source     = entry.get("source", "app"),
            event_type = entry.get("event_type", "api_request"),
            principal  = entry.get("user") or entry.get("user_id") or entry.get("principal"),
            action     = entry.get("action") or entry.get("method"),
            resource   = entry.get("resource") or entry.get("endpoint"),
            result     = str(entry.get("result") or entry.get("status_code", "")),
            source_ip  = entry.get("source_ip") or entry.get("client_ip"),
            asset_id   = entry.get("asset_id"),
            session_id = entry.get("session_id"),
            domain     = entry.get("domain"),
            raw_log    = entry,
        )
    except (KeyError, ValueError):
        return _quarantine(entry)


def normalize_cloud_log(entry: dict) -> dict:
    """Normalize cloud provider log entries (AWS CloudTrail style)."""
    try:
        ts_key = "eventTime" if "eventTime" in entry else "timestamp"
        return build_canonical(
            timestamp  = datetime.fromisoformat(entry[ts_key].replace("Z", "")),
            source     = entry.get("source", "cloud"),
            event_type = entry.get("event_type", "cloud_event"),
            principal  = (entry.get("userIdentity") or {}).get("arn") or entry.get("principal"),
            action     = entry.get("action") or entry.get("eventName"),
            resource   = (entry.get("requestParameters") or {}).get("bucketName") or entry.get("resource"),
            result     = entry.get("result") or entry.get("errorCode", "success"),
            source_ip  = entry.get("source_ip") or entry.get("sourceIPAddress"),
            asset_id   = entry.get("asset_id"),
            session_id = entry.get("session_id"),
            domain     = entry.get("domain"),
            raw_log    = entry,
        )
    except (KeyError, ValueError):
        return _quarantine(entry)


# ── Dispatcher ────────────────────────────────────────────────────────────────

SOURCE_NORMALIZERS = {
    "auth":     normalize_auth_log,
    "vpn":      normalize_auth_log,     # VPN uses the same auth normalizer
    "firewall": normalize_firewall_log,
    "network":  normalize_firewall_log,
    "app":      normalize_app_log,
    "cloud":    normalize_cloud_log,
}


def normalize(entry: dict, source: str) -> dict:
    """
    Main entry point.
    If the log already follows the canonical schema it passes through directly.
    Otherwise dispatches to the correct source normalizer.
    """
    if _is_already_canonical(entry):
        ts = entry.get("timestamp")
        if isinstance(ts, str):
            entry["timestamp"] = datetime.fromisoformat(ts.replace("Z", ""))
        entry.setdefault("raw_log", entry.copy())
        entry["is_normalized"]  = True
        entry["is_quarantined"] = False
        return entry

    normalizer = SOURCE_NORMALIZERS.get(source.lower())
    if not normalizer:
        return _quarantine(entry, reason=f"Unknown source: {source}")
    return normalizer(entry)


def _is_already_canonical(entry: dict) -> bool:
    """Check if the log already uses the agreed canonical field names."""
    canonical_fields = {"timestamp", "source", "event_type", "principal", "result"}
    return canonical_fields.issubset(entry.keys())


def _quarantine(entry: dict, reason: str = "Normalization failed") -> dict:
    """Mark a log entry as quarantined (SRS FR-06). raw_log stored as dict for JSONB."""
    return {
        "timestamp":      datetime.utcnow(),
        "source":         "unknown",
        "event_type":     "quarantined",
        "is_normalized":  False,
        "is_quarantined": True,
        "raw_log":        {"reason": reason, "original": entry},  # dict — not json.dumps()
    }
