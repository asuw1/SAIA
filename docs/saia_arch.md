# SAIA V4 — Final Architecture & Implementation Specification

---

## 1. Overview

SAIA (Secure Artificial Intelligence Auditor) is a regulation-aware cybersecurity auditing platform for Saudi organizations. It ingests IT system logs, applies rule-based and AI-driven analytics to detect compliance violations against the NCA Essential Cybersecurity Controls (ECC 2:2024), and provides dashboards, alerts, evidence packs, and an AI-powered investigation chatbot.

This document specifies the final architecture (V4) — the version the team will build.

### 1.1 Scope Boundaries

This is a **university capstone prototype**, not an enterprise deployment. The following scoping decisions reflect this:

- **Ingestion:** File upload (JSON/CSV) only. No live syslog or agent connectors.
- **Regulatory focus:** NCA ECC 2:2024 only. SAMA/CST/IA controls are referenced in the data model but not actively mapped.
- **LLM hosting:** Saudi-based cloud server (RunPod KSA region or equivalent). Acceptable for a prototype because log data remains within Saudi jurisdiction. Production would move to on-premises GPU infrastructure.
- **Data store:** PostgreSQL with GIN/B-tree indexes. No Elasticsearch.
- **Scale target:** Thousands of events per upload batch, not millions of events per second.
- **ML training data:** Primarily synthetic. Real data used if available from pilot partners.

### 1.2 Technology Stack

| Component | Technology | Notes |
|-----------|-----------|-------|
| Backend API | FastAPI (Python) | Async, WebSocket support, OpenAPI docs auto-generated |
| Database | PostgreSQL 16 | Single database for all structured data |
| Vector Store | Qdrant (Docker) | Semantic search for RAG over NCA controls and confirmed alerts |
| ML Models | scikit-learn (Isolation Forest) + NumPy/Pandas | CPU-only, no GPU needed locally |
| Embedding Model | `bge-base-en-v1.5` (768-dim) | Runs on CPU locally, <10ms per query |
| LLM | Llama 3.1 70B (Q4 quantized) | Hosted on Saudi-based cloud GPU server via vLLM |
| LLM Client | OpenAI-compatible API (vLLM exposes this) | Standard HTTP calls from FastAPI backend |
| Frontend | HTML / CSS / JavaScript (vanilla) | Existing codebase extended with chatbot panel |
| Auth | JWT + bcrypt password hashing | RBAC enforced server-side on every endpoint |
| Containerization | Docker Compose | All local services (PostgreSQL, Qdrant, FastAPI, embedding model) |

---

## 2. One-Time Setup: Seed Script

Before the system processes any logs, a one-time seed script runs to populate the knowledge base.

**What it does:**

```
1. Read the NCA ECC 2:2024 PDF
2. Parse and chunk it into individual controls (~110 controls)
   Each chunk = one control with:
   - control_id (e.g., "2-2-1")
   - domain (e.g., "Cybersecurity Defense")
   - subdomain (e.g., "Identity and Access Management")
   - title
   - full_text (the control description)
   - keywords (manually curated per control)

3. Generate embeddings for each control using bge-base-en-v1.5

4. Load embeddings + metadata into Qdrant
   Collection: "nca_controls"
   
5. Load the Control-Signal Matrix (JSON file) into PostgreSQL
   Table: control_signal_matrix
   Maps anomaly feature patterns → NCA clause IDs
   Used by both the Rule Engine and Service A
   
6. Load seed rules into PostgreSQL
   Table: rules
   Starter rules for: failed logins, unencrypted transfers,
   dormant accounts, privilege escalation

7. Load lookup tables into PostgreSQL
   Table: action_privilege_levels
   Seed with known actions and their privilege levels (1-5)
   Table: asset_registry
   Seed with known assets, criticality scores, and sensitivity flags
```

**When it runs:** Once, during initial deployment. Re-run only if NCA updates the ECC document.

**The Control-Signal Matrix** is a first-class artifact in the project. It lives as a JSON file in the repository and is loaded into PostgreSQL on seed. Its structure:

```json
[
  {
    "matrix_id": "CSM-IAM-001",
    "domain": "IAM",
    "anomaly_pattern": {
      "trigger_features": ["failed_action_ratio_1h", "events_in_last_hour"],
      "description": "High failure rate with elevated event volume"
    },
    "primary_clause": "2-2-1",
    "secondary_clauses": ["2-2-3"],
    "severity_guidance": "High",
    "explanation_template": "Elevated failure rate ({failed_action_ratio_1h}) with high event volume ({events_in_last_hour}) suggests brute force or credential stuffing, relevant to identity and access management controls.",
    "false_positive_notes": "May trigger during password reset campaigns or system migrations."
  },
  {
    "matrix_id": "CSM-IAM-002",
    "domain": "IAM",
    "anomaly_pattern": {
      "trigger_features": ["hour_of_day", "source_country_is_usual"],
      "description": "Login outside business hours from unusual location"
    },
    "primary_clause": "2-2-1",
    "secondary_clauses": ["2-7-3"],
    "severity_guidance": "High",
    "explanation_template": "Login at {hour_of_day}:00 from location flagged as unusual. Deviates from entity baseline of business-hour access from within Saudi Arabia.",
    "false_positive_notes": "Check for VPN usage or authorized travel."
  },
  {
    "matrix_id": "CSM-IAM-003",
    "domain": "IAM",
    "anomaly_pattern": {
      "trigger_features": ["is_new_resource_for_entity", "privilege_level_of_action", "deviation_from_daily_baseline"],
      "description": "Access to unfamiliar high-privilege resource with behavioral deviation"
    },
    "primary_clause": "2-2-4",
    "secondary_clauses": ["2-2-1", "2-3-1"],
    "severity_guidance": "Critical",
    "explanation_template": "Entity accessed a previously-unseen resource requiring elevated privilege (level {privilege_level_of_action}), with daily activity deviating {deviation_from_daily_baseline} sigma from baseline.",
    "false_positive_notes": "Check for role change, new project assignment, or approved access request."
  },
  {
    "matrix_id": "CSM-NET-001",
    "domain": "Network",
    "anomaly_pattern": {
      "trigger_features": ["entity_event_volume_zscore", "unique_resources_accessed_1h"],
      "description": "Unusual network traffic volume and resource access diversity"
    },
    "primary_clause": "2-7-3",
    "secondary_clauses": ["2-7-1"],
    "severity_guidance": "High",
    "explanation_template": "Network traffic volume at {entity_event_volume_zscore} sigma above baseline with {unique_resources_accessed_1h} unique resources accessed in one hour, suggesting potential lateral movement or data exfiltration.",
    "false_positive_notes": "Check for scheduled backups, migrations, or authorized scans."
  },
  {
    "matrix_id": "CSM-LOG-001",
    "domain": "Application",
    "anomaly_pattern": {
      "trigger_features": ["entity_event_volume_zscore"],
      "description": "Sudden drop in log volume from a source"
    },
    "primary_clause": "2-13-1",
    "secondary_clauses": ["2-9-1"],
    "severity_guidance": "Medium",
    "explanation_template": "Log volume from source dropped to {entity_event_volume_zscore} sigma below baseline. This may indicate log tampering, source failure, or retention policy violation.",
    "false_positive_notes": "Check for planned maintenance or system shutdown."
  }
]
```

The matrix is extended as new anomaly patterns are discovered. For the capstone prototype, 15-25 entries covering IAM, Network, Application, and Cloud domains is sufficient.

---

## 3. Authentication & Authorization Layer

Every API request passes through this layer before reaching any handler. No exceptions.

### 3.1 Flow

```
Request arrives at FastAPI endpoint
    │
    ▼
JWT Middleware extracts token from Authorization header
    │
    ├── Token missing or expired → 401 Unauthorized, stop
    │
    ▼
Decode JWT, extract user_id and role
    │
    ▼
RBAC Middleware checks: does this role have permission for this endpoint + action?
    │
    ├── No → 403 Forbidden, stop
    │
    ▼
Inject user context into request state:
  request.state.user_id = user_id
  request.state.role = role
  request.state.data_scope = [domains this user can access]
    │
    ▼
Log action to AuditLog table (user_id, action, resource, timestamp, ip)
    │
    ▼
Proceed to handler
```

### 3.2 Roles and Permissions

Three roles: **Admin**, **Compliance Officer**, **Analyst**.

| Action | Admin | Compliance Officer | Analyst |
|--------|:-----:|:------------------:|:-------:|
| Manage users | Yes | No | No |
| Configure thresholds | Yes | No | No |
| View all alerts | Yes | Yes | Own only |
| Assign alerts | Yes | Yes | No |
| Mark TP / FP | Yes | Yes | No |
| Create rules | Yes | Yes | No |
| Publish rules | Yes | No | No |
| Generate reports | Yes | Yes | No |
| Approve narratives | Yes | Yes | No |
| AI Chatbot | Yes | Yes | Yes |
| View audit log | Yes | No | No |
| View dashboard | Yes | Yes | Yes |
| Upload logs | Yes | Yes | No |

### 3.3 Data Scoping

Each user has a `data_scope` field — an array of domains they can access (e.g., `["IAM", "Network"]` or `["*"]` for all). Every database query that returns log events, alerts, or reports includes a `WHERE domain IN (user.data_scope)` filter. The chatbot includes the user's role and data_scope in every LLM prompt so the model does not reference data outside the user's authorization.

**Analyst alert visibility:** Analysts can only view alerts assigned to them (`WHERE assigned_to = user.id`). Admin and Compliance Officer can view all alerts within their data scope.

### 3.4 Database Tables

```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'compliance_officer', 'analyst')),
    data_scope TEXT[] NOT NULL DEFAULT '{\"*\"}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit Log (immutable — enforced at database level via Row Level Security)
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(255),
    details JSONB,
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_audit_log_user ON audit_log(user_id);
CREATE INDEX idx_audit_log_time ON audit_log(created_at);

-- NFR-08: Tamper-evident audit log — INSERT only, no UPDATE/DELETE
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY audit_insert_only ON audit_log FOR INSERT WITH CHECK (true);
-- No UPDATE or DELETE policies = those operations are blocked by RLS

-- Lookup: Action privilege levels (used by feature 10: privilege_level_of_action)
-- Unknown actions default to privilege level 1
CREATE TABLE action_privilege_levels (
    action VARCHAR(255) PRIMARY KEY,
    privilege_level INTEGER NOT NULL DEFAULT 1 CHECK (privilege_level BETWEEN 1 AND 5)
);
-- Seeded with known actions, e.g.:
-- ('login', 1), ('read', 1), ('write', 2), ('delete', 3),
-- ('admin_login', 4), ('role_change', 5), ('config_change', 5)

-- Lookup: Asset registry (used by features 17 and 20: asset_criticality, is_sensitive)
-- Unknown assets default to criticality 3, not sensitive
CREATE TABLE asset_registry (
    asset_id VARCHAR(255) PRIMARY KEY,
    asset_name VARCHAR(500),
    criticality_score INTEGER NOT NULL DEFAULT 3 CHECK (criticality_score BETWEEN 1 AND 5),
    is_sensitive BOOLEAN DEFAULT FALSE
);
-- Seeded with known assets, e.g.:
-- ('HR_DATABASE', 'HR Database', 5, true),
-- ('EMAIL_SERVER', 'Email Server', 4, false),
-- ('PUBLIC_WEBSITE', 'Public Website', 2, false)
```

---

## 4. Layer 1: Ingestion & Normalization

### 4.1 Upload Endpoint

