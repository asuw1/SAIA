# SAIA — Secure Artificial Intelligence Auditor
**Alfaisal University | SE 495 Capstone Project I**

Supervisor: Dr. Nidal Nasser  
Team: Firas AlWahhabi (230254) · Abdulaziz AlSuwailim (230253) · Rakan AlSaikhan (230270) · Faisal Rassas (230238)

---

## What is SAIA?
An AI-powered compliance auditing platform for Saudi regulated entities.  
Ingests enterprise logs, maps violations to NCA / SAMA / CST / IA regulatory clauses, and produces regulator-ready alerts and reports.

---

## Repo Structure
```
SAIA/
├── frontend/           Static HTML/CSS/JS dashboard (Pair 2)
└── backend/            FastAPI + PostgreSQL API server (Pair 1 + Pair 2)
```

---

## Frontend
Pure HTML/CSS/JS — open `frontend/index.html` in a browser.

**Pages:**
- `index.html` — Dashboard (KPIs, charts, alerts table)
- `login.html` — Authentication
- `pages/alerts.html` — Alert management
- `pages/reports.html` — Compliance report generation
- `pages/rules.html` — Rule creation and management

---

## Backend

### Setup
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # fill in DATABASE_URL and SECRET_KEY
uvicorn main:app --reload
```

API docs auto-generated at: `http://localhost:8000/docs`

### Structure
```
backend/
├── main.py                 FastAPI app entry point
├── config.py               Settings via .env
├── database.py             SQLAlchemy engine + session
├── requirements.txt
├── .env.example
│
├── api/                    Route handlers (one file per feature)
│   ├── auth.py             POST /api/auth/login, register, me
│   ├── ingest.py           POST /api/ingest/upload
│   ├── alerts.py           GET/PATCH /api/alerts/
│   ├── rules.py            GET/POST/PATCH /api/rules/
│   ├── reports.py          GET/POST /api/reports/
│   └── ai.py               GET /api/ai/status, POST /api/ai/train
│
├── models/                 SQLAlchemy ORM models (PostgreSQL)
├── schemas/                Pydantic request/response schemas
├── services/               Business logic (one file per domain)
│   ├── normalization_service.py
│   ├── ingestion_service.py
│   ├── rule_engine.py
│   ├── ai_service.py
│   ├── alert_service.py
│   └── report_service.py
└── core/
    ├── security.py         JWT + bcrypt
    └── dependencies.py     RBAC middleware
```

### Ingestion Pipeline
```
Upload file → parse → normalize → save to DB → rule engine → AI → alerts
```

---

## Regulatory Frameworks
| Code | Authority |
|------|-----------|
| NCA  | National Cybersecurity Authority |
| SAMA | Saudi Arabian Monetary Authority |
| CST  | Communications and Space Technology |
| IA   | Internal Audit |

---

## Canonical Log Format
```json
{
  "timestamp":  "2026-03-11T10:23:45Z",
  "source":     "vpn_server",
  "event_type": "authentication",
  "principal":  "admin",
  "action":     "login_attempt",
  "resource":   "vpn_gateway",
  "result":     "failed",
  "source_ip":  "192.168.1.50",
  "asset_id":   "vpn-01",
  "session_id": "sess-4821",
  "domain":     "IT"
}
```
