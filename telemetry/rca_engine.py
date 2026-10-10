import os
import sys
import time
import json
import uuid
import datetime
import logging
import argparse
from typing import Dict, Any, List, Optional
import pandas as pd
from tabulate import tabulate

# Configure Windows UTF-8 stdout
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telemetry.config import get_telemetry_settings
from telemetry.anomaly_detector import AnomalyDetector, AnomalyReport
from telemetry.llm_inference import LLMRCAInference
from telemetry.email_dispatcher import EmailAlertDispatcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("telemetry.rca")


class RCAEngine:
    """End-to-end Root Cause Analysis Engine for AIOps.
    Correlates Prometheus metrics, application logs, and ML anomaly signals
    with LLM-powered incident diagnosis and automated remediation planning.
    """

    def __init__(self, model_dir: Optional[str] = None):
        self.settings = get_telemetry_settings()
        self.reports_dir = os.path.join(self.settings.SNAPSHOT_DIR, "rca_reports")
        os.makedirs(self.reports_dir, exist_ok=True)

        self.detector = AnomalyDetector()
        self.llm = LLMRCAInference(model_dir=model_dir)
        self.email_dispatcher = EmailAlertDispatcher()

        # Train baseline if historical dataset exists
        dataset_path = os.path.join(self.settings.SNAPSHOT_DIR, "telemetry_dataset.csv")
        if os.path.exists(dataset_path):
            try:
                df = pd.read_csv(dataset_path)
                normal_df = df[df["anomaly_type"] == "normal"] if "anomaly_type" in df.columns else df
                self.detector.fit_baseline(normal_df)
            except Exception as e:
                logger.warning(f"Could not load baseline dataset for detector: {e}")

    def diagnose(
        self,
        current_metrics: Dict[str, Any],
        recent_logs: Optional[List[Dict[str, Any]]] = None,
        history_df: Optional[pd.DataFrame] = None,
        persist_incident: bool = True,
        dispatch_email: bool = True,
    ) -> Dict[str, Any]:
        """Performs full anomaly evaluation and LLM RCA diagnosis."""
        recent_logs = recent_logs or []

        # 1. Anomaly detection
        anomaly_report = self.detector.evaluate_vector(current_metrics, history_df)

        incident_id = f"INC-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
        timestamp_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # 2. LLM RCA Generation
        llm_output = self.llm.generate_rca(
            metrics=current_metrics,
            recent_logs=recent_logs,
            anomaly_type=anomaly_report.anomaly_type,
        )

        # 3. Construct unified RCA Document
        report = {
            "incident_id": incident_id,
            "timestamp": timestamp_iso,
            "is_anomaly": anomaly_report.is_anomaly,
            "anomaly_type": anomaly_report.anomaly_type,
            "confidence": anomaly_report.confidence,
            "severity": llm_output.get("severity", "LOW"),
            "root_cause": llm_output.get("root_cause", "Operational Baseline Normal"),
            "mechanism": llm_output.get("mechanism", ""),
            "imminent_risk": llm_output.get("imminent_risk", ""),
            "telemetry_evidence": {
                "current_vector": current_metrics,
                "deviations": anomaly_report.deviant_metrics,
            },
            "recent_logs_inspected": len(recent_logs),
            "immediate_mitigation": llm_output.get("immediate_mitigation", []),
            "permanent_resolution": llm_output.get("permanent_resolution", []),
            "prompt_used": llm_output.get("prompt_used", ""),
            "model_info": llm_output.get("model_info", {}),
            "engine_source": llm_output.get("source", "rca_engine"),
        }

        # 4. Save to disk and dispatch email alert if anomaly flagged and requested
        if anomaly_report.is_anomaly and persist_incident:
            self.save_report(report)
            if dispatch_email:
                self.email_dispatcher.send_rca_alert(report)

        return report

    def save_report(self, report: Dict[str, Any]) -> str:
        """Saves RCA report as JSON and Markdown."""
        inc_id = report["incident_id"]
        json_path = os.path.join(self.reports_dir, f"{inc_id}.json")
        md_path = os.path.join(self.reports_dir, f"{inc_id}.md")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        md_content = self.render_markdown_report(report)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        logger.info(f"Saved RCA report: {json_path} and {md_path}")
        return json_path

    def render_markdown_report(self, report: Dict[str, Any]) -> str:
        """Renders an executive incident Markdown RCA document."""
        sev_badge = {
            "CRITICAL": "CRITICAL",
            "HIGH": "HIGH",
            "MEDIUM": "MEDIUM",
            "LOW": "INFO",
        }.get(report.get("severity", "LOW"), "INFO")

        cur = report["telemetry_evidence"]["current_vector"]
        devs = report["telemetry_evidence"]["deviations"]

        dev_lines = []
        for k, v in devs.items():
            dev_lines.append(f"- **{k}**: observed `{v.get('observed')}` vs normal baseline `{v.get('baseline')}` ({v.get('severity')})")
        dev_text = "\n".join(dev_lines) if dev_lines else "No specific threshold breaches."

        mitigations = "\n".join([f"{i+1}. `{cmd}`" for i, cmd in enumerate(report["immediate_mitigation"])])
        resolutions = "\n".join([f"- {res}" for res in report["permanent_resolution"]])

        return f"""# AIOps Incident Root Cause Analysis (RCA)

**Incident ID:** `{report['incident_id']}`  
**Timestamp:** `{report['timestamp']}`  
**Severity:** **{sev_badge}**  
**Anomaly Classification:** `{report['anomaly_type'].upper()}` (Confidence: {report['confidence']*100:.0f}%)  
**Diagnosis Engine:** `{report['engine_source']}`  

---

## 1. Executive Summary & Root Cause
**Identified Root Cause:**  
> **{report['root_cause']}**

**Technical Mechanism:**  
{report['mechanism']}

**Imminent Production Risk:**  
{report['imminent_risk']}

---

## 2. Telemetry Evidence & Telemetry Matrix
| Telemetry Metric | Observed Value | Limit / Baseline | State |
|---|---|---|---|
| CPU Utilization | `{cur.get('cpu_cores', 0.0):.4f}` cores | `0.5000` limit / `0.1000` req | {'CRITICAL' if cur.get('cpu_cores', 0) > 0.45 else 'OK'} |
| Memory Working Set | `{cur.get('memory_mb', 0.0):.1f}` MB | `512.0` limit / `128.0` req | {'CRITICAL' if cur.get('memory_mb', 0) > 460 else 'OK'} |
| HTTP Throughput | `{cur.get('request_rate_rps', 0.0):.2f}` RPS | Normal traffic | OK |
| HTTP 5xx Error Rate | `{cur.get('error_rate_pct', 0.0):.1f}` % | `< 2.0%` normal | {'ALERT' if cur.get('error_rate_pct', 0) > 2.0 else 'OK'} |
| P95 Latency | `{cur.get('p95_latency_ms', 0.0):.1f}` ms | `< 100` ms normal | {'DEGRADED' if cur.get('p95_latency_ms', 0) > 250 else 'OK'} |
| Active Pods | `{cur.get('active_pods', 1)}` | 2 replicas target | OK |

### Specific Anomaly Deviations:
{dev_text}

---

## 3. Prescribed Immediate Mitigation Commands
Execute the following automated runbook steps to restore cluster stability:
{mitigations}

---

## 4. Permanent Architectural Resolution
{resolutions}
"""