```
POST /api/v1/logs/upload
  Content-Type: multipart/form-data
  Body: file (JSON or CSV), source_name (string), domain (string)
  Auth: Admin, Compliance Officer
  
  Response: { upload_id, events_parsed, events_accepted, events_quarantined }
```

The endpoint accepts a single file (JSON array of events or CSV with headers). Multiple files can be uploaded sequentially. The response returns immediately after parsing and quality gating — it does NOT wait for ML detection or LLM analysis (those happen asynchronously).

**REST Ingest Endpoint (for programmatic use and demo log generator):**

```
POST /api/v1/logs/ingest
  Content-Type: application/json
  Body: { "source_name": "string", "domain": "string", "events": [ {...}, {...} ] }
  Auth: Admin, Compliance Officer
  Rate limit: 60 requests/minute per user (configurable via INGEST_RATE_LIMIT in .env)
  
  Response: { upload_id, events_parsed, events_accepted, events_quarantined }
  Error 429: { "error": "rate_limit_exceeded", "retry_after_seconds": 10 }
```

Rate limiting is implemented via a simple in-memory counter in FastAPI middleware using `slowapi` (a thin wrapper around the `limits` library, compatible with FastAPI):

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/ingest")
@limiter.limit("60/minute")
async def ingest_events(request: Request, ...):
    ...
```

The demo log generator sends one batch every 5 seconds (12 requests/minute), well within the limit. The rate limit protects against accidental loops or misconfigured clients hammering the endpoint during the demo.

Accepts a JSON body containing a single event or an array of events. Same normalization and quality gate pipeline as the file upload endpoint. Used by the demo log generator script (`scripts/log_generator.py`) which sends batches of synthetic events every 5 seconds.

### 4.2 Normalization

Raw log events are mapped to the canonical schema. The backend includes a parser per supported format (currently: generic JSON, generic CSV). Each parser maps source-specific field names to canonical fields.

**Canonical Schema:**

```sql
CREATE TABLE log_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    upload_id UUID NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    source VARCHAR(100) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    principal VARCHAR(255),
    action VARCHAR(255) NOT NULL,
    resource VARCHAR(500),
    result VARCHAR(50),
    source_ip INET,
    asset_id VARCHAR(255),
    domain VARCHAR(50) NOT NULL,
    raw_log JSONB NOT NULL,
    
    -- Quality and ML metadata
    quality_score FLOAT NOT NULL,
    is_quarantined BOOLEAN DEFAULT FALSE,
    anomaly_score FLOAT,
    is_flagged BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Performance indexes (B-Tree)
CREATE INDEX idx_log_events_domain_time ON log_events(domain, timestamp);
CREATE INDEX idx_log_events_principal_result_time ON log_events(principal, result, timestamp);
CREATE INDEX idx_log_events_event_type_time ON log_events(event_type, timestamp);
CREATE INDEX idx_log_events_source_ip ON log_events(source_ip);
CREATE INDEX idx_log_events_flagged ON log_events(is_flagged) WHERE is_flagged = TRUE;
CREATE INDEX idx_log_events_quarantined ON log_events(is_quarantined) WHERE is_quarantined = TRUE;

-- Full-text search index for chatbot queries
ALTER TABLE log_events ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english', 
            coalesce(event_type, '') || ' ' || 
            coalesce(action, '') || ' ' || 
            coalesce(resource, '') || ' ' ||
            coalesce(result, '')
        )
    ) STORED;
CREATE INDEX idx_log_events_search ON log_events USING GIN(search_vector);

-- GIN index on raw_log for flexible JSONB queries
CREATE INDEX idx_log_events_raw ON log_events USING GIN(raw_log);
```

### 4.3 Feature Quality Gate

Before an event enters the ML pipeline, it is checked for minimum feature completeness.

**Logic:**

```python
REQUIRED_FIELDS = ['timestamp', 'action', 'domain']
IMPORTANT_FIELDS = ['principal', 'resource', 'result', 'source_ip', 'event_type']

def compute_quality_score(event: dict) -> float:
    required_present = sum(1 for f in REQUIRED_FIELDS if event.get(f) is not None)
    important_present = sum(1 for f in IMPORTANT_FIELDS if event.get(f) is not None)
    
    if required_present < len(REQUIRED_FIELDS):
        return 0.0  # Missing critical fields
    
    score = 0.4 + (important_present / len(IMPORTANT_FIELDS)) * 0.6
    return round(score, 2)

# Quality gate threshold
QUALITY_THRESHOLD = 0.7

# Events with score < 0.7:
#   - Saved to log_events with is_quarantined = True
#   - Skipped by ML pipeline
#   - Still visible in dashboard data quality metrics
#   - Still searchable by chatbot (with quality warning)

# Events with score >= 0.7:
#   - Saved to log_events with is_quarantined = False
#   - Proceed to Layer 2A (Rule Engine) and Layer 2B (ML Detection)
```

**Imputation for partial events (score >= 0.7 but some fields missing):**

- Missing `principal` → `"UNKNOWN"`
- Missing `source_ip` → `NULL` (contextual features that depend on it become 0.0)
- Missing `result` → `"UNKNOWN"` (failed_action_ratio features become unreliable — the model has seen this in training via synthetic data with similar patterns)

### 4.4 Async Processing Handoff

After normalization and quality gating, the upload endpoint returns a response to the user. The remaining pipeline runs asynchronously:

```
Upload endpoint returns { upload_id, stats }
    │
    ▼
Background task is queued (FastAPI BackgroundTasks or Celery)
    │
    ├── For each non-quarantined event:
    │       1. Run Rule Engine (Layer 2A)
    │       2. Run ML Detection (Layer 2B)
    │       3. If rule fires or ML flags → Alert Aggregation (Layer 3)
    │
    └── When batch complete:
            Update upload status in DB
            Push new alerts to frontend via WebSocket
```

---

## 5. Layer 2A: Rule Engine

The rule engine evaluates deterministic rules against each normalized log event.

### 5.1 Rule Storage

```sql
CREATE TABLE rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    domain VARCHAR(50) NOT NULL,
    clause_reference VARCHAR(50) NOT NULL,  -- e.g., "2-2-1"
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    conditions JSONB NOT NULL,  -- The rule logic
    is_active BOOLEAN DEFAULT FALSE,
    version INTEGER DEFAULT 1,
    author_id UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_rules_active ON rules(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_rules_domain ON rules(domain);
```

### 5.2 Rule Conditions Format

Rules are expressed as JSON conditions evaluated against canonical event fields:

```json
{
  "rule_name": "Brute Force Login Detection",
  "conditions": {
    "field_checks": [
      { "field": "event_type", "operator": "eq", "value": "authentication" },
      { "field": "result", "operator": "eq", "value": "failure" }
    ],
    "aggregation": {
      "group_by": ["principal", "source_ip"],
      "window_minutes": 10,
      "count_threshold": 5
    }
  },
  "clause_reference": "2-2-1",
  "severity": "high"
}
```

The rule engine loads all active rules on startup and caches them in memory. When a new event arrives, each rule is evaluated:

1. **Field checks:** Does the event match the rule's field conditions?
2. **Aggregation checks (if present):** Query PostgreSQL for recent events matching the group_by fields within the time window. If count exceeds threshold, the rule fires.
3. **Rule fires → create a rule_alert** with the rule's clause_reference and severity.

### 5.3 Rule Lifecycle

Rules follow the lifecycle: **Draft → Active → Archived**

- Only Admins can create/edit rules (per RBAC)
- Rules can be tested against historical log data before activation (dry-run)
- Each edit increments the version number
- Archived rules are retained for audit trails but don't execute

---

## 6. Layer 2B: ML Anomaly Detection

### 6.1 Feature Extraction

For each non-quarantined event, extract 25 features organized into four groups.

**A. Temporal Features (6)**

| # | Feature Name | Type | Description | How Computed |
|---|-------------|------|-------------|-------------|
| 1 | `hour_of_day` | int (0-23) | Hour the event occurred | Extract from event timestamp |
| 2 | `day_of_week` | int (0-6) | Day of week (0=Monday) | Extract from event timestamp |
| 3 | `is_business_hours` | binary (0/1) | Whether event is within 7AM-6PM Sun-Thu (Saudi business days) | Derive from hour + day |
| 4 | `is_weekend` | binary (0/1) | Whether event is on Friday or Saturday (Saudi weekend) | Derive from day_of_week |
| 5 | `minutes_since_last_event` | float | Time gap from this entity's previous event | Query last event for same principal |
| 6 | `events_in_last_hour` | int | Count of events by this entity in the last 60 minutes | Aggregate query on principal + timestamp |

**B. Behavioral Features (8)**

| # | Feature Name | Type | Description |
|---|-------------|------|-------------|
| 7 | `unique_resources_accessed_1h` | int | Number of distinct resources this entity accessed in last hour |
| 8 | `unique_actions_performed_1h` | int | Number of distinct action types in last hour |
| 9 | `failed_action_ratio_1h` | float (0-1) | Fraction of events with result="failure" in last hour |
| 10 | `privilege_level_of_action` | int (1-5) | Privilege level required for this action (from `action_privilege_levels` table, default: 1 for unknown actions) |
| 11 | `is_new_resource_for_entity` | binary (0/1) | Has this entity ever accessed this resource before? |
| 12 | `is_new_action_for_entity` | binary (0/1) | Has this entity ever performed this action type before? |
| 13 | `deviation_from_hourly_baseline` | float | Events this hour vs. entity's median for this hour-of-day (z-score using MAD). Returns 0.0 for new entities with no baseline. |
| 14 | `deviation_from_daily_baseline` | float | Events today vs. entity's median for this day-of-week (z-score using MAD). Returns 0.0 for new entities with no baseline. |

**C. Contextual Features (6)**

| # | Feature Name | Type | Description |
|---|-------------|------|-------------|
| 15 | `source_ip_is_known` | binary (0/1) | Has this entity used this IP before? |
| 16 | `source_country_is_usual` | binary (0/1) | Is the IP geolocated in the entity's usual country? (simple GeoIP lookup, default: Saudi = usual) |
| 17 | `asset_criticality_score` | int (1-5) | Criticality of the target resource/asset (from `asset_registry` table, default: 3 for unknown assets) |
| 18 | `principal_risk_score` | float (0-1) | Rolling risk score for this entity based on recent anomaly flags. Decays exponentially: `score = prev_score * e^(-0.1 * days_since_last_flag)`. Increases by 0.1 per flagged event, capped at 1.0. New entities start at 0.0. Read from `entity_baselines` (updated after each completed batch, never mid-batch). |
| 19 | `concurrent_sessions` | int | Number of distinct source_IPs this entity has active in current 30-minute window |
| 20 | `is_sensitive_resource` | binary (0/1) | Is the target resource tagged as sensitive? (from `asset_registry` table, default: FALSE for unknown assets) |

**D. Aggregate Features (5)**

| # | Feature Name | Type | Description |
|---|-------------|------|-------------|
| 21 | `entity_event_volume_zscore` | float | This entity's event count for current hour compared to their historical median (z-score using MAD) |
| 22 | `entity_error_rate_zscore` | float | This entity's error rate for current hour compared to historical median |
| 23 | `entity_resource_diversity_zscore` | float | This entity's unique resource count for current hour compared to historical median |
| 24 | `entity_privilege_escalation_rate` | float (0-1) | Fraction of this entity's recent events that involved privilege levels higher than their modal level |
| 25 | `cross_entity_correlation_score` | float (0-1) | Are multiple entities showing anomalous behavior simultaneously on the same resource? (normalized count) |

### 6.2 Statistical Baselines

Per-entity profiles are computed and stored in PostgreSQL, updated after each log batch upload.

```sql
CREATE TABLE entity_baselines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    principal VARCHAR(255) NOT NULL,
    domain VARCHAR(50) NOT NULL,
    
    -- Hourly medians (24 values, stored as JSON array)
    hourly_event_count_median JSONB,  -- [median_for_hour_0, ..., median_for_hour_23]
    hourly_event_count_mad JSONB,     -- MAD for each hour
    
    -- Daily medians (7 values, stored as JSON array)
    daily_event_count_median JSONB,   -- [median_for_monday, ..., median_for_sunday]
    daily_event_count_mad JSONB,
    
    -- Global behavioral medians
    median_error_rate FLOAT,
    mad_error_rate FLOAT,
    median_resource_diversity FLOAT,
    mad_resource_diversity FLOAT,
    median_event_volume FLOAT,
    mad_event_volume FLOAT,
    
    -- Known patterns
    known_ips TEXT[],
    known_resources TEXT[],
    known_actions TEXT[],
    modal_privilege_level INTEGER,
    usual_country VARCHAR(10) DEFAULT 'SA',
    
    -- Risk score (feature 18)
    risk_score FLOAT NOT NULL DEFAULT 0.0,        -- Current decayed risk score
    last_flag_time TIMESTAMPTZ,                    -- When this entity was last flagged
    
    -- Metadata
    sample_count INTEGER DEFAULT 0,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(principal, domain)
);
CREATE INDEX idx_baselines_principal ON entity_baselines(principal);
```

**Why Median/MAD instead of Mean/Std:** Security event distributions are heavy-tailed. A single brute-force incident produces thousands of events, destroying mean-based statistics. Median Absolute Deviation is robust to these outliers and gives stable baselines.

**Baseline update logic:**
```
After each log upload batch:
1. For each entity that appeared in the batch:
   a. Query all their events from the last 30 days
   b. Recompute hourly/daily medians and MADs
   c. Update known_ips, known_resources, known_actions sets
   d. Update risk_score: new_score = old_score * e^(-0.1 * days_since_last_flag)
      If entity was flagged in this batch: new_score = min(new_score + 0.1, 1.0)
   e. Upsert into entity_baselines table
