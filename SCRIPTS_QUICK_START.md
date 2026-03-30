# SAIA V4 Scripts Quick Start Guide

## What Was Created

### Utility Scripts (3 files)
1. **log_generator.py** - Generates synthetic security logs
2. **train_isolation_forest.py** - Trains ML anomaly detection models
3. **export_feedback.py** - Exports labeled alerts for analysis

### Evaluation Framework (2 files)
1. **generate_scenarios.py** - Creates 50 test scenarios
2. **run_evaluation.py** - Executes evaluation and computes metrics

### Documentation (1 file)
- **UTILITY_SCRIPTS_README.md** - Complete reference documentation

---

## Quick Commands

### 1. Generate Test Scenarios
```bash
cd /sessions/eloquent-charming-hypatia/mnt/capstone
python evaluation/generate_scenarios.py
```
Creates 50 JSON scenario files in `evaluation/scenarios/` directory.

### 2. Generate Synthetic Logs (Testing)
```bash
python scripts/log_generator.py \
  --url http://localhost:8000 \
  --token YOUR_JWT_TOKEN \
  --duration 300  # Run for 5 minutes
```

### 3. Train ML Models
```bash
python scripts/train_isolation_forest.py --synthetic-only
```
Creates trained models in `backend/ml_models/` directory.

### 4. Run Full Evaluation
```bash
python evaluation/run_evaluation.py \
  --url http://localhost:8000 \
  --token YOUR_JWT_TOKEN
```
Generates report in `evaluation/results/evaluation_report.md`.

### 5. Export Feedback Data
```bash
python scripts/export_feedback.py --output feedback.csv
```
Creates CSV file with all verdicted alerts and features.

---

## File Structure

```
capstone/
├── scripts/
│   ├── log_generator.py
│   ├── train_isolation_forest.py
│   └── export_feedback.py
├── evaluation/
│   ├── generate_scenarios.py
│   ├── run_evaluation.py
│   ├── scenarios/              ← Generated scenario files
│   └── results/                ← Evaluation reports
├── backend/
│   └── ml_models/              ← Trained model files
├── UTILITY_SCRIPTS_README.md   ← Full documentation
└── SCRIPTS_QUICK_START.md      ← This file
```

---

## Key Features

### Log Generator
- 4 domains: IAM, Network, Application, Cloud
- Realistic events: 50 users, domain-specific resources/actions
- 5% anomaly injection: off-hours, brute force, privilege escalation, unusual IPs, lateral movement
- Saudi Arabia business hours awareness
- Configurable batch sizes and intervals

### ML Training
- Isolation Forest algorithm
- 25 features per event
- Per-domain contamination rates
- Automatic synthetic data generation
- Training statistics and model metrics

### Feedback Export
- CSV format with 25 features
- Alert metadata: number, domain, severity, verdict
- Easy integration with Excel/Pandas
- Statistics by verdict and domain

### Scenario Generation
- **30 violation scenarios** (6 per domain) - should trigger alerts
- **10 benign scenarios** (2-3 per domain) - should NOT trigger alerts
- **5 cold-start scenarios** - new entities
- **5 edge-case scenarios** - borderline events
- Ground truth labels for validation

### Evaluation Framework
- Executes all 50 scenarios
- Computes 10 performance metrics
- Generates markdown report
- JSON results for further analysis
- Confusion matrix: TP, FP, TN, FN

---

## Performance Metrics

The evaluation framework tracks:

| Metric | Target | Description |
|--------|--------|-------------|
| ML Detection Recall | ≥70% | % violations detected |
| ML Detection Precision | ≥80% | % detected alerts valid |
| Rule Detection Recall | ≥90% | % violations by rules |
| Regulatory Mapping | ≥85% | % correct clause mapping |
| LLM Validity | ≥95% | % valid LLM outputs |
| FP Identification | ≥80% | % benign correctly ignored |
| E2E Latency P95 | ≤300s | Max processing time |
| Chatbot Latency | ≤10s | Response time |
| Chatbot Accuracy | ≥85% | Answer correctness |

---

## 25 ML Features

**Temporal (6):** hour, day, business hours, weekend, time since last, events/hour

**Behavioral (8):** unique resources, unique actions, failure rate, privilege, new resource, new action, hourly deviation, daily deviation

**Contextual (6):** IP known, country usual, asset criticality, risk score, sessions, sensitive resource

