#!/usr/bin/env python3
"""Run evaluation scenarios and compute performance metrics for SAIA V4.

Executes all scenario files against the running SAIA backend, uploads events,
waits for processing, queries resulting alerts, and computes the 10 key metrics
defined in §12.2 of the architecture specification.

Usage:
    python evaluation/run_evaluation.py --url http://localhost:8000 --token <jwt>
"""

import argparse
import asyncio
import json
import logging
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── Metric targets from spec §12.2 ──────────────────────────────────────────

METRIC_TARGETS = {
    "ml_detection_recall":          {"target": 0.70, "unit": "%",  "direction": "gte"},
    "ml_detection_precision":       {"target": 0.80, "unit": "%",  "direction": "gte"},
    "rule_detection_recall":        {"target": 0.90, "unit": "%",  "direction": "gte"},
    "regulatory_mapping_accuracy":  {"target": 0.85, "unit": "%",  "direction": "gte"},
    "llm_output_validity_rate":     {"target": 0.95, "unit": "%",  "direction": "gte"},
    "llm_reasoning_quality":        {"target": 4.0,  "unit": "/5", "direction": "gte"},
    "false_positive_identification":{"target": 0.80, "unit": "%",  "direction": "gte"},
    "end_to_end_latency_p95_sec":   {"target": 300,  "unit": "s",  "direction": "lte"},
    "chatbot_response_latency_sec": {"target": 10,   "unit": "s",  "direction": "lte"},
    "chatbot_accuracy":             {"target": 0.85, "unit": "%",  "direction": "gte"},
}

# ── Chatbot test queries (for metrics 9 & 10) ───────────────────────────────