```

**Cold start handling for new entities:**

Entities with no existing baseline (first time seen) require special handling because features 5, 11, 12, 13, 14, 18, 21-24 all return zero or degenerate values. Without mitigation, new entities either always get flagged (if zeros look anomalous to the model) or never get flagged.

Two-part mitigation:

1. **Training data inclusion:** The synthetic training data for Isolation Forest must include "new entity" feature vectors where all baseline-dependent features are zero. This teaches the model that zero-baseline profiles are normal, not anomalous.

2. **Baseline maturity suppression:** If an entity has `sample_count < 50` in `entity_baselines`, suppress ML flagging for that entity and rely only on rule-based detection. This avoids false positives during the entity's warm-up period while still catching known violation patterns via rules.

```python
BASELINE_MATURITY_THRESHOLD = 50

def should_apply_ml(principal: str, domain: str) -> bool:
    baseline = db.fetch_one(
        "SELECT sample_count FROM entity_baselines WHERE principal=$1 AND domain=$2",
        principal, domain
    )
    if baseline is None or baseline['sample_count'] < BASELINE_MATURITY_THRESHOLD:
        return False  # Rules only — skip ML scoring
    return True
```

### 6.3 Isolation Forest Models

Separate Isolation Forest model per domain, trained on feature vectors from normal (non-anomalous) events.

```python
from sklearn.ensemble import IsolationForest
import joblib

# One model per domain
MODELS = {
    'IAM': IsolationForest(
        n_estimators=200,
        contamination=0.02,  # Expect ~2% anomalies in IAM logs
        max_features=0.8,
        random_state=42
    ),
    'Network': IsolationForest(
        n_estimators=200,
        contamination=0.03,  # Network logs tend to have more noise
        max_features=0.8,
        random_state=42
    ),
    'Application': IsolationForest(
        n_estimators=200,
        contamination=0.02,
        max_features=0.8,
        random_state=42
    ),
    'Cloud': IsolationForest(
        n_estimators=200,
        contamination=0.02,
        max_features=0.8,
        random_state=42
    )
}

# Training: use synthetic normal data + any available real normal data
# model.fit(X_train)  where X_train is a matrix of 25 features from normal events

# Inference: returns anomaly score in range [-1, 0]
# score = model.decision_function(X_event.reshape(1, -1))[0]
# More negative = more anomalous

# Normalize to [0, 1] for score fusion:
# normalized_score = 1 - (score - min_score) / (max_score - min_score)
```

**Model persistence:** Models are saved as `.joblib` files and loaded on backend startup. Retraining is manual (triggered by admin when sufficient labeled feedback is available).

### 6.4 Score Fusion

```python
def compute_combined_score(if_score_normalized: float, max_baseline_deviation: float,
                           domain: str) -> float:
    """
    Combine Isolation Forest score with statistical baseline deviation.
    
    if_score_normalized: Isolation Forest anomaly score, normalized to [0, 1]
    max_baseline_deviation: Maximum z-score deviation across all baseline features
    domain: Event domain (used to look up domain-specific weights)
    """
    # Domain-specific weights (tuned via calibration)
    weights = {
        'IAM':         {'w_if': 0.6, 'w_baseline': 0.4},
        'Network':     {'w_if': 0.7, 'w_baseline': 0.3},
        'Application': {'w_if': 0.5, 'w_baseline': 0.5},
        'Cloud':       {'w_if': 0.6, 'w_baseline': 0.4},
    }
    
    w = weights.get(domain, {'w_if': 0.6, 'w_baseline': 0.4})
    
    # Normalize baseline deviation to [0, 1] using sigmoid
    baseline_norm = 1 / (1 + math.exp(-0.5 * (max_baseline_deviation - 3)))
    
    combined = w['w_if'] * if_score_normalized + w['w_baseline'] * baseline_norm
    return round(combined, 4)

# Thresholds (configurable per domain)
THRESHOLDS = {
    'IAM': 0.65,
    'Network': 0.60,
    'Application': 0.65,
    'Cloud': 0.65
}
```

**If combined_score > threshold:** The event is flagged. Its `anomaly_score` and `is_flagged` fields are updated in the `log_events` table, and it proceeds to Layer 3 (Alert Aggregation).

**Attach to flagged event:**
- `anomaly_score` (the combined score)
- `top_contributing_features` (top 3 features by absolute deviation from training mean, from Isolation Forest's feature importance)
- `baseline_deviations` (per-feature z-scores from statistical baselines)

---

## 7. Layer 3: Alert Aggregation

Receives flags from both the Rule Engine and ML Detection, creates or updates alerts.

### 7.1 Alert Table

```sql
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_number VARCHAR(20) UNIQUE NOT NULL,  -- e.g., "ALT-2025-0001" (auto-generated)
    
    -- Classification
    domain VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    status VARCHAR(30) NOT NULL DEFAULT 'open' 
        CHECK (status IN ('open', 'investigating', 'resolved', 'false_positive')),
    source VARCHAR(20) NOT NULL CHECK (source IN ('rule', 'ai', 'both')),
    
    -- Detection details
    entity_principal VARCHAR(255),
    clause_reference VARCHAR(50),     -- Available at creation: from rule (immediate) or CSM lookup (immediate).
                                      -- Updated by Service A if LLM suggests a different primary clause.
    anomaly_score FLOAT,
    top_features JSONB,           -- [{"name": "...", "value": ..., "deviation": ...}, ...]
    baseline_deviations JSONB,    -- {"feature_name": z_score, ...}
    triggered_rule_ids UUID[],    -- Array of rule IDs that fired (if source = rule or both)
    event_ids UUID[] NOT NULL,    -- Array of log_event IDs that compose this alert
    
    -- LLM enrichment (populated by Service A, initially NULL)
    llm_assessment JSONB,
    /*  Structure when populated:
        {
            "violation_detected": true,
            "confidence": 0.91,
            "primary_clause": "2-2-1",
            "secondary_clauses": ["2-7-3"],
            "severity_assessment": "critical",
            "reasoning": "...",
            "recommended_action": "...",
            "false_positive_likelihood": 0.12
        }
    */
    
    -- Case management
    assigned_to UUID REFERENCES users(id),
    case_id UUID REFERENCES cases(id),
    
    -- Feedback
    analyst_verdict VARCHAR(20) CHECK (analyst_verdict IN ('true_positive', 'false_positive')),
    analyst_comment TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX idx_alerts_severity_status_created ON alerts(severity, status, created_at);
CREATE INDEX idx_alerts_assigned_status ON alerts(assigned_to, status);
CREATE INDEX idx_alerts_domain ON alerts(domain);
CREATE INDEX idx_alerts_case ON alerts(case_id);
CREATE INDEX idx_alerts_number ON alerts(alert_number);
```

### 7.2 Cases Table

```sql
CREATE TABLE cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_number VARCHAR(20) UNIQUE NOT NULL,  -- e.g., "CASE-2025-0001"
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'in_progress', 'resolved', 'verified')),
    severity VARCHAR(20) NOT NULL,
    assigned_to UUID REFERENCES users(id),
    
    -- Evidence narrative (populated by Service C, initially NULL)
    narrative_draft TEXT,                      -- Markdown output from Service C
    narrative_approved BOOLEAN DEFAULT FALSE,  -- Flipped to TRUE by Compliance Officer/Admin after review
    narrative_approved_by UUID REFERENCES users(id),
    narrative_approved_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);
```

### 7.3 Deduplication and Aggregation Logic

```python
async def aggregate_alert(event_id: UUID, domain: str, entity: str, 
                          clause: str, severity: str, source: str,
                          anomaly_score: float = None, 
                          top_features: dict = None,
                          rule_id: UUID = None):
    """
    Check for existing open alert matching this event's fingerprint.
    If found, append. If not, create new.
    
    The `clause` parameter is available at creation time:
    - Rule-sourced alerts: clause comes from the rule's clause_reference (immediate)
    - ML-sourced alerts: clause comes from CSM lookup on the top features (immediate)
    - If no CSM match for ML alerts: clause = None, dedup uses (entity, domain) only
    """
    DEDUP_WINDOW_HOURS = 1
    
    # Check for existing open alert with same entity + domain + clause
    # Uses clause_reference (available at creation time from rule or CSM)
    # NOT llm_assessment->>'primary_clause' (which is NULL until Service A runs)
    # NULL-safe: if clause is None (ML-only, no CSM match), matches other NULL-clause alerts
    existing = await db.fetch_one("""
        SELECT id, event_ids, triggered_rule_ids, source
        FROM alerts
        WHERE entity_principal = $1
          AND domain = $2
          AND (clause_reference = $3 OR (clause_reference IS NULL AND $3 IS NULL))
          AND status IN ('open', 'investigating')
          AND created_at > NOW() - INTERVAL '{} hours'
        ORDER BY created_at DESC
        LIMIT 1
    """.format(DEDUP_WINDOW_HOURS), entity, domain, clause)
    
    if existing:
        # Append event to existing alert
        new_event_ids = existing['event_ids'] + [event_id]
        new_source = 'both' if existing['source'] != source else existing['source']
        new_rule_ids = existing['triggered_rule_ids'] or []
        if rule_id:
            new_rule_ids.append(rule_id)
        
        await db.execute("""
            UPDATE alerts 
            SET event_ids = $1, source = $2, triggered_rule_ids = $3, updated_at = NOW()
            WHERE id = $4
        """, new_event_ids, new_source, new_rule_ids, existing['id'])
        
        return existing['id']
    else:
        # Create new alert
        alert_number = await generate_alert_number()  # "ALT-2025-XXXX"
        
        severity_from_score = compute_severity(anomaly_score) if source != 'rule' else severity
        
        alert_id = await db.fetch_val("""
            INSERT INTO alerts (alert_number, domain, severity, status, source,
                               entity_principal, clause_reference, anomaly_score, 
                               top_features, triggered_rule_ids, event_ids)
            VALUES ($1, $2, $3, 'open', $4, $5, $6, $7, $8, $9, $10)
            RETURNING id
        """, alert_number, domain, severity_from_score, source,
             entity, clause, anomaly_score, top_features,
             [rule_id] if rule_id else None, [event_id])
        
        # Queue for LLM analysis
        await llm_queue.enqueue(alert_id, priority=severity_to_priority(severity_from_score))
        
        # Push to frontend via WebSocket
        await ws_manager.broadcast_new_alert(alert_id, alert_number, severity_from_score)
        
        return alert_id

