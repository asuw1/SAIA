# SAIA V4 Utility Scripts and Evaluation Framework

Complete production-ready utility scripts and evaluation framework for the SAIA V4 security analysis platform.

## Overview

This package includes:
- **3 Utility Scripts** for log generation, model training, and feedback export
- **2 Evaluation Framework Scripts** for scenario generation and evaluation execution
- **Comprehensive metrics computation** across 10 performance dimensions
- **Full production-ready code** with error handling, logging, and CLI support

## Utility Scripts

### 1. `scripts/log_generator.py`

Generates realistic synthetic security log events and streams them to the API.

**Features:**
- Generates realistic normal business events across all 4 domains (IAM, Network, Application, Cloud)
- Injects 5% synthetic anomalies: off-hours access, brute force, privilege escalation, unusual IPs, lateral movement
- Saudi Arabia business hours awareness (Sun-Thu 7AM-6PM)
- Configurable batch sizes, intervals, and anomaly ratios
- Full CLI with argparse support
- Real-time statistics and progress logging

**Usage:**
```bash
# Basic usage
python scripts/log_generator.py --url http://localhost:8000 --token <JWT>

# Custom parameters
python scripts/log_generator.py \
  --url http://localhost:8000 \
  --token <JWT> \
  --duration 3600 \
  --interval 5 \
  --min-events 10 \
  --max-events 30 \
  --domains IAM Network \
  --anomaly-ratio 0.10

# Run infinitely
python scripts/log_generator.py --url http://localhost:8000 --token <JWT>
```

**Output:**
```
INFO - Starting log generator for domains: IAM, Network, Application, Cloud
INFO - Sending batches every 5 seconds
INFO - Anomaly ratio: 5.0%
INFO - Batch sent: 25 accepted, 0 quarantined from 25 parsed
...
INFO - Progress: 10 batches, 275 events, 10 successful, 0 failed
```

### 2. `scripts/train_isolation_forest.py`

Trains Isolation Forest anomaly detection models per domain.

**Features:**
- Loads labeled data from PostgreSQL (TP/FP alerts)
- Automatic synthetic data generation if no real data available
- Trains 4 per-domain models with optimized hyperparameters:
  - n_estimators: 200
  - max_features: 0.8
  - Contamination rates: IAM=8%, Network=5%, Application=6%, Cloud=7%
- Saves models as `.joblib` files to `backend/ml_models/`
- Generates training statistics and evaluation metrics
- JSON report of training results

**Usage:**
```bash
# Train all domains with database data
python scripts/train_isolation_forest.py

# Train only specific domains
python scripts/train_isolation_forest.py --domains IAM Network

# Use only synthetic data (no database connection)
python scripts/train_isolation_forest.py --synthetic-only

# Custom output directory
python scripts/train_isolation_forest.py --output-dir /custom/path
```

**Output:**
```
Training model for IAM domain
  Normal samples: 2000
  Anomalous samples: 200
  Contamination rate: 8.0%
  Model trained successfully

Training Summary
IAM:
  Samples: 2000 normal, 200 anomalous
  Contamination: 8.0%
  False positives: 5.20%
  Detection rate: 75.50%
  Model: backend/ml_models/isolation_forest_iam.joblib
```

### 3. `scripts/export_feedback.py`

Exports labeled alert data for analysis and model training.

**Features:**
- Queries all alerts with analyst verdicts (TP/FP)
- Joins with log_events to get complete event context
- Exports 25 ML feature values per alert
- CSV format for easy analysis in Excel/Pandas
- Statistics by verdict and domain

**Usage:**
```bash
# Export to default file
python scripts/export_feedback.py

# Export to custom file
python scripts/export_feedback.py --output my_feedback_data.csv

# Export to custom directory
python scripts/export_feedback.py --output /data/exports/feedback.csv
```

