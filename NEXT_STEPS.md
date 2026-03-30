# SAIA V4 — Next Steps & Deployment Guide

## What You Have Right Now

A fully-built SAIA V4 codebase that runs in **mock mode** — no real LLM needed.
Everything works: ingestion → ML detection → rule engine → alert aggregation → dashboard → chatbot.

---

## Step 1 — First-Time Setup (Do This Once)

### Prerequisites
| Tool | Version | Notes |
|------|---------|-------|
| Docker Desktop | Latest | postgres + qdrant containers |
| Python | 3.10+ | 3.12 preferred |
| pip | Latest | `pip install --upgrade pip` |

### Start the system

```bash
cd /path/to/capstone

# Make the script executable
chmod +x start.sh

# First-time full start: installs deps, starts Docker, applies schema, seeds DB, trains models
./start.sh --all
```

This will:
1. Copy `.env.example` → `.env`
2. Install Python packages from `requirements.txt`
3. Start PostgreSQL 16 + Qdrant via Docker Compose
4. Apply `sql/001_schema.sql`, `002_indexes.sql`, `003_seed_data.sql`
5. Seed NCA controls, CSM patterns, rules, assets into the DB
6. Train 4 Isolation Forest models (saved to `backend/ml_models/`)
7. Launch the FastAPI server on **http://localhost:8000**

**Login:** `admin` / `admin123`

---

## Step 2 — Daily Usage

```bash
./start.sh          # Start Docker services + API server (no re-seeding)
./start.sh --stop   # Stop all containers
```

**Generate synthetic log traffic** (separate terminal):
```bash
python3 scripts/log_generator.py
# Sends batches every 5 s with a 5% anomaly ratio — watch alerts appear live
```

---

## Step 3 — Connect a Real LLM (When Ready)

The system runs in **LLM_MOCK_MODE=true** by default. To use a real Llama 3.1 70B:

### Option A — Saudi Cloud GPU (recommended for production)
1. Provision a GPU VM (e.g., on Saudi Aramco Cloud or AWS Riyadh region)
2. Install vLLM: `pip install vllm`
3. Start the server:
   ```bash
   python -m vllm.entrypoints.openai.api_server \
     --model meta-llama/Llama-3.1-70B-Instruct \
     --quantization awq \
     --port 8001
   ```
4. Edit `.env`:
   ```
   LLM_MOCK_MODE=false
   LLM_BASE_URL=http://<your-gpu-server-ip>:8001/v1
   ```
5. Restart the API server.

### Option B — Local (for testing only, needs ~40GB RAM)
```bash
pip install vllm
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-70B-Instruct \
  --quantization awq \
  --port 8001
```

The three LLM services (enrichment, chatbot, narrative) will automatically switch to real responses.

---

## Step 4 — Load the NCA ECC 2:2024 Document

The RAG system is seeded with **43 synthetic NCA controls** for development.
To replace these with the real NCA ECC 2:2024 PDF:

1. Obtain the official NCA ECC 2:2024 PDF from https://nca.gov.sa
2. Place it at `seed/nca_ecc_2024.pdf`
3. Run the PDF ingestion script (you'll need to add a simple extraction step):
   ```bash
   # Extract text from PDF (requires pypdf)
   pip install pypdf
   python3 - <<'EOF'
   from pypdf import PdfReader
   import json

   reader = PdfReader("seed/nca_ecc_2024.pdf")
   controls = []
   for i, page in enumerate(reader.pages):
       text = page.extract_text()
       # Parse out clause IDs (2-X-Y format) and text — customise as needed
       controls.append({"page": i+1, "text": text})

   with open("seed/nca_controls_real.json", "w") as f:
       json.dump(controls, f, ensure_ascii=False, indent=2)
   print(f"Extracted {len(controls)} pages")
   EOF

   # Then seed into Qdrant
   python3 seed/seed_nca_controls.py --source seed/nca_controls_real.json
   ```

---

## Step 5 — Run the Evaluation Framework

```bash
# Generate 50 test scenarios
python3 evaluation/generate_scenarios.py

# Run full evaluation (10 metrics, 3 phases)
python3 evaluation/run_evaluation.py

# Results saved to evaluation/results/
```

**Metrics evaluated:** Detection Rate, False Positive Rate, MTTD, Precision, Recall, F1, Chatbot Accuracy, Evidence Quality, Enrichment Latency, Throughput.

---

## Step 6 — Export Feedback for Model Improvement

```bash
# Export TP/FP verdicts to CSV for analysis
python3 scripts/export_feedback.py --output feedback_export.csv
```

This pulls analyst verdicts from the `alerts` table and formats them for review or retraining.

---

## Architecture Cheat Sheet

```
Browser → FastAPI (port 8000)
            ├── /api/v1/auth        JWT login/refresh
            ├── /api/v1/logs        Ingest + search log events
            ├── /api/v1/alerts      Alert CRUD + verdict feedback
            ├── /api/v1/rules       Rule management + dry-run
            ├── /api/v1/cases       Case management
            ├── /api/v1/chat        Chatbot (SSE streaming)
            ├── /api/v1/dashboard   KPIs, trend charts
            ├── /api/v1/reports     Evidence pack generation (202 + WS notify)
            └── /ws                 WebSocket (real-time alert push)

FastAPI → PostgreSQL 16 (port 5432)  — all transactional data
        → Qdrant       (port 6333)  — NCA control embeddings + confirmed alerts
        → vLLM         (port 8001)  — Llama 3.1 70B  [mock by default]
```

---

## Credentials & Secrets

| Setting | Default | Change Before Production |
|---------|---------|--------------------------|
| `JWT_SECRET` | `change-this-...` | **Yes — generate a random 64-char string** |
| `DB_PASSWORD` | `saia_password` | Yes |
| Admin user | `admin / admin123` | Yes — update via `/api/v1/auth/change-password` |

Generate a secure JWT secret:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `docker: command not found` | Install Docker Desktop |
| PostgreSQL won't start | Check port 5432 isn't in use: `lsof -i :5432` |
| Qdrant won't start | Check port 6333: `lsof -i :6333` |
| `ModuleNotFoundError: fastapi` | Run `pip install -r requirements.txt` |
| ML models not found warning | Run `python3 scripts/train_isolation_forest.py` |
| Chatbot returns empty responses | Normal in mock mode — responses are synthetic |
| Rate limit 429 errors | Default: 60 req/min on `/logs/ingest` — adjust `INGEST_RATE_LIMIT` in `.env` |

---

## File Map (Quick Reference)

```
capstone/
├── start.sh                   ← THIS FILE — run me first
├── .env                       ← All secrets and config
├── docker-compose.yml         ← PostgreSQL + Qdrant
├── requirements.txt           ← Python packages
├── sql/                       ← Schema, indexes, seed SQL
├── backend/
│   ├── main.py                ← FastAPI app + startup
│   ├── config.py              ← Settings from .env
│   ├── routers/               ← 8 API routers
│   ├── services/              ← 18 service modules
│   ├── middleware/            ← JWT auth + audit logging
│   ├── models/                ← Pydantic request/response models
│   ├── workers/               ← LLM queue background worker
│   └── ml_models/             ← Trained IF models (after --train)
├── frontend/                  ← 9 HTML pages + JS/CSS
├── seed/                      ← Seed scripts + JSON data
├── scripts/                   ← log_generator, train_IF, export_feedback
└── evaluation/                ← 50 scenarios, 10-metric evaluation
```
