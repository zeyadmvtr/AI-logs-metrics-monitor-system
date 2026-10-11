import os
import sys
import time
import smtplib
import logging
import argparse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, List, Optional

# Configure Windows UTF-8 stdout
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telemetry.config import get_telemetry_settings

logger = logging.getLogger("telemetry.alerts.email")


class EmailAlertDispatcher:
    """Automated Email Alert Dispatcher for AIOps Incidents & Root Cause Analysis.
    Dispatches rich HTML alert summaries and kubectl runbooks with anti-spam throttling.
    """

    def __init__(self):
        self.settings = get_telemetry_settings()
        self._last_sent_timestamps: Dict[str, float] = {}

    def is_throttled(self, anomaly_type: str) -> bool:
        """Checks if a given anomaly type is in cooldown to prevent inbox flooding."""
        now = time.time()
        last_sent = self._last_sent_timestamps.get(anomaly_type, 0.0)
        cooldown = self.settings.ALERT_COOLDOWN_SECONDS
        return (now - last_sent) < cooldown

    def build_html_email(self, report: Dict[str, Any]) -> str:
        """Generates a responsive, modern SRE incident alert email."""
        incident_id = report.get("incident_id", "INC-UNKNOWN")
        sev = report.get("severity", "HIGH")
        anomaly_type = report.get("anomaly_type", "UNCLASSIFIED").upper()
        root_cause = report.get("root_cause", "Anomaly Detected")
        mechanism = report.get("mechanism", "Underlying technical mechanism not available.")
        imminent_risk = report.get("imminent_risk", "Potential service degradation.")
        
        cur = report.get("telemetry_evidence", {}).get("current_vector", {})
        cpu = cur.get("cpu_cores", 0.0)
        mem = cur.get("memory_mb", 0.0)
        err_pct = cur.get("error_rate_pct", 0.0)
        latency = cur.get("p95_latency_ms", 0.0)
        pods = cur.get("active_pods", 1)

        mitigations = report.get("immediate_mitigation", [])
        mitigation_html = "".join([f"<li style='margin-bottom: 6px;'><code>{cmd}</code></li>" for cmd in mitigations])

        badge_color = "#dc2626" if sev == "CRITICAL" else "#ea580c" if sev == "HIGH" else "#2563eb"

        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>AIOps Incident Alert: {incident_id}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #1e293b;">
  <div style="max-width: 650px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
    
    <!-- Header -->
    <div style="background-color: #0f172a; padding: 20px 24px; color: #ffffff;">
      <div style="font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #94a3b8; margin-bottom: 4px;">AIOps Autonomous Incident Notification</div>
      <h1 style="margin: 0; font-size: 20px; font-weight: 600; color: #ffffff;">Incident Alert: {incident_id}</h1>
    </div>

    <!-- Alert Banner -->
    <div style="background-color: {badge_color}; color: #ffffff; padding: 12px 24px; font-size: 14px; font-weight: 600; display: flex; align-items: center;">
      <span>[SEVERITY: {sev}] Anomaly Signature: {anomaly_type}</span>
    </div>

    <!-- Content -->
    <div style="padding: 24px;">
      
      <!-- Root Cause Section -->
      <div style="background-color: #f1f5f9; border-left: 4px solid {badge_color}; padding: 14px 16px; border-radius: 4px; margin-bottom: 20px;">
        <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: #64748b; margin-bottom: 4px;">Identified Root Cause (Qwen2 LLM)</div>
        <div style="font-size: 16px; font-weight: 700; color: #0f172a; margin-bottom: 8px;">{root_cause}</div>
        <div style="font-size: 13px; line-height: 1.5; color: #334155;">{mechanism}</div>
      </div>

      <!-- Risk Warning -->
      <div style="margin-bottom: 20px; padding: 12px 16px; background-color: #fff1f2; border: 1px solid #fecdd3; border-radius: 6px; color: #9f1239; font-size: 13px;">
        <strong>⚠️ Imminent Risk:</strong> {imminent_risk}
      </div>

      <!-- Telemetry Metrics Table -->
      <h3 style="font-size: 14px; text-transform: uppercase; letter-spacing: 0.05em; color: #475569; margin: 20px 0 10px 0;">Observed Telemetry Vitals</h3>
      <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 24px;">
        <thead>
          <tr style="background-color: #f8fafc; border-bottom: 2px solid #e2e8f0; text-align: left;">
            <th style="padding: 8px 12px; color: #64748b;">Dimension</th>
            <th style="padding: 8px 12px; color: #64748b;">Observed Value</th>
            <th style="padding: 8px 12px; color: #64748b;">Target Limit / Baseline</th>
          </tr>
        </thead>
        <tbody>
          <tr style="border-bottom: 1px solid #e2e8f0;">
            <td style="padding: 8px 12px; font-weight: 600;">CPU Utilization</td>
            <td style="padding: 8px 12px;">{cpu:.4f} cores</td>
            <td style="padding: 8px 12px; color: #64748b;">0.5000 limit (500m)</td>
          </tr>
          <tr style="border-bottom: 1px solid #e2e8f0;">
            <td style="padding: 8px 12px; font-weight: 600;">Memory Working Set</td>
            <td style="padding: 8px 12px; color: {'#dc2626' if mem > 400 else '#1e293b'}; font-weight: {'700' if mem > 400 else '400'};">{mem:.1f} MB</td>
            <td style="padding: 8px 12px; color: #64748b;">512.0 MB limit (512Mi)</td>
          </tr>
          <tr style="border-bottom: 1px solid #e2e8f0;">
            <td style="padding: 8px 12px; font-weight: 600;">HTTP 5xx Errors</td>
            <td style="padding: 8px 12px; color: {'#dc2626' if err_pct > 2 else '#1e293b'};">{err_pct:.1f}%</td>
            <td style="padding: 8px 12px; color: #64748b;">&lt; 2.0% normal</td>
          </tr>
          <tr style="border-bottom: 1px solid #e2e8f0;">
            <td style="padding: 8px 12px; font-weight: 600;">P95 Latency</td>
            <td style="padding: 8px 12px;">{latency:.1f} ms</td>
            <td style="padding: 8px 12px; color: #64748b;">&lt; 100 ms normal</td>
          </tr>
          <tr>
            <td style="padding: 8px 12px; font-weight: 600;">Active Backend Pods</td>
            <td style="padding: 8px 12px;">{pods} Replicas</td>
            <td style="padding: 8px 12px; color: #64748b;">2 Replicas</td>
          </tr>
        </tbody>
      </table>

      <!-- Runbook Section -->
      <div style="background-color: #0f172a; color: #f8fafc; padding: 16px 20px; border-radius: 6px; margin-bottom: 20px;">
        <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: #38bdf8; margin-bottom: 8px;">Prescribed Runbook Mitigation Commands</div>
        <ul style="margin: 0; padding-left: 20px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 13px; color: #a5f3fc;">
          {mitigation_html}
        </ul>
      </div>

      <div style="font-size: 12px; color: #94a3b8; text-align: center; margin-top: 24px; border-top: 1px solid #e2e8f0; padding-top: 16px;">
        AIOps Automated SRE Platform • Generated at {report.get('timestamp', 'N/A')}
      </div>

    </div>
  </div>