**Output CSV Columns:**
```
alert_number, domain, severity, verdict, anomaly_score,
hour_of_day, day_of_week, is_business_hours, is_weekend,
minutes_since_last_event, events_in_last_hour,
unique_resources_1h, unique_actions_1h, failed_action_ratio_1h,
privilege_level, is_new_resource, is_new_action,
deviation_from_hourly_baseline, deviation_from_daily_baseline,
source_ip_is_known, source_country_is_usual, asset_criticality,
principal_risk_score, concurrent_sessions, is_sensitive_resource,
entity_event_volume_zscore, entity_error_rate_zscore,
entity_resource_diversity_zscore, entity_privilege_escalation_rate,
cross_entity_correlation_score, comment
```

**Sample Output:**
```
INFO - Found 142 verdicted alerts
INFO - Processing 142 alerts...
Export Summary
Total alerts exported: 142
True positives: 98
False positives: 44
By domain:
  IAM: 45
  Network: 38
  Application: 34
  Cloud: 25
Exported to: feedback_export.csv
```

## Evaluation Framework

### 1. `evaluation/generate_scenarios.py`

Generates 50 comprehensive evaluation scenarios with ground truth labels.

**Features:**
- **30 Violation scenarios** (6 per domain)
  - Covers all SAIA clause references
  - Includes typical attack patterns: brute force, privilege escalation, off-hours access, unusual IPs, lateral movement
- **10 Benign scenarios** (2-3 per domain)
  - Should NOT trigger alerts
  - Normal business activity patterns
- **5 Cold-start scenarios**
  - New entities (users, IPs) to test baseline learning
- **5 Edge-case scenarios**
  - Borderline events testing decision boundaries
  - Partial data, unusual combinations

**Features:**
- Each scenario: 1000+ background normal events + 10 test events
- Ground truth event IDs labeled for validation
- SAIA-compliant clause references
- Saved as individual JSON files for parallelization
- Comprehensive metadata: scenario type, domain, expected clause, severity

**Usage:**
```bash
# Generate to default directory
python evaluation/generate_scenarios.py

# Generate to custom directory
python evaluation/generate_scenarios.py --output /data/eval_scenarios
```

**Output:**
```
Generating Evaluation Scenarios
Generating scenario 1/50: EVAL-IAM-001
  → Saved EVAL-IAM-001.json
...
Scenario Generation Summary
Total scenarios generated: 50
  Violation scenarios: 30
  Benign scenarios: 10
  Cold-start scenarios: 5
  Edge-case scenarios: 5
Scenarios saved to: evaluation/scenarios
```

**Scenario File Format (JSON):**
```json
{
  "metadata": {
    "scenario_id": "EVAL-IAM-001",
    "type": "violation",
    "domain": "IAM",
    "expected_clause": "SAIA-IAM-003",
    "expected_severity": "Critical",
    "description": "IAM security violation: SAIA-IAM-003",
    "ground_truth_event_ids": ["test_event_0", "test_event_1"],
    "generated_at": "2024-01-15T10:00:00+00:00"
  },
  "events": [
    {
      "timestamp": "2024-01-15T10:00:00+00:00",
      "source": "source_iam",
      "event_type": "authentication",
      "principal": "user_042",
      "action": "login",
      "resource": "ldap_server",
      "result": "success",
      "source_ip": "198.51.100.42",
      "asset_id": "auth_cluster_001",
      "domain": "IAM"
    }
  ]
}
```

### 2. `evaluation/run_evaluation.py`

Executes all scenarios and computes 10 performance metrics against ground truth.

**Features:**
- Loads all 50 scenario JSON files from `evaluation/scenarios/`
- Uploads events via `/api/v1/logs/ingest`
- Waits for alert processing with configurable timeout
- Computes confusion matrix (TP/FP/TN/FN)
- Calculates all 10 metrics with targets:

| Metric | Target | Type |
|--------|--------|------|
| ML Detection Recall | ≥70% | Detection accuracy on violations |
| ML Detection Precision | ≥80% | False positive rate |
| Rule Detection Recall | ≥90% | Rule-based alert accuracy |
| Regulatory Mapping Accuracy | ≥85% | Clause reference accuracy |
| LLM Output Validity Rate | ≥95% | Valid LLM assessments |
| LLM Reasoning Quality | Manual | Needs human evaluation |
| False Positive Identification | ≥80% | FP detection rate on benign |
| End-to-End Latency P95 | ≤300s | Processing speed |
| Chatbot Response Latency | ≤10s | Chatbot response time |
| Chatbot Accuracy | ≥85% | Chatbot answer correctness |