def compute_severity(anomaly_score: float) -> str:
    if anomaly_score is None:
        return 'medium'
    if anomaly_score > 0.9:
        return 'critical'
    elif anomaly_score > 0.75:
        return 'high'
    elif anomaly_score > 0.6:
        return 'medium'
    return 'low'
```

### 7.4 LLM Queue

Alerts are queued for LLM enrichment in a simple PostgreSQL-backed queue:

```sql
CREATE TABLE llm_queue (
    id BIGSERIAL PRIMARY KEY,
    alert_id UUID REFERENCES alerts(id) NOT NULL,
    priority INTEGER NOT NULL,  -- 1=critical, 2=high, 3=medium, 4=low
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'done', 'failed')),
    attempts INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);
CREATE INDEX idx_llm_queue_pending ON llm_queue(priority, created_at) WHERE status = 'pending';
```

A background worker runs every 2 minutes, picks the top 5 pending items by priority, and sends them to Service A for enrichment.

---

## 8. Layer 4: LLM Services

A single LLM instance (Llama 3.1 70B Q4, served via vLLM on Saudi-based cloud GPU) handles three services through different prompt templates.

### 8.1 LLM Infrastructure

```
Saudi-Based Cloud Server (e.g., RunPod KSA / local GPU cluster):
  └── vLLM server
      ├── Model: Llama 3.1 70B (Q4_K_M quantization, ~40GB VRAM)
      ├── Endpoint: http://<server-ip>:8000/v1/chat/completions
      ├── OpenAI-compatible API
      └── Continuous batching enabled for throughput

Local Backend (FastAPI):
  └── HTTP client calls to vLLM server
      ├── Service A: background worker, batched
      ├── Service B: on-demand, streaming response
      └── Service C: on-demand, non-streaming
```

All LLM calls use the same HTTP client pattern:

```python
import httpx

LLM_BASE_URL = "http://<cloud-server>:8000/v1"

async def call_llm(system_prompt: str, user_prompt: str, 
                   max_tokens: int = 2000, temperature: float = 0.1,
                   stream: bool = False) -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{LLM_BASE_URL}/chat/completions",
            json={
                "model": "llama-3.1-70b",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": stream
            }
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
```

### 8.2 Service A: Anomaly Enrichment & Regulatory Mapping

**Trigger:** Background worker processes LLM queue every 2 minutes.

**Flow for each queued alert:**

```
1. Load alert from PostgreSQL (anomaly_score, top_features, baseline_deviations, event_ids)
2. Load referenced log events from PostgreSQL (canonical fields, not raw_log)
3. Check Control-Signal Matrix for matching feature patterns:
   - Query CSM table for entries where trigger_features overlap with
     this alert's top contributing features and domain matches
   - If match found: use CSM's primary_clause and secondary_clauses
     to construct a targeted Qdrant query
   - If no match: fall back to semantic search (step 3b)
   
   3a. CSM match → Targeted Qdrant retrieval:
       Query Qdrant "nca_controls" for the specific clause IDs from CSM
       (exact match on control_id metadata, not semantic search)
       This is precise: we know which control to retrieve
   
   3b. No CSM match → Semantic Qdrant retrieval:
       Embed query: "{domain} {top_feature_names} violation"
       Retrieve top 3 most relevant NCA controls by similarity
       This is a fallback for novel anomaly patterns not yet in the CSM

4. Query Qdrant "confirmed_alerts" collection:
   - Embed query: "{domain} {top_feature_names} {anomaly_score_range}"
   - Retrieve top 2 most similar analyst-confirmed alerts (if any exist)
5. Assemble prompt (see below)
6. Call LLM
7. Parse JSON response
8. Validate response (see validation rules below)
9. If valid: update alert.llm_assessment in PostgreSQL
10. If invalid: retry once with simplified prompt. If still invalid: mark queue item as failed.
    Alert stays in dashboard without LLM reasoning (still has ML score and rule triggers).
```

**System Prompt (Service A):**

```
You are a cybersecurity compliance analyst specializing in Saudi Arabia's NCA Essential Cybersecurity Controls (ECC 2:2024). You analyze security anomalies detected by an automated monitoring system and assess whether they constitute violations of specific ECC controls.

Rules:
- Analyze the anomaly using ONLY the NCA controls provided in the context. Do not reference controls not provided.
- Cite specific control IDs using the format "2-X-Y" (e.g., "2-2-1", "2-7-3").
- Provide reasoning that a compliance auditor can directly use in a report.
- Assess false positive likelihood based on common benign explanations.
- Respond ONLY in valid JSON. No markdown, no preamble, no explanation outside the JSON structure.

Current user role: {user_role}
Data scope: {user_data_scope}
```

**User Prompt (Service A):**

```
## Relevant NCA ECC Controls
{rag_control_1_id}: {rag_control_1_title}
{rag_control_1_text}

{rag_control_2_id}: {rag_control_2_title}
{rag_control_2_text}

{rag_control_3_id}: {rag_control_3_title}
{rag_control_3_text}