def main():
    parser = argparse.ArgumentParser(description="AIOps Root Cause Analysis (RCA) Engine")
    parser.add_argument("--eval", action="store_true", help="Run RCA diagnosis on current data/telemetry_latest.json snapshot")
    parser.add_argument("--anomaly", choices=["memory_leak", "cpu_spike", "http_500_spike", "latency_spike", "normal"], help="Simulate a specific anomaly scenario for evaluation")
    args = parser.parse_args()

    engine = RCAEngine()

    if args.anomaly:
        samples = {
            "memory_leak": {
                "cpu_cores": 0.185,
                "memory_mb": 485.4,
                "request_rate_rps": 12.4,
                "error_rate_pct": 0.0,
                "p95_latency_ms": 65.2,
                "active_pods": 2
            },
            "cpu_spike": {
                "cpu_cores": 0.485,
                "memory_mb": 142.1,
                "request_rate_rps": 35.8,
                "error_rate_pct": 0.0,
                "p95_latency_ms": 280.0,
                "active_pods": 2
            },
            "http_500_spike": {
                "cpu_cores": 0.125,
                "memory_mb": 150.0,
                "request_rate_rps": 14.2,
                "error_rate_pct": 42.5,
                "p95_latency_ms": 45.0,
                "active_pods": 2
            },
            "latency_spike": {
                "cpu_cores": 0.110,
                "memory_mb": 160.0,
                "request_rate_rps": 8.0,
                "error_rate_pct": 1.2,
                "p95_latency_ms": 520.0,
                "active_pods": 2
            },
            "normal": {
                "cpu_cores": 0.095,
                "memory_mb": 118.0,
                "request_rate_rps": 10.5,
                "error_rate_pct": 0.0,
                "p95_latency_ms": 22.0,
                "active_pods": 2
            }
        }
        test_metrics = samples[args.anomaly]
        print(f"\n=======================================================")
        print(f"RUNNING RCA DIAGNOSTIC SIMULATION: {args.anomaly.upper()}")
        print(f"=======================================================")
        report = engine.diagnose(test_metrics, recent_logs=[])
        print(engine.render_markdown_report(report))
        return

    # Default: evaluate latest snapshot
    snapshot_path = os.path.join(engine.settings.SNAPSHOT_DIR, "telemetry_latest.json")
    if os.path.exists(snapshot_path):
        with open(snapshot_path, "r", encoding="utf-8") as f:
            snap = json.load(f)
        metrics = snap.get("latest_metrics") or {
            "cpu_cores": 0.0, "memory_mb": 0.0, "request_rate_rps": 0.0,
            "error_rate_pct": 0.0, "p95_latency_ms": 0.0, "active_pods": 1
        }
        logs = snap.get("recent_logs", [])
        report = engine.diagnose(metrics, recent_logs=logs)
        print(f"\n=======================================================")
        print(f"EVALUATING LATEST TELEMETRY SNAPSHOT")
        print(f"=======================================================")
        print(engine.render_markdown_report(report))
    else:
        print("No telemetry_latest.json snapshot found. Run telemetry/ingestion_worker.py first.")


if __name__ == "__main__":
    main()