**Usage:**
```bash
# Run evaluation with default paths
python evaluation/run_evaluation.py \
  --url http://localhost:8000 \
  --token <JWT>

# Custom scenario/results directories
python evaluation/run_evaluation.py \
  --url https://saia.prod.example.com \
  --token <JWT> \
  --scenarios /data/eval/scenarios \
  --results /data/eval/results

# Local testing
python evaluation/run_evaluation.py \
  --url http://localhost:8000 \
  --token dev_token_123
```

**Output:**
```
[1/50] Processing EVAL-IAM-001.json
  Uploading 1010 events...
  Events accepted: 1010
  Waiting for alerts...
  Alerts generated: 2
...
Computing Metrics
ML Detection Recall: 72.5% (target: 70%)
ML Detection Precision: 81.2% (target: 80%)
Rule Detection Recall: 91.5% (target: 90%)
LLM Output Validity: 96.3% (target: 95%)
FP Identification: 82.1% (target: 80%)
E2E Latency P95: 245.3s (target: 300s)

Report saved to evaluation/results/evaluation_report.md
Results saved to evaluation/results/evaluation_results.json
```

**Generated Report (Markdown):**
```markdown
# SAIA V4 Evaluation Report

Generated: 2024-01-15T10:45:30+00:00

## Executive Summary

Evaluated 50 scenarios across 4 domains.
Test framework: 30 violations, 10 benign, 5 cold-start, 5 edge-case

## Performance Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| ML Detection Recall | 72.5% | 70% | ✓ Pass |
| ML Detection Precision | 81.2% | 80% | ✓ Pass |
...

## Recommendations

- LLM reasoning quality: Requires manual evaluation by security experts
- Consider retraining ML models if recall drops below 65%
```

## Directory Structure

```
/capstone
├── scripts/
│   ├── log_generator.py          # Synthetic log generator
│   ├── train_isolation_forest.py # ML model training
│   └── export_feedback.py        # Feedback export
│
├── evaluation/
│   ├── generate_scenarios.py     # Scenario generation
│   ├── run_evaluation.py         # Evaluation execution
│   ├── scenarios/                # Generated scenario JSON files
│   │   ├── EVAL-IAM-001.json
│   │   ├── EVAL-IAM-002.json
│   │   └── ...
│   └── results/                  # Evaluation results
│       ├── evaluation_report.md
│       └── evaluation_results.json
│
└── backend/
    └── ml_models/
        ├── isolation_forest_iam.joblib
        ├── isolation_forest_network.joblib
        ├── isolation_forest_application.joblib
        ├── isolation_forest_cloud.joblib
        └── training_report.json
```

## Feature Engineering

All scripts use the same 25 ML features for consistency:

**Temporal Features (1-6):**
- Hour of day (0-23)
- Day of week (0-6)
- Is business hours (Saudi Sun-Thu 7-18)
- Is weekend (Fri-Sat)
- Minutes since last event
- Events in last hour

**Behavioral Features (7-14):**
- Unique resources in last hour
- Unique actions in last hour
- Failed action ratio in last hour
- Privilege level (0-1)
- Is new resource
- Is new action
- Deviation from hourly baseline
- Deviation from daily baseline

**Contextual Features (15-20):**
- Source IP is known
- Source country is usual
- Asset criticality
- Principal risk score
- Concurrent sessions
- Is sensitive resource

**Aggregate Features (21-25):**
- Entity event volume z-score
- Entity error rate z-score
- Entity resource diversity z-score
- Entity privilege escalation rate
- Cross-entity correlation score

## Error Handling

All scripts include:
- Comprehensive try-except blocks
- Graceful error recovery
- Detailed logging of failures
- Fallback mechanisms (e.g., synthetic data if DB unavailable)
- Input validation with helpful error messages