</body>
</html>
"""

    def build_text_email(self, report: Dict[str, Any]) -> str:
        """Generates a plain-text fallback alert."""
        incident_id = report.get("incident_id", "INC-UNKNOWN")
        sev = report.get("severity", "HIGH")
        anomaly_type = report.get("anomaly_type", "UNCLASSIFIED").upper()
        root_cause = report.get("root_cause", "Anomaly Detected")
        mechanism = report.get("mechanism", "")
        imminent_risk = report.get("imminent_risk", "")
        mitigations = "\n".join([f"  $ {cmd}" for cmd in report.get("immediate_mitigation", [])])

        return f"""[AIOPS SRE ALERT] {sev} - {anomaly_type}
Incident ID: {incident_id}
Timestamp:   {report.get('timestamp', 'N/A')}

ROOT CAUSE:
{root_cause}

TECHNICAL MECHANISM:
{mechanism}

IMMINENT RISK:
{imminent_risk}

PRESCRIBED REMEDIATION RUNBOOK:
{mitigations}

Report saved to data/rca_reports/{incident_id}.md
"""

    def send_rca_alert(
        self,
        report: Dict[str, Any],
        force: bool = False,
        recipient: Optional[str] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
    ) -> bool:
        """Dispatches email notification for an active RCA report."""
        if not report.get("is_anomaly"):
            return False

        anomaly_type = report.get("anomaly_type", "unclassified")
        if not force and self.is_throttled(anomaly_type):
            logger.info(f"Email alert for {anomaly_type} suppressed due to active cooldown.")
            return False

        incident_id = report.get("incident_id", "INC-UNKNOWN")
        sev = report.get("severity", "HIGH")
        subject = f"[{sev}] AIOps Incident Alert: {anomaly_type.upper()} ({incident_id})"

        html_body = self.build_html_email(report)
        text_body = self.build_text_email(report)

        # Save email snapshot artifact for local audit
        email_preview_path = os.path.join(self.settings.SNAPSHOT_DIR, "rca_reports", f"email_{incident_id}.html")
        try:
            with open(email_preview_path, "w", encoding="utf-8") as f:
                f.write(html_body)
            logger.info(f"Saved email preview to {email_preview_path}")
        except Exception:
            pass

        # Target recipient priority: parameter > settings > default
        target_recipients = []
        if recipient and recipient.strip():
            target_recipients = [r.strip() for r in recipient.split(",") if r.strip()]
        elif self.settings.ALERT_RECIPIENTS.strip():
            target_recipients = [r.strip() for r in self.settings.ALERT_RECIPIENTS.split(",") if r.strip()]
        else:
            target_recipients = ["zeyadmohammed983@gmail.com"]

        active_smtp_user = smtp_user or self.settings.SMTP_USER
        active_smtp_pass = smtp_password or self.settings.SMTP_PASSWORD

        # Check if live email dispatch is enabled and configured with credentials
        if not active_smtp_user or not active_smtp_pass:
            logger.info(
                f"[SAVED-PREVIEW] Email alert prepared for {incident_id} -> {target_recipients} | "
                f"Subject: '{subject}' | Provide Gmail App Password to send live over SMTP."
            )
            self._last_sent_timestamps[anomaly_type] = time.time()
            self.last_dispatch_status = {
                "success": True,
                "mode": "preview_saved",
                "recipients": target_recipients,
                "preview_path": email_preview_path,
                "message": f"Alert formatted and saved for {', '.join(target_recipients)}"
            }
            return True

        # Live SMTP Dispatch
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.settings.SMTP_FROM or active_smtp_user
            msg["To"] = ", ".join(target_recipients)

            msg.attach(MIMEText(text_body, "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            logger.info(f"Connecting to SMTP server {self.settings.SMTP_HOST}:{self.settings.SMTP_PORT} for {target_recipients}...")
            with smtplib.SMTP(self.settings.SMTP_HOST, self.settings.SMTP_PORT, timeout=12) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(active_smtp_user, active_smtp_pass)
                server.sendmail(msg["From"], target_recipients, msg.as_string())

            logger.info(f"Live email alert successfully sent to {target_recipients} for {incident_id}!")
            self._last_sent_timestamps[anomaly_type] = time.time()
            self.last_dispatch_status = {
                "success": True,
                "mode": "live_smtp",
                "recipients": target_recipients,
                "preview_path": email_preview_path,
                "message": f"Live email successfully delivered to {', '.join(target_recipients)} via SMTP"
            }
            return True

        except Exception as exc:
            logger.error(f"Failed to dispatch live email alert for {incident_id}: {exc}", exc_info=True)
            self.last_dispatch_status = {
                "success": False,
                "mode": "error",
                "recipients": target_recipients,
                "preview_path": email_preview_path,
                "message": f"SMTP Error: {exc}"
            }
            return False


def main():
    parser = argparse.ArgumentParser(description="AIOps Email Alert Server & Dispatcher")
    parser.add_argument("--test", action="store_true", help="Send a simulated test incident email")
    parser.add_argument("--anomaly", default="memory_leak", choices=["memory_leak", "cpu_spike", "http_500_spike", "latency_spike"], help="Anomaly archetype to simulate")
    parser.add_argument("--recipient", type=str, help="Override recipient email address")
    args = parser.parse_args()

    dispatcher = EmailAlertDispatcher()
    if args.recipient:
        dispatcher.settings.ALERT_RECIPIENTS = args.recipient

    from telemetry.rca_engine import RCAEngine
    engine = RCAEngine()

    sample_metrics = {
        "cpu_cores": 0.18,
        "memory_mb": 490.0,
        "request_rate_rps": 12.0,
        "error_rate_pct": 0.0,
        "p95_latency_ms": 50.0,
        "active_pods": 2
    }
    report = engine.diagnose(sample_metrics, recent_logs=[])
    print(f"\nDispatching sample {args.anomaly.upper()} alert email...")
    success = dispatcher.send_rca_alert(report, force=True)
    if success:
        print(f"SUCCESS: Alert processed. Check data/rca_reports/email_{report['incident_id']}.html for the rendered email.")
    else:
        print("FAILED to send alert email.")


if __name__ == "__main__":
    main()