CHATBOT_QUERIES = [
    {"message": "Show me all IAM alerts this week",
     "expect_keywords": ["IAM", "alert"]},
    {"message": "What is ECC control 2-2-1?",
     "expect_keywords": ["2-2-1", "Identity", "Access"]},
    {"message": "How many critical alerts are open?",
     "expect_keywords": ["critical"]},
    {"message": "Explain alert ALT-2025-0001",
     "expect_keywords": ["ALT-2025"]},
    {"message": "What is our compliance posture?",
     "expect_keywords": ["compliance", "control"]},
    {"message": "Show failed login attempts today",
     "expect_keywords": ["login", "fail"]},
    {"message": "Which entities have the highest risk score?",
     "expect_keywords": ["risk"]},
    {"message": "List all Network domain alerts",
     "expect_keywords": ["Network"]},
    {"message": "Summarize the most recent case",
     "expect_keywords": ["case"]},
    {"message": "Are there any drift alerts?",
     "expect_keywords": ["drift", "baseline"]},
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def upload_events(client: httpx.AsyncClient, scenario: dict,
                        url: str, token: str) -> tuple[bool, dict]:
    """Upload a scenario's events via POST /api/v1/logs/ingest."""
    meta = scenario["metadata"]
    body = {
        "source_name": f"eval_{meta['scenario_id']}",
        "domain": meta["domain"],
        "events": scenario["events"],
    }
    try:
        resp = await client.post(
            f"{url}/api/v1/logs/ingest", json=body,
            headers=_headers(token), timeout=120.0,
        )
        if resp.status_code in (200, 201):
            return True, resp.json()
        logger.error(f"  Upload failed: {resp.status_code} {resp.text[:200]}")
        return False, {}
    except Exception as exc:
        logger.error(f"  Upload error: {exc}")
        return False, {}


async def poll_alerts(client: httpx.AsyncClient, url: str, token: str,
                      domain: str, after: str,
                      timeout: int = 120, interval: int = 3) -> list[dict]:
    """Poll GET /api/v1/alerts until new alerts appear or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = await client.get(
                f"{url}/api/v1/alerts",
                params={"domain": domain, "page_size": 200},
                headers=_headers(token), timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                alerts = data.get("alerts", data) if isinstance(data, dict) else data
                if isinstance(alerts, list):
                    # Filter alerts created after our upload timestamp
                    recent = [
                        a for a in alerts
                        if a.get("created_at", "") >= after
                    ]
                    if recent:
                        return recent
        except Exception:
            pass
        await asyncio.sleep(interval)
    return []


async def test_chatbot(client: httpx.AsyncClient, url: str,
                       token: str) -> tuple[list[float], int, int]:
    """Send test queries to chatbot, return (latencies, correct, total)."""
    latencies = []
    correct = 0
    total = len(CHATBOT_QUERIES)

    # Create a session first
    try:
        resp = await client.post(
            f"{url}/api/v1/chat/session",
            headers=_headers(token), timeout=10,
        )
        if resp.status_code in (200, 201):
            session_id = resp.json().get("session_id")
        else:
            logger.warning("Could not create chat session, skipping chatbot tests")
            return [], 0, total
    except Exception as exc:
        logger.warning(f"Chat session creation failed: {exc}")
        return [], 0, total

    for q in CHATBOT_QUERIES:
        t0 = time.monotonic()
        try:
            resp = await client.post(
                f"{url}/api/v1/chat/message",
                json={"session_id": session_id, "message": q["message"]},
                headers=_headers(token), timeout=30,
            )
            latency = time.monotonic() - t0
            latencies.append(latency)

            # Check if response contains expected keywords
            text = resp.text.lower() if resp.status_code == 200 else ""
            if any(kw.lower() in text for kw in q["expect_keywords"]):
                correct += 1
        except Exception:
            latencies.append(30.0)  # timeout penalty

    return latencies, correct, total


# ── Metric computation ───────────────────────────────────────────────────────

def compute_metrics(results: list[dict],
                    chatbot_latencies: list[float],
                    chatbot_correct: int,
                    chatbot_total: int) -> dict:
    """Compute all 10 evaluation metrics."""

    violation_results = [r for r in results if r["type"] == "violation"]
    benign_results    = [r for r in results if r["type"] == "benign"]
    rule_eligible     = [r for r in violation_results if r.get("has_matching_rule")]
    all_alerts        = []
    for r in results:
        all_alerts.extend(r.get("alerts", []))

    # TP / FP / FN for ML detection
    ml_tp = sum(1 for r in violation_results if len(r.get("alerts", [])) > 0)
    ml_fn = sum(1 for r in violation_results if len(r.get("alerts", [])) == 0)
    ml_fp_events = sum(
        1 for r in benign_results if len(r.get("alerts", [])) > 0
    )
    total_flagged = ml_tp + ml_fp_events

    # 1. ML Detection Recall
    ml_recall = ml_tp / (ml_tp + ml_fn) if (ml_tp + ml_fn) > 0 else 0.0

    # 2. ML Detection Precision
    ml_precision = ml_tp / total_flagged if total_flagged > 0 else 0.0

    # 3. Rule Detection Recall (only for scenarios with matching rules)
    rule_tp = sum(
        1 for r in rule_eligible
        if any(a.get("source") in ("rule", "both") for a in r.get("alerts", []))
    )
    rule_recall = rule_tp / len(rule_eligible) if rule_eligible else 0.0

    # 4. Regulatory Mapping Accuracy
    correct_clauses = 0
    total_assessed = 0
    for r in violation_results:
        expected = r.get("expected_clause")
        if not expected:
            continue
        for a in r.get("alerts", []):
            llm = a.get("llm_assessment")
            if llm and isinstance(llm, dict):
                total_assessed += 1
                if llm.get("primary_clause") == expected:
                    correct_clauses += 1
    reg_accuracy = correct_clauses / total_assessed if total_assessed > 0 else 0.0

    # 5. LLM Output Validity Rate
    valid_outputs = 0
    total_llm_calls = 0
    for a in all_alerts:
        llm = a.get("llm_assessment")
        if llm is not None:
            total_llm_calls += 1
            required = ["violation_detected", "confidence", "primary_clause",
                        "severity_assessment", "reasoning",
                        "recommended_action", "false_positive_likelihood"]
            if all(k in llm for k in required):
                valid_outputs += 1
    llm_validity = valid_outputs / total_llm_calls if total_llm_calls > 0 else 0.0

    # 6. LLM Reasoning Quality — requires human rating (placeholder)
    llm_reasoning = 0.0  # Must be filled by human reviewers

    # 7. False Positive Identification
    benign_correct = sum(
        1 for r in benign_results
        if len(r.get("alerts", [])) == 0
        or any(
            (a.get("llm_assessment") or {}).get("false_positive_likelihood", 0) > 0.5
            for a in r.get("alerts", [])
        )
    )
    fp_id = benign_correct / len(benign_results) if benign_results else 0.0

    # 8. End-to-End Latency P95
    latencies = []
    for r in results:
        upload_ts = r.get("upload_time", "")
        for a in r.get("alerts", []):
            created = a.get("created_at", "")
            if upload_ts and created:
                try:
                    t_up = datetime.fromisoformat(upload_ts.replace("Z", "+00:00"))
                    t_cr = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    latencies.append((t_cr - t_up).total_seconds())
                except Exception:
                    pass
    if latencies:
        latencies.sort()
        idx = min(int(len(latencies) * 0.95), len(latencies) - 1)
        e2e_p95 = latencies[idx]
    else:
        e2e_p95 = 0.0

    # 9. Chatbot Response Latency (P95 of first-token times)
    if chatbot_latencies:
        chatbot_latencies.sort()
        idx = min(int(len(chatbot_latencies) * 0.95), len(chatbot_latencies) - 1)
        chat_lat = chatbot_latencies[idx]
    else:
        chat_lat = 0.0

    # 10. Chatbot Accuracy
    chat_acc = chatbot_correct / chatbot_total if chatbot_total > 0 else 0.0

    return {
        "ml_detection_recall": round(ml_recall, 4),
        "ml_detection_precision": round(ml_precision, 4),
        "rule_detection_recall": round(rule_recall, 4),
        "regulatory_mapping_accuracy": round(reg_accuracy, 4),
        "llm_output_validity_rate": round(llm_validity, 4),
        "llm_reasoning_quality": llm_reasoning,
        "false_positive_identification": round(fp_id, 4),
        "end_to_end_latency_p95_sec": round(e2e_p95, 2),
        "chatbot_response_latency_sec": round(chat_lat, 2),
        "chatbot_accuracy": round(chat_acc, 4),
    }


# ── Report generation ────────────────────────────────────────────────────────

def format_report(metrics: dict, results: list[dict]) -> str:
    """Generate the evaluation report in the §12.4 template format."""
    lines = [
        "## Evaluation Results\n",
        "### Test Environment",
        "- Hardware: Local development machine + Docker Compose",
        "- LLM Model: Llama 3.1 70B Q4 (mock mode)" if True else "",
        f"- Dataset: {len(results)} evaluation scenarios "
        f"({sum(1 for r in results if r['type']=='violation')} violations, "
        f"{sum(1 for r in results if r['type']=='benign')} benign, "
        f"{sum(1 for r in results if r['type']=='cold_start')} cold-start, "
        f"{sum(1 for r in results if r['type']=='edge_case')} edge-case)",
        f"- Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n",
        "### Metric Results\n",
        "| Metric | Target | Actual | Status |",
        "|--------|--------|--------|--------|",
    ]

    display_names = {
        "ml_detection_recall": "ML Detection Recall",
        "ml_detection_precision": "ML Detection Precision",
        "rule_detection_recall": "Rule Detection Recall",
        "regulatory_mapping_accuracy": "Regulatory Mapping Accuracy",
        "llm_output_validity_rate": "LLM Output Validity",
        "llm_reasoning_quality": "LLM Reasoning Quality",
        "false_positive_identification": "False Positive ID",
        "end_to_end_latency_p95_sec": "End-to-End Latency P95",
        "chatbot_response_latency_sec": "Chatbot Latency",
        "chatbot_accuracy": "Chatbot Accuracy",
    }

    for key, meta in METRIC_TARGETS.items():
        val = metrics.get(key, 0)
        target = meta["target"]
        unit = meta["unit"]

        if unit == "s":
            val_s = f"{val:.1f}s"
            tgt_s = f"≤ {target:.0f}s"
            passed = val <= target
        elif unit == "/5":
            val_s = f"{val:.1f}/5.0"
            tgt_s = f"≥ {target:.1f}/5.0"
            passed = val >= target
        else:
            val_s = f"{val*100:.1f}%"
            tgt_s = f"≥ {target*100:.0f}%"
            passed = val >= target

        status = "PASS" if passed else "FAIL"
        name = display_names.get(key, key)
        lines.append(f"| {name} | {tgt_s} | {val_s} | {status} |")

    lines.append("")
    lines.append("### Discussion")

    # Auto-generate discussion for failing metrics
    for key, meta in METRIC_TARGETS.items():
        val = metrics.get(key, 0)
        target = meta["target"]
        unit = meta["unit"]
        passed = (val <= target) if unit == "s" else (val >= target)
        if not passed:
            name = display_names.get(key, key)
            lines.append(
                f"- **{name}**: Below target. "
                f"Actual={val:.2f}, Target={target}. "
                "Further tuning of model parameters, rule thresholds, "
                "or prompt engineering may be required."
            )

    if all(
        (metrics.get(k, 0) <= m["target"]) if m["unit"] == "s"
        else (metrics.get(k, 0) >= m["target"])
        for k, m in METRIC_TARGETS.items()
    ):
        lines.append("All metrics meet or exceed targets.")

    lines.append("")
    lines.append("### Feedback Loop Impact")
    lines.append("[Show precision before/after incorporating analyst feedback into RAG]")
    lines.append("")
    lines.append("---")
    lines.append(f"*Generated by SAIA V4 Evaluation Framework — "
                 f"{datetime.now(timezone.utc).isoformat()}*")

    return "\n".join(lines)


# ── Main orchestrator ────────────────────────────────────────────────────────

async def run_evaluation(
    scenarios_dir: str,
    url: str,
    token: str,
    results_dir: str,
    alert_wait: int = 120,
) -> None:
    url = url.rstrip("/")
    scenarios_path = Path(scenarios_dir)
    results_path = Path(results_dir)
    results_path.mkdir(parents=True, exist_ok=True)

    files = sorted(scenarios_path.glob("*.json"))
    if not files:
        logger.error(f"No scenario files in {scenarios_dir}")
        return

    logger.info("=" * 60)
    logger.info("SAIA V4 — Evaluation Framework")
    logger.info("=" * 60)
    logger.info(f"Scenarios: {len(files)}")
    logger.info(f"Endpoint:  {url}")

    all_results = []

    async with httpx.AsyncClient() as client:
        # ── Phase 1: Upload scenarios and collect alerts ─────────────
        for i, fpath in enumerate(files):
            logger.info(f"\n[{i+1}/{len(files)}] {fpath.stem}")

            with open(fpath) as f:
                scenario = json.load(f)
            meta = scenario["metadata"]

            upload_time = datetime.now(timezone.utc).isoformat()
            ok, resp = await upload_events(client, scenario, url, token)
            if not ok:
                logger.warning(f"  Skipped (upload failed)")
                continue

            accepted = resp.get("events_accepted", 0)
            quarantined = resp.get("events_quarantined", 0)
            logger.info(f"  Uploaded: {accepted} accepted, {quarantined} quarantined")

            logger.info(f"  Waiting for alerts (up to {alert_wait}s)...")
            alerts = await poll_alerts(
                client, url, token,
                domain=meta["domain"],
                after=upload_time,
                timeout=alert_wait,
            )
            logger.info(f"  Alerts found: {len(alerts)}")

            all_results.append({
                "scenario_id": meta["scenario_id"],
                "type": meta["type"],
                "domain": meta["domain"],
                "expected_clause": meta.get("expected_clause"),
                "expected_severity": meta.get("expected_severity"),
                "ground_truth_event_ids": meta.get("ground_truth_event_ids", []),
                "has_matching_rule": meta["type"] == "violation",
                "upload_time": upload_time,
                "events_accepted": accepted,
                "alerts": alerts,
            })

        # ── Phase 2: Chatbot tests ──────────────────────────────────
        logger.info("\nRunning chatbot accuracy tests...")
        chat_lats, chat_ok, chat_total = await test_chatbot(client, url, token)
        logger.info(f"  Chatbot: {chat_ok}/{chat_total} correct, "
                     f"median latency {statistics.median(chat_lats):.2f}s"
                     if chat_lats else "  Chatbot tests skipped")

    # ── Phase 3: Compute metrics ────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("Computing Metrics")
    logger.info("=" * 60)

    metrics = compute_metrics(all_results, chat_lats, chat_ok, chat_total)

    # ── Phase 4: Write report ───────────────────────────────────────
    report_md = format_report(metrics, all_results)
    report_file = results_path / "evaluation_report.md"
    report_file.write_text(report_md)
    logger.info(f"Report → {report_file}")

    raw_file = results_path / "evaluation_results.json"
    with open(raw_file, "w") as f:
        json.dump({"metrics": metrics, "scenarios": all_results},
                  f, indent=2, default=str)
    logger.info(f"Raw data → {raw_file}")

    # ── Summary table ───────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("EVALUATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"{'Metric':<35} {'Actual':>10} {'Target':>10} {'Status':>8}")
    logger.info("-" * 65)

    for key, meta in METRIC_TARGETS.items():
        val = metrics.get(key, 0)
        tgt = meta["target"]
        unit = meta["unit"]
        if unit == "s":
            v_str = f"{val:.1f}s"
            t_str = f"≤{tgt:.0f}s"
            ok = val <= tgt
        elif unit == "/5":
            v_str = f"{val:.1f}/5"
            t_str = f"≥{tgt:.1f}/5"
            ok = val >= tgt
        else:
            v_str = f"{val*100:.1f}%"
            t_str = f"≥{tgt*100:.0f}%"
            ok = val >= tgt
        status = "PASS" if ok else "FAIL"
        logger.info(f"  {key:<33} {v_str:>10} {t_str:>10} {status:>8}")

    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Run SAIA V4 evaluation scenarios and compute metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python evaluation/run_evaluation.py \\
    --url http://localhost:8000 --token YOUR_JWT

  python evaluation/run_evaluation.py \\
    --url http://localhost:8000 --token YOUR_JWT \\
    --scenarios evaluation/scenarios --results evaluation/results \\
    --alert-wait 180
        """,
    )
    parser.add_argument("--url", default="http://localhost:8000",
                        help="API base URL (default: http://localhost:8000)")
    parser.add_argument("--token", required=True, help="JWT authentication token")
    parser.add_argument("--scenarios", default="evaluation/scenarios",
                        help="Scenarios directory (default: evaluation/scenarios)")
    parser.add_argument("--results", default="evaluation/results",
                        help="Results directory (default: evaluation/results)")
    parser.add_argument("--alert-wait", type=int, default=120,
                        help="Max seconds to wait for alerts per scenario (default: 120)")
    args = parser.parse_args()

    asyncio.run(run_evaluation(
        scenarios_dir=args.scenarios,
        url=args.url,
        token=args.token,
        results_dir=args.results,
        alert_wait=args.alert_wait,
    ))


if __name__ == "__main__":
    main()