## Prerequisites

Required Python packages (from `requirements.txt`):
```
httpx==0.28.1          # HTTP client for API calls
asyncpg==0.30.0        # PostgreSQL async driver
pydantic==2.10.3       # Data validation
scikit-learn==1.6.0    # ML models
joblib==1.4.2          # Model serialization
pandas==2.2.3          # Data analysis
numpy==1.26.4          # Numerical computing
sqlalchemy==2.0.x      # ORM (async support)
```

## Running the Complete Workflow

1. **Generate scenarios:**
   ```bash
   python evaluation/generate_scenarios.py
   # Creates 50 JSON files in evaluation/scenarios/
   ```

2. **Generate synthetic logs (optional, for testing):**
   ```bash
   python scripts/log_generator.py \
     --url http://localhost:8000 \
     --token <JWT> \
     --duration 600 \
     --min-events 20 \
     --max-events 50
   # Runs for 10 minutes, sending batches every 5 seconds
   ```

3. **Train ML models:**
   ```bash
   python scripts/train_isolation_forest.py --synthetic-only
   # Creates models in backend/ml_models/
   ```

4. **Run evaluation:**
   ```bash
   python evaluation/run_evaluation.py \
     --url http://localhost:8000 \
     --token <JWT>
   # Executes all 50 scenarios and generates report
   ```

5. **Export feedback for analysis:**
   ```bash
   python scripts/export_feedback.py --output feedback_data.csv
   # Creates CSV with all verdicted alerts
   ```

## Performance Targets

The evaluation framework is designed to meet these targets:

- **ML Model Accuracy:** 70%+ recall, 80%+ precision
- **Rule Engine:** 90%+ detection on violations
- **LLM Quality:** 95%+ valid outputs, proper reasoning
- **False Positive Handling:** 80%+ identification rate
- **Latency:** <5 minutes end-to-end, <10 seconds chatbot response
- **Compliance:** 85%+ accurate clause mapping

## Customization

### Adding Custom Scenarios

Edit `evaluation/generate_scenarios.py`:

```python
# Add custom scenario type
if scenario_type == "custom_attack":
    event = {
        "timestamp": ...,
        "principal": "target_user",
        "action": "custom_action",
        # ... custom fields
    }
```

### Adjusting Thresholds

Edit metric targets in `evaluation/run_evaluation.py`:

```python
METRICS_TARGETS = {
    "ml_detection_recall": 0.75,  # Increase from 0.70
    "false_positive_identification": 0.85,  # Increase from 0.80
    # ...
}
```

### Training Parameters

Edit `scripts/train_isolation_forest.py`:

```python
TRAINING_PARAMS = {
    "n_estimators": 300,  # Increase from 200
    "max_features": 0.9,  # Increase from 0.8
}

DOMAIN_CONTAMINATION = {
    "IAM": 0.10,  # Adjust contamination rates
    # ...
}
```

## Production Deployment

### Database Setup
- All scripts support async PostgreSQL connections
- Automatic fallback to synthetic data if DB unavailable
- Connection pooling with configurable pool size (default 20)

### API Integration
- Scripts use standard HTTP/REST with Bearer token auth
- Rate limiting aware (60 events/minute by default)
- Configurable timeouts and retries

### Monitoring
- All scripts log to stdout with timestamps
- Integration with standard Python logging
- Progress indicators for long-running tasks

### Security
- JWT tokens passed via CLI arguments (not hardcoded)
- Database credentials from environment/config
- No sensitive data in logs (event counts only)

## Troubleshooting

**Database connection errors:**
```bash
# Use synthetic data mode
python scripts/train_isolation_forest.py --synthetic-only
```

**API connection errors:**
```bash
# Check URL format (no trailing slash)
# Verify token validity
# Check network connectivity
```

**High latency in evaluation:**
```bash
# Increase timeout in run_evaluation.py
# Check server load
# Reduce scenario batch size
```

---

Created for SAIA V4 - Security Analysis and Investigation Assistant