## Similar Past Alerts (Analyst-Confirmed)
{# If confirmed alerts exist in Qdrant: }
Alert {similar_1_id}: Domain={similar_1_domain}, Score={similar_1_score}
Features: {similar_1_features}
Analyst verdict: {similar_1_verdict} (true_positive / false_positive)
Mapped to: {similar_1_clause}
{# If no confirmed alerts yet: }
No confirmed historical alerts available yet.

## Anomaly to Analyze
Alert: {alert_number}
Domain: {domain}
Entity: {entity_principal}
Detection Time: {timestamp}
Anomaly Score: {anomaly_score} (threshold: {threshold})

Top Contributing Features:
- {feature_1_name}: {feature_1_value} ({feature_1_deviation} sigma from baseline)
- {feature_2_name}: {feature_2_value} ({feature_2_deviation} sigma from baseline)
- {feature_3_name}: {feature_3_value} ({feature_3_deviation} sigma from baseline)

Event Summary:
- Event Type: {event_type}
- Action: {action}
- Resource: {resource}
- Result: {result}
- Source IP: {source_ip}

Related Rule Triggers: {rule_names_and_clauses or "None"}

## Required Response Format
{
  "violation_detected": boolean,
  "confidence": float between 0.0 and 1.0,
  "primary_clause": "2-X-Y",
  "secondary_clauses": ["2-X-Y", ...] or [],
  "severity_assessment": "critical" | "high" | "medium" | "low",
  "reasoning": "2-4 sentences explaining the assessment",
  "recommended_action": "specific next step for the analyst",
  "false_positive_likelihood": float between 0.0 and 1.0
}
```

**Response Validation:**

```python
VALID_CLAUSE_IDS = {"2-1-1", "2-1-2", ..., "2-14-3"}  # All 110 ECC control IDs

def validate_llm_response(raw: str) -> dict | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try stripping markdown fences
        cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return None
    
    # Required fields
    required = ['violation_detected', 'confidence', 'primary_clause', 
                'secondary_clauses', 'severity_assessment', 'reasoning',
                'recommended_action', 'false_positive_likelihood']
    if not all(k in data for k in required):
        return None
    
    # Type checks
    if not isinstance(data['violation_detected'], bool):
        return None
    if not (0.0 <= data['confidence'] <= 1.0):
        return None
    if not (0.0 <= data['false_positive_likelihood'] <= 1.0):
        return None
    if data['severity_assessment'] not in ('critical', 'high', 'medium', 'low'):
        return None
    
    # Clause ID validation — reject hallucinated clauses
    if data['primary_clause'] not in VALID_CLAUSE_IDS:
        return None
    data['secondary_clauses'] = [c for c in data['secondary_clauses'] if c in VALID_CLAUSE_IDS]
    
    return data
```

### 8.3 Service B: AI Security Analyst Chatbot

**Trigger:** On-demand, user sends message from chat interface.

**Endpoint:**

```
POST /api/v1/chat/message
  Auth: All roles
  Body: { "session_id": "uuid", "message": "string" }
  Response: Server-Sent Events (streaming text)
```

**Flow:**

```
1. User sends message
2. Backend loads conversation history for this session from PostgreSQL
3. Intent classification via lightweight keyword heuristics (zero latency):

   import re
   def classify_intent(message: str) -> str:
       msg = message.lower()
       if re.search(r'alt-\d{4}-\d+', msg):
           return 'ALERT_INVESTIGATION'
       if any(w in msg for w in ['show', 'list', 'find', 'search', 'how many', 'count']):
           return 'LOG_QUERY'
       if any(w in msg for w in ['compliant', 'compliance', 'posture', 'status']):
           return 'COMPLIANCE_STATUS'
       if re.search(r'ecc\s+\d+-\d+', msg) or re.search(r'\d+-\d+-\d+', msg):
           return 'REGULATORY_GUIDANCE'
       if any(w in msg for w in ['health', 'queue', 'latency', 'model', 'baseline']):
           return 'SYSTEM_STATUS'
       return 'GENERAL'

   This avoids a second LLM call for intent classification. The six intent
   categories are structurally distinct enough that keyword matching is
   correct for >90% of queries. Only one LLM call is needed per message
   (the response generation with tool results in context).

4. Based on detected intent, backend runs tool calls:
   
   ALERT_INVESTIGATION:
     → Query alerts table by alert_number or keywords
     → Load alert details + llm_assessment + event_ids
     → Load referenced log events
   
   LOG_QUERY:
     → Extract structured filter parameters from user message using
       keyword + regex heuristics (no LLM call, no SQL injection risk):

       def extract_log_filters(message: str) -> dict:
           filters = {}
           msg = message.lower()

           # Time range
           if 'today' in msg:
               filters['since'] = 'NOW() - INTERVAL \'1 day\''
           elif 'this week' in msg or 'last 7 days' in msg:
               filters['since'] = 'NOW() - INTERVAL \'7 days\''
           elif 'this month' in msg:
               filters['since'] = 'NOW() - INTERVAL \'30 days\''

           # Result filter
           if 'failed' in msg or 'failure' in msg:
               filters['result'] = 'failed'
           elif 'success' in msg:
               filters['result'] = 'success'

           # Event type
           if 'login' in msg or 'authentication' in msg:
               filters['event_type'] = 'authentication'
           elif 'file' in msg or 'download' in msg:
               filters['event_type'] = 'file_access'

           # Domain
           for domain in ['IAM', 'Network', 'Application', 'Cloud']:
               if domain.lower() in msg:
                   filters['domain'] = domain
                   break

           return filters

     → Build parameterized query using only the extracted filter dict.
       The user message NEVER becomes part of the SQL string.
       The data_scope filter is ALWAYS appended regardless of extracted filters:

       async def run_log_query(filters: dict, data_scope: list[str]) -> dict:
           conditions = ["domain = ANY($1)"]
           params = [data_scope]
           i = 2

           if 'since' in filters:
               conditions.append(f"timestamp > {filters['since']}")
           if 'result' in filters:
               conditions.append(f"result = ${i}")
               params.append(filters['result']); i += 1
           if 'event_type' in filters:
               conditions.append(f"event_type = ${i}")
               params.append(filters['event_type']); i += 1
           if 'domain' in filters:
               conditions[0] = f"domain = ${i}"
               params[0] = filters['domain']; i += 1

           where = " AND ".join(conditions)
           rows = await db.fetch(
               f"SELECT * FROM log_events WHERE {where} LIMIT 100",
               *params
           )
           return {
               "count": len(rows),
               "rows": rows,
               "filters_applied": filters
           }

     → Pass result summary (count, top entities, time distribution) to LLM as context
   
   COMPLIANCE_STATUS:
     → Query alerts grouped by clause_reference
     → Count open vs resolved per NCA control
     → Query Qdrant for the relevant control descriptions
   
   REGULATORY_GUIDANCE:
     → Query Qdrant for the specific NCA control
     → Return control text as context for LLM explanation
   
   SYSTEM_STATUS:
     → Query dashboard KPI computation functions
     → Return system health metrics
   
   GENERAL:
     → No tool calls needed, LLM responds directly

5. Assemble prompt with tool call results as context
6. Stream LLM response back to user via SSE (single LLM call)
7. Save message + response to chat_history table
8. Log interaction to audit_log
```

**Chat History Table:**

```sql
CREATE TABLE chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    user_id UUID REFERENCES users(id) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    sources JSONB,  -- [{"type": "alert", "id": "..."}, {"type": "nca_control", "id": "..."}]
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_chat_session ON chat_history(session_id, created_at);
```

**Chat Session Lifecycle:**

A session represents one continuous conversation. Sessions are created explicitly so the frontend always has a `session_id` before sending the first message.

```
POST /api/v1/chat/session
  Auth: All roles
  Body: (none)
  Response: { "session_id": "uuid", "created_at": "timestamp" }

  Creates a new session. Called once when the user opens the chat panel.
  The returned session_id is stored in the frontend's JS memory for the
  duration of the page visit. Opening a new browser tab always creates a
  new session.

GET /api/v1/chat/session/{session_id}/history
  Auth: All roles (own sessions only)
  Response: { "session_id": "uuid", "messages": [ { "role": "...", "content": "...", "created_at": "..." } ] }

  Loads conversation history for an existing session. Called on page reload
  if a session_id is stored in sessionStorage.

Sessions table:

CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_active_at TIMESTAMPTZ DEFAULT NOW()
);

Session expiry: Sessions older than 24 hours with no activity are considered
expired. The backend rejects messages sent to an expired session with 404,
prompting the frontend to create a new session automatically.

Frontend behaviour:
1. User opens chat panel → POST /api/v1/chat/session → store session_id
   in sessionStorage (cleared when tab closes)
2. User sends message → POST /api/v1/chat/message with stored session_id
3. Tab closes → session_id is lost, next open creates a fresh session
4. Tab reloads → session_id retrieved from sessionStorage
   → GET /api/v1/chat/session/{id}/history to restore context
```

**System Prompt (Service B):**

```
You are SAIA Assistant, an AI security analyst for a Saudi organization. You help admins, compliance officers, and analysts investigate security alerts, query log data, and understand NCA Essential Cybersecurity Controls.

You have access to query results provided in the CONTEXT section below. Base your answers ONLY on the provided context. If the context doesn't contain enough information, say so.

Rules:
- Never reveal raw PII. Use entity hashes or identifiers only.
- Never make definitive compliance judgments. Provide evidence and reasoning; let humans decide.
- Cite specific ECC control IDs (e.g., "2-2-1") when discussing regulatory requirements.
- If unsure, say so. Never fabricate data.
- Keep responses concise and actionable.
- When showing log data, present it in structured tables using markdown.
- Always indicate the time range and scope of data you present.

Current user: {username}
Role: {user_role}
Data scope: {user_data_scope}
Current time: {current_timestamp}
```

**Safety constraints enforced at the application level (not just in the prompt):**
- All database queries include `WHERE domain IN (user.data_scope)` — even if the LLM hallucinates a broader query, the data returned is always scoped.
- The chatbot is read-only. No database mutations happen through the chat interface.
- All chat interactions are logged to both `chat_history` and `audit_log`.

### 8.4 Service C: Evidence Narrative Generator

**Trigger:** On-demand when user clicks "Generate Evidence Pack" on a resolved or verified case.

**Endpoint:**

```
POST /api/v1/cases/{case_id}/generate-evidence
  Auth: Compliance Officer, Admin
  Response: 202 Accepted
            { "case_id": "uuid", "status": "generating",
              "message": "Narrative generation started. You will be notified when complete." }
```

The endpoint returns **immediately** with 202 Accepted. Generation runs in the background. The frontend is notified via WebSocket when the narrative is ready. This prevents a 30-60 second blocking call from hanging the browser during the demo.

**Flow:**

```
1. Validate case exists and belongs to user's data_scope
2. Set cases.narrative_draft = NULL, narrative_status = 'generating' in PostgreSQL
3. Return 202 Accepted immediately (frontend shows a "Generating..." spinner)
4. Background task starts:
   a. Load case from PostgreSQL (case details + all associated alerts)
   b. Load all alerts' llm_assessments, event_ids, analyst_comments
   c. Load referenced log events (canonical fields)
   d. Query Qdrant for full text of all cited NCA controls
   e. Assemble prompt with all case context
   f. Call LLM (non-streaming, max_tokens=4000)
   g. Save narrative to cases.narrative_draft column
   h. Set cases.narrative_status = 'ready', narrative_approved = FALSE
   i. Push WebSocket notification to user:
      { "type": "narrative_ready", "case_id": "uuid", "case_number": "CASE-2025-0001" }
5. Frontend receives WebSocket event → fetches narrative via GET endpoint → displays it
6. Compliance Officer or Admin reviews and clicks "Approve"
   → PATCH /api/v1/cases/{case_id}/approve-narrative sets narrative_approved = TRUE,
     narrative_approved_by = user_id, narrative_approved_at = NOW()
```

**Get Narrative Endpoint (called by frontend after WebSocket notification):**

```
GET /api/v1/cases/{case_id}/narrative
  Auth: Compliance Officer, Admin
  Response: { "narrative_draft": "string (markdown)", "narrative_status": "ready" | "generating",
              "narrative_approved": false }
```

**Cases table addition — narrative_status column:**

```sql
ALTER TABLE cases ADD COLUMN narrative_status VARCHAR(20) DEFAULT 'none'
    CHECK (narrative_status IN ('none', 'generating', 'ready'));
```

**Approve Narrative Endpoint:**

```
PATCH /api/v1/cases/{case_id}/approve-narrative
  Auth: Compliance Officer, Admin
  Response: { "case_id": "uuid", "narrative_approved": true }
```

**System Prompt (Service C):**

```
You are a cybersecurity compliance report writer. Generate a structured evidence narrative for a resolved security case. The narrative must be suitable for inclusion in a regulatory compliance evidence pack submitted to Saudi NCA auditors.

Structure your response as:
1. **Executive Summary** (2-3 sentences)
2. **Timeline of Events** (chronological, with timestamps)
3. **Regulatory Context** (which ECC controls are implicated and why)
4. **Evidence Description** (what the logs show, citing specific events)
5. **Detection & Analysis** (how the violation was detected: rule-based, AI-based, or both)
6. **Resolution** (what actions were taken, by whom, when)
7. **Recommendations** (preventive measures)

Rules:
- Use formal, professional language suitable for regulatory submission.
- Cite specific ECC control IDs.
- Reference specific event timestamps and alert IDs.
- Do not fabricate any details not present in the provided context.

Current user role: {user_role}
Data scope: {user_data_scope}
```

---

## 9. Feedback Loop

When an analyst marks an alert as `true_positive` or `false_positive`, two things happen:

### 9.1 Database Update

```python
async def submit_feedback(alert_id: UUID, verdict: str, comment: str, user_id: UUID):
    # Update alert
    new_status = 'resolved' if verdict == 'true_positive' else 'false_positive'
    await db.execute("""
        UPDATE alerts 
        SET analyst_verdict = $1, analyst_comment = $2, status = $3,
            resolved_at = NOW(), updated_at = NOW()
        WHERE id = $4
    """, verdict, comment, new_status, alert_id)
    
    # Log to audit trail
    await db.execute("""
        INSERT INTO audit_log (user_id, action, resource, details)
        VALUES ($1, 'alert_feedback', $2, $3)
    """, user_id, str(alert_id), json.dumps({"verdict": verdict, "comment": comment}))
```

### 9.2 Qdrant Confirmed Alerts Collection

The alert summary is embedded and added to Qdrant's `confirmed_alerts` collection, so future Service A calls can retrieve similar confirmed examples as few-shot context.

```python
async def add_to_confirmed_alerts(alert_id: UUID):
    alert = await db.fetch_one("SELECT * FROM alerts WHERE id = $1", alert_id)
    
    # Build text representation for embedding
    summary = f"""
    Domain: {alert['domain']}
    Severity: {alert['severity']}
    Anomaly Score: {alert['anomaly_score']}
    Features: {json.dumps(alert['top_features'])}
    Verdict: {alert['analyst_verdict']}
    Clause: {alert['llm_assessment']['primary_clause'] if alert['llm_assessment'] else 'N/A'}
    Comment: {alert['analyst_comment']}
    """
    
    # Embed and store
    embedding = embedding_model.encode(summary)
    
    qdrant_client.upsert(
        collection_name="confirmed_alerts",
        points=[{
            "id": str(alert_id),
            "vector": embedding.tolist(),
            "payload": {
                "alert_number": alert['alert_number'],
                "domain": alert['domain'],
                "severity": alert['severity'],
                "anomaly_score": alert['anomaly_score'],
                "top_features": alert['top_features'],
                "verdict": alert['analyst_verdict'],
                "clause": alert['llm_assessment'].get('primary_clause') if alert['llm_assessment'] else None,
                "comment": alert['analyst_comment'],
                "created_at": alert['created_at'].isoformat()
            }
        }]
    )
```

**Impact on Service A:** The next time Service A processes a new anomaly, its Qdrant query against `confirmed_alerts` may return these confirmed examples. They appear in the prompt as few-shot context:

```
## Similar Past Alerts (Analyst-Confirmed)
Alert ALT-2025-0012: Domain=IAM, Score=0.82
Features: [failed_action_ratio=0.6, hour=2, source_country_is_usual=false]
Analyst verdict: TRUE POSITIVE
Mapped to: 2-2-1
Comment: "Confirmed unauthorized access from external IP during off-hours"

Alert ALT-2025-0019: Domain=IAM, Score=0.71
Features: [failed_action_ratio=0.45, hour=9, events_in_last_hour=50]
Analyst verdict: FALSE POSITIVE
Comment: "Password reset campaign in progress — bulk failures expected"
```

This gives the LLM calibration signal: "anomalies like the first example are real, anomalies like the second example are benign." Over time, as the confirmed collection grows, Service A's accuracy improves without any model retraining.

### 9.3 Periodic Isolation Forest Retraining (Manual)

Admin can trigger model retraining when sufficient labeled data accumulates:

```
1. Export all events from alerts marked true_positive (these are anomalous)
2. Export a random sample of events NOT flagged as anomalous (normal baseline)
3. Optionally: remove events from false_positive alerts from the anomalous set
4. Retrain Isolation Forest per domain using the cleaned normal baseline
5. Save new model weights as .joblib files
6. Restart backend to load new models (or hot-reload via admin endpoint)
```

This is a manual process triggered by admin decision, not automated. For a capstone prototype, this is appropriate.

---

## 10. Layer 5: Presentation Layer

### 10.1 Dashboard

The main dashboard displays:

**A. KPI Cards (4 cards)**
- Active Alerts (count of alerts where status = 'open' or 'investigating')
- Resolved Cases (count of cases where status = 'resolved' or 'verified', last 30 days)
- Pending Reports (count of reports not yet downloaded/reviewed)
- Average Response Time (mean time from alert creation to resolution, last 30 days)

Computed via SQL aggregation queries, cached and refreshed every 60 seconds.

**B. Anomaly Score Distribution (Histogram)**
- Shows distribution of `anomaly_score` across all flagged events in the selected time window
- Vertical line at the detection threshold
- Analyst can select time window: 24h / 7d / 30d
- Analyst can filter by domain

**C. Rolling Precision/Recall Tracker (Line Chart)**
- X-axis: time (daily granularity)
- Y-axis: precision and recall estimates
- Precision = TP / (TP + FP) — computed from analyst feedback on alerts
- Recall estimate = TP / (TP + FN) — FN estimated from back-test if available, otherwise shown as "insufficient data"
- Target lines at precision=0.80 and recall=0.60
- Per-domain toggle

**D. Recent Alerts Table**
- Columns: Alert #, Domain, Severity, Status, Entity, Clause, Anomaly Score, Timestamp
- Filterable by severity, status, domain
- Click to open alert detail view
- Real-time updates via WebSocket

### 10.2 Alerts Page

Alert detail view shows:

```
┌─────────────────────────────────────────────────────────┐
│  Alert ALT-2025-0001                     Status: Open ▼ │
│  Domain: IAM    Severity: Critical    Source: AI + Rule  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  AI Assessment                                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Violation Detected: Yes (91% confidence)           │  │
│  │ Primary Control: ECC 2-2-1 (Identity & Access Mgmt)│  │
│  │ Secondary: ECC 2-7-3 (Network Security)            │  │
│  │                                                    │  │
│  │ Reasoning: Entity accessed HR database at 03:14    │  │
│  │ from non-KSA IP after 7 failed attempts. This      │  │
│  │ deviates from established pattern (08:00-17:00,    │  │
│  │ Riyadh). Suggests possible account compromise.      │  │
│  │                                                    │  │
│  │ Recommended Action: Verify VPN auth or initiate    │  │
│  │ incident response.                                  │  │
│  │                                                    │  │
│  │ False Positive Likelihood: 12%                      │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  Detection Details                                       │
│  Anomaly Score: 0.87 (threshold: 0.65)                  │
│  Top Features:                                           │
│    - hour_of_day: 3 (4.2σ from baseline)                │
│    - source_country_is_usual: False                      │
│    - failed_action_ratio_1h: 0.78 (3.1σ)               │
│                                                          │
│  Triggered Rules: R-IAM-001 (Brute Force Detection)     │
│                                                          │
│  Source Events (3 events)                                │
│  ┌───────────┬────────┬──────────┬────────┬───────────┐ │
│  │ Timestamp │ Action │ Resource │ Result │ Source IP  │ │
│  ├───────────┼────────┼──────────┼────────┼───────────┤ │
│  │ 03:12:01  │ login  │ HR_DB    │ fail   │ 45.x.x.x │ │
│  │ 03:13:14  │ login  │ HR_DB    │ fail   │ 45.x.x.x │ │
│  │ 03:14:02  │ login  │ HR_DB    │ success│ 45.x.x.x │ │
│  └───────────┴────────┴──────────┴────────┴───────────┘ │
│                                                          │
│  Actions                                                 │
│  [Assign to ▼]  [Mark TP]  [Mark FP]  [Add Comment]    │
│                                                          │
│  Comments                                                │
│  (none yet)                                              │
└─────────────────────────────────────────────────────────┘
```

### 10.3 AI Chatbot Panel

A slide-out panel or full page accessible from the sidebar.

```
┌──────────────────────────────────────────────────────────┐
│  SAIA Assistant                                     [×]  │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ 👤 Why was alert ALT-2025-0001 flagged?            │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ 🤖 ALT-2025-0001 was flagged for two reasons:     │  │
│  │                                                    │  │
│  │ **AI Detection:** The Isolation Forest model       │  │
│  │ scored this event at 0.87 (threshold: 0.65).       │  │
│  │ The top contributing factors were a login at       │  │
│  │ 3 AM (4.2σ from this entity's baseline), from     │  │
│  │ an IP geolocated outside Saudi Arabia, after       │  │
│  │ a 78% failure rate in the preceding hour.          │  │
│  │                                                    │  │
│  │ **Rule Trigger:** Rule R-IAM-001 (Brute Force     │  │
│  │ Detection) also fired — 7 failed logins from      │  │
│  │ the same IP within 10 minutes.                     │  │
│  │                                                    │  │
│  │ This maps to NCA ECC 2-2-1 (Identity and Access   │  │
│  │ Management) with 91% confidence.                   │  │
│  │                                                    │  │
│  │ [View Alert] [View ECC 2-2-1]                     │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ 👤 Show me all IAM violations this week            │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ 🤖 In the last 7 days, there were 12 IAM alerts:  │  │
│  │                                                    │  │
│  │ | Severity | Count | Primary Control |             │  │
│  │ |----------|-------|-----------------|             │  │
│  │ | Critical |   2   | 2-2-1           |             │  │
│  │ | High     |   5   | 2-2-1, 2-2-4   |             │  │
│  │ | Medium   |   4   | 2-2-3           |             │  │
│  │ | Low      |   1   | 2-2-1           |             │  │
│  │                                                    │  │
│  │ 3 have been resolved, 9 remain open.               │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────┐  [Send]   │
│  │ Type your question...                     │           │
│  └──────────────────────────────────────────┘           │
└──────────────────────────────────────────────────────────┘
```

### 10.4 Model Health Panel (Dashboard Sub-Section)

```
┌────────────────────────────────────────────────────────┐
│  Model Health                                           │
│                                                         │
│  Events Processed (24h):     12,847                    │
│  Events Flagged (24h):          342  (2.7%)            │
│  Quarantined (24h):              89  (0.7%)            │
│                                                         │
│  LLM Queue Depth:                 3  pending            │
│  LLM Avg Latency:             2.3s                      │
│                                                         │
│  Baselines Active:              156  entities           │
│  Drift Alerts:                    2  (user_x, host_y)  │
│                                                         │
│  Feedback This Month:                                   │
│    True Positives:               24                     │
│    False Positives:               7                     │
│    Rolling Precision:          77.4%  (target: 80%)    │
└────────────────────────────────────────────────────────┘
```

---

## 11. API Contract

### 11.1 Alert Payload

Used by: Dashboard alerts table, alert detail view, WebSocket push notifications.

```json
{
  "id": "uuid",
  "alert_number": "ALT-2025-0001",
  "domain": "IAM",
  "severity": "critical",
  "status": "open",
  "source": "both",
  "entity_principal": "user_a3f8",
  "clause_reference": "2-2-1",
  "anomaly_score": 0.87,
  "top_features": [
    { "name": "hour_of_day", "value": 3, "deviation_sigma": 4.2 },
    { "name": "source_country_is_usual", "value": false, "deviation_sigma": null },
    { "name": "failed_action_ratio_1h", "value": 0.78, "deviation_sigma": 3.1 }
  ],
  "triggered_rules": [
    { "rule_id": "uuid", "rule_name": "Brute Force Detection", "clause": "2-2-1" }
  ],
  "llm_assessment": {
    "violation_detected": true,
    "confidence": 0.91,
    "primary_clause": "2-2-1",
    "secondary_clauses": ["2-7-3"],
    "severity_assessment": "critical",
    "reasoning": "Entity accessed HR database at 03:14 from non-KSA IP...",
    "recommended_action": "Verify VPN authorization or initiate incident response.",
    "false_positive_likelihood": 0.12
  },
  "event_count": 3,
  "assigned_to": null,
  "analyst_verdict": null,
  "analyst_comment": null,
  "created_at": "2025-03-11T03:14:02Z",
  "updated_at": "2025-03-11T03:16:34Z"
}
```

**Note:** `llm_assessment` is `null` until Service A processes the alert. The frontend should display "AI analysis pending..." when this field is null.

### 11.2 Chatbot Messages

**Request:**
```json
POST /api/v1/chat/message
{
  "session_id": "uuid",
  "message": "Why was ALT-2025-0001 flagged?"
}
```

**Response:** Server-Sent Events stream.

```
event: token
data: {"text": "ALT-2025-0001 was flagged "}

event: token
data: {"text": "because the Isolation Forest model "}

...

event: done
data: {
  "sources": [
    { "type": "alert", "id": "uuid", "label": "ALT-2025-0001" },
    { "type": "nca_control", "id": "2-2-1", "label": "Identity & Access Management" }
  ]
}
```

### 11.3 KPI Endpoints

```
GET /api/v1/dashboard/kpis
Response:
{
  "active_alerts": 27,
  "resolved_cases_30d": 142,
  "pending_reports": 8,
  "avg_response_time_hours": 2.4,
  "data_quality_score": 0.96
}

GET /api/v1/dashboard/anomaly-distribution?window=24h&domain=IAM
Response:
{
  "buckets": [
    { "range_start": 0.0, "range_end": 0.1, "count": 4521 },
    { "range_start": 0.1, "range_end": 0.2, "count": 3102 },
    ...
    { "range_start": 0.9, "range_end": 1.0, "count": 12 }
  ],
  "threshold": 0.65,
  "total_events": 12847,
  "flagged_events": 342
}

GET /api/v1/dashboard/precision-tracker?window=30d
Response:
{
  "data_points": [
    { "date": "2025-03-01", "precision": 0.82, "tp_count": 5, "fp_count": 1, "domain": "IAM" },
    { "date": "2025-03-02", "precision": 0.75, "tp_count": 3, "fp_count": 1, "domain": "IAM" },
    ...
  ],
  "overall_precision": 0.774,
  "target_precision": 0.80,
  "total_tp": 24,
  "total_fp": 7
}

GET /api/v1/dashboard/model-health
Response:
{
  "events_processed_24h": 12847,
  "events_flagged_24h": 342,
  "events_quarantined_24h": 89,
  "llm_queue_depth": 3,
  "llm_avg_latency_ms": 2340,
  "active_baselines": 156,
  "drift_alerts": [
    { "entity": "user_x", "domain": "IAM", "drift_metric": "event_volume", "shift_sigma": 3.2 }
  ],
  "feedback_this_month": { "tp": 24, "fp": 7, "precision": 0.774 }
}
```

### 11.4 Other Core Endpoints

```
GET    /api/v1/health               → { status, db, llm, qdrant }  (No auth required)

POST   /api/v1/auth/login           → { access_token, user }
POST   /api/v1/auth/register        → { user }  (Admin only)

POST   /api/v1/logs/upload          → { upload_id, events_parsed, events_accepted, events_quarantined }
POST   /api/v1/logs/ingest          → { upload_id, events_parsed, events_accepted, events_quarantined }  (JSON body)
GET    /api/v1/logs/events          → paginated log events (filterable by domain, time, principal)
GET    /api/v1/logs/uploads         → list of upload batches with stats

GET    /api/v1/alerts               → paginated alerts (filterable by severity, status, domain)
GET    /api/v1/alerts/{id}          → single alert detail (full payload per 11.1)
PATCH  /api/v1/alerts/{id}          → update status, assign, add comment
POST   /api/v1/alerts/{id}/feedback → submit TP/FP verdict  (Admin, Compliance Officer)

GET    /api/v1/rules                → list all rules
POST   /api/v1/rules               → create rule  (Admin, Compliance Officer)
PATCH  /api/v1/rules/{id}          → update rule  (Admin, Compliance Officer)
POST   /api/v1/rules/{id}/publish  → publish rule  (Admin only)
POST   /api/v1/rules/{id}/test     → dry-run rule against recent logs

GET    /api/v1/cases                         → list cases
POST   /api/v1/cases                         → create case from alert group
PATCH  /api/v1/cases/{id}                    → update case status
POST   /api/v1/cases/{id}/generate-evidence  → Service C: generate narrative  (Admin, Compliance Officer)
PATCH  /api/v1/cases/{id}/approve-narrative   → approve narrative draft  (Admin, Compliance Officer)

POST   /api/v1/chat/message         → chatbot (SSE streaming)  (All roles)
GET    /api/v1/chat/sessions        → list user's chat sessions
GET    /api/v1/chat/sessions/{id}   → load chat history

POST   /api/v1/reports/generate     → generate compliance report  (Admin, Compliance Officer)
                                      Body: { framework, date_from, date_to, format }
GET    /api/v1/reports              → list generated reports

GET    /api/v1/dashboard/kpis                  → KPI summary
GET    /api/v1/dashboard/anomaly-distribution  → anomaly score histogram
GET    /api/v1/dashboard/precision-tracker     → rolling precision/recall
GET    /api/v1/dashboard/model-health          → LLM queue depth, latency, baselines, drift
```

---

## 12. Evaluation Strategy

### 12.1 Evaluation Dataset Construction

Since real labeled violation data is scarce, construct a **synthetic evaluation dataset** with known ground truth.

**Step 1: Define Violation Scenarios (50-100 scenarios)**

For each NCA ECC control in scope, define 5-10 concrete violation scenarios with realistic log event patterns.

| Scenario ID | Domain | Description | Expected Clause | Expected Severity |
|------------|--------|-------------|-----------------|-------------------|
| EVAL-IAM-001 | IAM | 20 failed logins in 5 min from single IP, then 1 success | 2-2-1 | High |
| EVAL-IAM-002 | IAM | Admin login at 3 AM Saturday from non-KSA IP | 2-2-1 | Critical |
| EVAL-IAM-003 | IAM | Login from Riyadh, then login from London 30 min later (same user) | 2-2-1 | Critical |
| EVAL-IAM-004 | IAM | Account inactive 90 days, suddenly accesses 15 resources in 1 hour | 2-2-4 | High |
| EVAL-IAM-005 | IAM | User role escalated to admin without corresponding change ticket | 2-2-4 | Critical |
| EVAL-NET-001 | Network | 10x normal outbound traffic to external IP over 2 hours | 2-7-3 | High |
| EVAL-NET-002 | Network | Port scan pattern: connection attempts to 50+ ports on single host | 2-7-1 | High |
| EVAL-LOG-001 | Application | Log volume drops 90% from a source for 18 hours | 2-13-1 | Medium |
| EVAL-LOG-002 | Application | Audit log entries deleted (gap in sequential IDs) | 2-9-1 | Critical |
| EVAL-BENIGN-001 | IAM | 5 failed logins during known password reset campaign (false positive test) | None | None |
| EVAL-BENIGN-002 | Network | High traffic during scheduled backup window (false positive test) | None | None |
| EVAL-COLD-001 | IAM | New entity (never seen before) performs normal login during business hours — should NOT be flagged by ML | None | None |
| EVAL-COLD-002 | IAM | New entity performs genuinely suspicious activity (admin login at 3 AM) — should be caught by rules even though ML is suppressed | 2-2-1 | High |
| ... | ... | ... | ... | ... |

**Step 2: Generate Synthetic Log Events**

For each scenario, create realistic log events matching the pattern, embedded in a background of 1000+ normal events. Document the exact event IDs that constitute the violation.

```python
# Example: EVAL-IAM-001 (Brute Force)
scenario_events = []
# Background: 1000 normal login events over 24 hours
for i in range(1000):
    scenario_events.append({
        "timestamp": random_business_hour(),
        "event_type": "authentication",
        "principal": random_user(),
        "action": "login",
        "resource": random_resource(),
        "result": "success",
        "source_ip": known_ip_for_user(),
        "domain": "IAM"
    })

# Violation: 20 failed logins in 5 minutes
attack_user = "user_eval_target"
attack_ip = "203.0.113.42"  # External IP
for i in range(20):
    scenario_events.append({
        "timestamp": base_time + timedelta(seconds=i*15),
        "event_type": "authentication",
        "principal": attack_user,
        "action": "login",
        "resource": "HR_DATABASE",
        "result": "failure",
        "source_ip": attack_ip,
        "domain": "IAM",
        "_ground_truth": "EVAL-IAM-001"  # Internal label, not sent to system
    })
# Followed by 1 success
scenario_events.append({
    "timestamp": base_time + timedelta(minutes=5, seconds=10),
    "event_type": "authentication",
    "principal": attack_user,
    "action": "login",
    "resource": "HR_DATABASE",
    "result": "success",
    "source_ip": attack_ip,
    "domain": "IAM",
    "_ground_truth": "EVAL-IAM-001"
})
```

**Step 3: Run Evaluation**

Feed each scenario's events through the full pipeline and record results.

### 12.2 Metrics and Targets

| # | Metric | Definition | Target | How Measured |
|---|--------|-----------|--------|-------------|
| 1 | **ML Detection Recall** | Fraction of injected violation scenarios where at least one event is flagged by ML | ≥ 70% | Count scenarios where IF or baseline flags ≥1 event / total violation scenarios |
| 2 | **ML Detection Precision** | Fraction of ML-flagged events that belong to a known violation scenario | ≥ 80% | Count flagged events in violation scenarios / total flagged events |
| 3 | **Rule Detection Recall** | Fraction of rule-detectable scenarios where the rule fires | ≥ 90% | Only applicable to scenarios matching an active rule |
| 4 | **Regulatory Mapping Accuracy** | Fraction of enriched alerts where the LLM's primary_clause matches the ground truth clause | ≥ 85% | Compare llm_assessment.primary_clause to scenario's expected clause |
| 5 | **LLM Output Validity Rate** | Fraction of Service A calls that return valid, parseable JSON matching the schema | ≥ 95% | Count valid responses / total LLM calls |
| 6 | **LLM Reasoning Quality** | Human-rated coherence and usefulness of the reasoning field (1-5 scale, rated by team + supervisor) | ≥ 4.0 / 5.0 | Blind review of 50 LLM reasoning outputs |
| 7 | **False Positive Identification** | Fraction of intentionally benign scenarios (EVAL-BENIGN-*) that are NOT flagged or are flagged with high FP likelihood | ≥ 80% | Count benign scenarios correctly identified / total benign scenarios |
| 8 | **End-to-End Latency (P95)** | Time from event upload completion to enriched alert visible in dashboard | ≤ 5 min | Measure across all evaluation scenarios |
| 9 | **Chatbot Response Latency** | Time from user message sent to first token received | ≤ 10 sec | Measure across 20 representative chatbot queries |
| 10 | **Chatbot Accuracy** | Fraction of chatbot answers that correctly reference the right alerts, events, or controls | ≥ 85% | Scripted test: 20 questions with known correct answers |

### 12.3 Evaluation Protocol

**Phase 1: Component Testing (Week 6)**

| Test | What | How | Pass Criteria |
|------|------|-----|---------------|
| 1.1 | Feature extractor correctness | Unit tests: given a known event, verify all 25 features are computed correctly | All tests pass |
| 1.2 | Isolation Forest detection | Feed 10 anomalous events + 1000 normal events, check flagging | ≥ 7/10 anomalous events flagged |
| 1.3 | Statistical baseline accuracy | Inject a known entity profile, verify deviation scores | Deviation scores within 5% of hand-calculated values |
| 1.4 | Score fusion | Verify combined scores produce correct severity assignments | 100% correct severity mapping |
| 1.5 | LLM prompt → valid JSON | Send 20 diverse anomaly summaries to Service A, check output | ≥ 19/20 valid JSON responses |
| 1.6 | RAG retrieval relevance | For 10 known anomaly types, verify top-3 retrieved NCA controls contain the correct one | ≥ 8/10 correct |
| 1.7 | Clause ID validation | Verify validator rejects hallucinated clause IDs | 100% rejection of invalid IDs |

**Phase 2: Integration Testing (Week 7)**

| Test | What | How | Pass Criteria |
|------|------|-----|---------------|
| 2.1 | End-to-end pipeline | Upload 5 evaluation scenario files, verify alerts appear with correct LLM enrichment | All 5 produce correct alerts |
| 2.2 | Chatbot investigation | Ask chatbot about each generated alert, verify accuracy | ≥ 85% accurate responses |
| 2.3 | Evidence narrative | Generate evidence pack for a resolved case, review quality | Narrative covers all 7 required sections, no fabricated details |
| 2.4 | Feedback loop | Mark alert as TP, verify it appears in Qdrant, verify next similar anomaly prompt includes it | Confirmed alert appears in RAG results |
| 2.5 | RBAC enforcement | Log in as Analyst, attempt to publish rule → should fail. Log in as Analyst with IAM-only scope, query Network alerts → should return empty. | All permission checks pass |
| 2.6 | Data quality gate | Upload file with 30% malformed events, verify quarantine | Quarantined count matches expected |

**Phase 3: Full Evaluation Run (Week 8)**

Run all 50-100 synthetic evaluation scenarios through the complete system. Compute all 10 metrics. Document results in a table. Discuss any metrics that fall below target and explain mitigation strategies.

### 12.4 Evaluation Reporting Template

```
## Evaluation Results

### Test Environment
- Hardware: [local specs] + [cloud GPU specs]
- LLM Model: Llama 3.1 70B Q4
- Dataset: [X] evaluation scenarios ([Y] violations, [Z] benign)
- Date: [evaluation date]

### Metric Results

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| ML Detection Recall | ≥ 70% | __% | PASS/FAIL |
| ML Detection Precision | ≥ 80% | __% | PASS/FAIL |
| Regulatory Mapping Accuracy | ≥ 85% | __% | PASS/FAIL |
| LLM Output Validity | ≥ 95% | __% | PASS/FAIL |
| LLM Reasoning Quality | ≥ 4.0 | __/5.0 | PASS/FAIL |
| False Positive ID | ≥ 80% | __% | PASS/FAIL |
| End-to-End Latency P95 | ≤ 5 min | __ sec | PASS/FAIL |
| Chatbot Latency | ≤ 10 sec | __ sec | PASS/FAIL |
| Chatbot Accuracy | ≥ 85% | __% | PASS/FAIL |

### Discussion
[For each metric below target, explain why and what would improve it]

### Feedback Loop Impact
[Show precision before/after incorporating analyst feedback into RAG]
```

---

## 13. Implementation Roadmap

| Week | Focus | Deliverables |
|------|-------|-------------|
| **1** | Foundation | PostgreSQL schema deployed. FastAPI project structure. Auth (JWT + RBAC). Seed script (NCA controls → Qdrant). Upload endpoint + normalization pipeline. |
| **2** | Detection | Feature extractor (25 features). Entity baseline computation. Isolation Forest training on synthetic data. Score fusion. Feature quality gate. |
| **3** | Alerting | Rule engine with 5 seed rules. Alert aggregation + deduplication. LLM queue. WebSocket push for new alerts. Alert CRUD endpoints. |
| **4** | LLM Integration | vLLM deployed on cloud GPU. Service A (enrichment) with prompt v1. JSON validation + fallback. Service A wired to LLM queue. Control-Signal Matrix loaded. |
| **5** | Chatbot + Evidence | Service B (chatbot) with intent routing + SSE streaming. Service C (evidence narrative). Chat history persistence. Audit logging. |
| **6** | Frontend | Dashboard with KPIs, histogram, precision tracker, model health. Alert detail view with LLM reasoning. Chatbot panel. Rules management page. Reports page. |
| **7** | Integration + Feedback | Feedback loop (TP/FP → Qdrant confirmed collection). Few-shot examples in Service A prompts. End-to-end testing. RBAC verification. Build evaluation dataset. |
| **8** | Evaluation + Polish | Run full evaluation protocol. Compute all metrics. Fix critical issues. Documentation. Demo preparation. |

---

## 14. Infrastructure Diagram (Final)

```
┌─────────────────────────────────────────────────────────────────┐
│                     LOCAL MACHINE / SERVER                        │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Docker Compose                                              │ │
│  │                                                              │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │ │
│  │  │  FastAPI      │  │  PostgreSQL  │  │  Qdrant          │  │ │
│  │  │  Backend      │  │  16          │  │  (Docker)        │  │ │
│  │  │              │  │              │  │                  │  │ │
│  │  │  - Auth      │  │  - users     │  │  Collections:   │  │ │
│  │  │  - Ingestion │  │  - log_events│  │  - nca_controls │  │ │
│  │  │  - Rules     │  │  - alerts    │  │  - confirmed_   │  │ │
│  │  │  - ML scoring│  │  - cases     │  │    alerts       │  │ │
│  │  │  - Alert agg │  │  - rules     │  │                  │  │ │
│  │  │  - LLM queue │  │  - audit_log │  │                  │  │ │
│  │  │  - Chat API  │  │  - chat_hist │  │                  │  │ │
│  │  │  - Dashboard │  │  - baselines │  │                  │  │ │
│  │  │    API       │  │  - llm_queue │  │                  │  │ │
│  │  │              │  │  - csm       │  │                  │  │ │
│  │  │  Port: 8000  │  │  Port: 5432  │  │  Port: 6333     │  │ │
│  │  └──────┬───────┘  └──────────────┘  └──────────────────┘  │ │
│  │         │                                                    │ │
│  │  ┌──────┴───────┐                                           │ │
│  │  │  Embedding   │  bge-base-en-v1.5 (CPU, loaded in-process)│ │
│  │  │  Model       │  Used for: Qdrant queries, seeding        │ │
│  │  └──────────────┘                                           │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Frontend (served by FastAPI or Nginx)                       │ │
│  │  HTML / CSS / JS                                             │ │
│  │  - Dashboard, Alerts, Rules, Reports, Chatbot               │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Static Files                                                │ │
│  │  - Isolation Forest models (.joblib per domain)              │ │
│  │  - Control-Signal Matrix (control_signal_matrix.json)        │ │
│  │  - NCA ECC chunks (generated by seed script)                │ │
│  └─────────────────────────────────────────────────────────────┘ │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ HTTPS (LLM API calls only)
                                │ Data sent: anomaly summaries,
                                │ NCA control text, chat context
                                │ (no raw logs, PII is hashed)
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              SAUDI-BASED CLOUD GPU SERVER                         │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  vLLM Server                                                 │ │
│  │                                                              │ │
│  │  Model: Llama 3.1 70B (Q4_K_M quantization)                │ │
│  │  API: OpenAI-compatible /v1/chat/completions                │ │
│  │  GPU: A100 80GB (or equivalent)                              │ │
│  │                                                              │ │
│  │  Serves:                                                     │ │
│  │  - Service A (anomaly enrichment) — background, batched     │ │
│  │  - Service B (chatbot) — on-demand, streaming               │ │
│  │  - Service C (evidence narrative) — on-demand               │ │
│  │                                                              │ │
│  │  Port: 8000 (behind TLS reverse proxy)                      │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 15. LLM Data Classification

The following fields are sent to the Saudi-based cloud LLM server in prompts. No raw logs are ever sent.

**Included in LLM prompts:**

| Field | Service | Justification |
|-------|---------|---------------|
| `anomaly_score` | A | Numerical, no PII |
| `top_features` (names + values) | A | Feature names are generic (e.g., "hour_of_day"), values are numerical |
| `baseline_deviations` | A | Numerical z-scores, no PII |
| `event_type`, `action`, `result` | A | Categorical, no PII |
| `source_ip` | A | Included because needed for meaningful reasoning about geographic anomalies. Organizational infrastructure detail — acceptable for Saudi-hosted cloud; production on-prem deployment would eliminate this concern. |
| `resource` (e.g., "HR_DATABASE") | A | Included because resource context is essential for severity assessment. Reveals system architecture — same caveat as source_ip. |
| `domain`, `severity`, `timestamp` | A, B, C | Categorical/temporal, no PII |
| NCA ECC control text | A, B, C | Public regulatory document, no sensitivity |
| Confirmed alert summaries (from Qdrant) | A | Contain same fields as above, already vetted |
| User chat messages | B | User-initiated, user accepts this by using the chatbot |
| Case metadata + alert summaries | C | Same fields as Service A, aggregated per case |

**Never sent to LLM:**

| Field | Reason |
|-------|--------|
| `raw_log` (JSONB) | May contain unmasked PII, credentials, or sensitive payloads |
| `principal` (real username) | PII — always hashed before inclusion in prompts |
| `password_hash` | Obviously never |
| User personal data from `users` table | Not relevant to analysis |

**Entity principal handling:** Before inclusion in any LLM prompt, the `principal` field is replaced with a truncated hash (e.g., `user_a3f8`). The LLM never sees real usernames or email addresses.

---

## 16. Production Considerations

Items documented for completeness. Not built in the capstone prototype; deferred to production.

| Item | Current State | Production Improvement |
|------|--------------|----------------------|
| `cross_entity_correlation_score` (feature 25) | Computed per-event via SQL query | Cache per-resource per 5-minute window to reduce query load |
| Baseline recomputation | Full recompute (30-day lookback) after each upload batch | Incremental median updates (Welford-style) or scheduled hourly job |
| Qdrant `confirmed_alerts` TTL | Collection grows indefinitely | Filter by `max_age_days=180` in Qdrant queries; periodic cleanup job |
| LLM data to cloud | Saudi-based cloud server, acceptable for prototype | On-premises GPU deployment eliminates all cloud data concerns |
| Service C blocking | ~~Synchronous 30-60 second LLM call~~ **Resolved in prototype:** Returns 202 Accepted immediately, narrative delivered via WebSocket when ready. | No further action needed. |
| `principal_risk_score` feedback loop (feature 18) | Risk score is an IF input feature and also driven by IF output (anomaly flags). Mitigated by: batch-only updates (never mid-batch), exponential decay, and being 1-of-25 features. Circularity is weak but exists. | Remove feature 18 from IF input features entirely. Use it only as a post-score severity multiplier: `final_severity = base_severity * (1 + risk_score)`. This eliminates the circularity while preserving the risk history signal. |

---

## 17. File Structure

```
saia/
├── docker-compose.yml
├── .env                          # DB credentials, LLM URL, JWT secret
├── README.md
│
├── backend/
│   ├── main.py                   # FastAPI app, middleware, startup
│   ├── config.py                 # Settings from .env
│   ├── database.py               # PostgreSQL connection pool (asyncpg)
│   ├── models/                   # Pydantic schemas
│   │   ├── auth.py
│   │   ├── log_event.py
│   │   ├── alert.py
│   │   ├── rule.py
│   │   ├── case.py
│   │   └── chat.py
│   ├── routers/                  # API endpoint handlers
│   │   ├── auth.py
│   │   ├── logs.py
│   │   ├── alerts.py
│   │   ├── rules.py
│   │   ├── cases.py
│   │   ├── chat.py
│   │   ├── dashboard.py
│   │   └── reports.py
│   ├── services/                 # Business logic
│   │   ├── ingestion.py          # Parse, normalize, quality gate
│   │   ├── feature_extractor.py  # 25 features from canonical event
│   │   ├── ml_detector.py        # Isolation Forest + baselines + score fusion
│   │   ├── rule_engine.py        # Rule evaluation
│   │   ├── alert_aggregator.py   # Dedup, create, merge alerts
│   │   ├── llm_client.py         # HTTP calls to vLLM server
│   │   ├── enrichment_service.py # Service A: anomaly enrichment (prompt, parse, validate)
│   │   ├── chatbot_service.py    # Service B: chatbot (intent routing, context building)
│   │   ├── narrative_service.py  # Service C: evidence narrative generation
│   │   ├── rag_service.py        # Qdrant queries (controls + confirmed alerts)
│   │   ├── feedback.py           # TP/FP processing + Qdrant upsert
│   │   └── websocket.py          # WebSocket manager for real-time pushes
│   ├── middleware/
│   │   ├── auth.py               # JWT verification + RBAC check
│   │   └── audit.py              # Audit log writer
│   ├── workers/
│   │   └── llm_queue_worker.py   # Background worker: process LLM queue every 2 min
│   └── ml_models/                # Saved Isolation Forest .joblib files
│       ├── if_iam_v1.joblib
│       ├── if_network_v1.joblib
│       ├── if_application_v1.joblib
│       └── if_cloud_v1.joblib
│
├── seed/
│   ├── seed_nca_controls.py      # Parse NCA PDF → chunk → embed → load Qdrant
│   ├── seed_rules.py             # Load starter rules into PostgreSQL
│   ├── seed_csm.py               # Load Control-Signal Matrix into PostgreSQL
│   ├── seed_lookup_tables.py     # Load action_privilege_levels + asset_registry
│   ├── control_signal_matrix.json
│   ├── action_privileges.json    # Action → privilege level mappings
│   └── asset_registry.json       # Asset → criticality + sensitivity mappings
│
├── evaluation/
│   ├── scenarios/                # Synthetic evaluation scenario files
│   │   ├── eval_iam_001.json
│   │   ├── eval_iam_002.json
│   │   └── ...
│   ├── generate_scenarios.py     # Script to generate synthetic evaluation data
│   ├── run_evaluation.py         # Script to run all scenarios and compute metrics
│   └── results/                  # Evaluation output
│       └── evaluation_report.md
│
├── frontend/
│   ├── index.html                # Dashboard
│   ├── alerts.html
│   ├── alert-detail.html
│   ├── rules.html
│   ├── reports.html
│   ├── chat.html                 # Chatbot page
│   └── assets/
│       ├── css/
│       ├── js/
│       │   ├── api.js            # API client (fetch wrapper with JWT)
│       │   ├── websocket.js      # WebSocket client for real-time alerts
│       │   ├── charts.js         # Histogram, precision tracker, pie chart
│       │   └── chat.js           # Chatbot SSE client
│       └── img/
│
├── sql/
│   ├── 001_schema.sql            # All CREATE TABLE statements
│   ├── 002_indexes.sql           # All indexes (B-tree, GIN, composite)
│   └── 003_seed_data.sql         # Default admin user, initial config
│
└── scripts/
    ├── train_isolation_forest.py  # Manual retraining script
    ├── export_feedback.py         # Export labeled data for retraining
    └── log_generator.py           # Demo fake log generator (streams to /api/v1/logs/ingest every 5 sec)
```