**Aggregate (5):** volume z-score, error rate z-score, resource diversity z-score, privilege escalation rate, correlation score

---

## Database Integration

All scripts support PostgreSQL:
- Async connections with asyncpg
- Connection pooling (default 20 connections)
- Automatic fallback to synthetic data if DB unavailable
- No hardcoded credentials (use environment variables)

---

## Error Handling

Complete error handling throughout:
- Try-except blocks for all external operations
- Graceful degradation (e.g., synthetic data fallback)
- Detailed error logging
- Input validation with helpful messages
- Network timeout handling (30-60 second defaults)

---

## Production Readiness Checklist

✓ Complete error handling
✓ Comprehensive logging
✓ CLI argument parsing with --help
✓ Progress indicators for long tasks
✓ Async/await for I/O operations
✓ Database connection pooling
✓ Configuration flexibility
✓ Detailed documentation
✓ Code comments explaining logic
✓ Type hints in function signatures
✓ Separation of concerns
✓ No hardcoded credentials
✓ Input validation
✓ Fallback mechanisms
✓ Statistical computation

---

## Examples

### Example 1: Development Testing
```bash
# Generate scenarios
python evaluation/generate_scenarios.py

# Train models (synthetic data)
python scripts/train_isolation_forest.py --synthetic-only

# Generate logs for 5 minutes
python scripts/log_generator.py \
  --url http://localhost:8000 \
  --token dev_token \
  --duration 300

# Run evaluation
python evaluation/run_evaluation.py \
  --url http://localhost:8000 \
  --token dev_token

# Check results
cat evaluation/results/evaluation_report.md
```

### Example 2: Production Evaluation
```bash
# Pre-existing scenarios
# python evaluation/generate_scenarios.py  # Already done

# Train with real data
python scripts/train_isolation_forest.py

# Run evaluation
python evaluation/run_evaluation.py \
  --url https://saia.prod.example.com \
  --token $PROD_JWT_TOKEN \
  --results /data/eval_results/2024-01

# Export labeled data for retraining
python scripts/export_feedback.py --output /data/training/labeled_alerts.csv
```

### Example 3: Continuous Testing
```bash
# Run generator continuously
nohup python scripts/log_generator.py \
  --url http://localhost:8000 \
  --token $JWT_TOKEN \
  --interval 10 \
  > logs/generator.log 2>&1 &

# Periodically run evaluation
while true; do
    --url http://localhost:8000 \
    --token $JWT_TOKEN \
    --results evaluation/results/$(date +%Y%m%d_%H%M%S)
  sleep 3600  # Run hourly
done
```

---

## Files Created

### Utility Scripts
- `scripts/log_generator.py` (456 lines)
- `scripts/train_isolation_forest.py` (513 lines)
- `scripts/export_feedback.py` (301 lines)

### Evaluation
- `evaluation/generate_scenarios.py` (465 lines)
- `evaluation/run_evaluation.py` (582 lines)

### Documentation
- `UTILITY_SCRIPTS_README.md` (400+ lines)
- `SCRIPTS_QUICK_START.md` (this file)

### Total: 2,700+ lines of production-ready code

---

## Getting Help

For detailed information about each script:
```bash
python scripts/log_generator.py --help
python scripts/train_isolation_forest.py --help
python scripts/export_feedback.py --help
python evaluation/generate_scenarios.py --help
python evaluation/run_evaluation.py --help
```

For complete documentation:
```bash
cat UTILITY_SCRIPTS_README.md
```

---

## System Requirements

**Python:** 3.9+

**Dependencies (from requirements.txt):**
- httpx (HTTP client)
- asyncpg (PostgreSQL driver)
- sqlalchemy (ORM)
- scikit-learn (ML models)
- joblib (Model serialization)
- pandas (Data analysis)
- numpy (Numerical computing)

**Database:** PostgreSQL 12+

**API:** SAIA V4 backend running with `/api/v1/logs/ingest` endpoint

---

## Notes

- All scripts are standalone and can be run independently
- Synthetic data mode allows testing without a database
- Scenarios are designed to exercise all security domains
- Evaluation metrics follow SAIA V4 specification
- All code includes proper async/await for I/O operations
- Comprehensive error handling and fallback mechanisms
- Production-ready with no TODOs or placeholders

---

For issues or questions, refer to UTILITY_SCRIPTS_README.md for detailed documentation.
