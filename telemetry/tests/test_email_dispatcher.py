import os
import pytest
from telemetry.email_dispatcher import EmailAlertDispatcher


@pytest.fixture
def dispatcher():
    return EmailAlertDispatcher()


def test_build_email_templates(dispatcher):
    sample_report = {
        "incident_id": "INC-TEST-001",
        "severity": "CRITICAL",
        "anomaly_type": "memory_leak",
        "root_cause": "Continuous Heap Allocation in Cache",
        "mechanism": "Working set reached 480MB",
        "imminent_risk": "OOMKilled 137",
        "telemetry_evidence": {
            "current_vector": {
                "cpu_cores": 0.20,
                "memory_mb": 480.0,
                "error_rate_pct": 0.0,
                "p95_latency_ms": 40.0,
                "active_pods": 2
            }
        },
        "immediate_mitigation": ["kubectl rollout restart deployment/aiops-backend -n dev"],
        "timestamp": "2026-10-09T20:00:00Z",
        "is_anomaly": True
    }

    html = dispatcher.build_html_email(sample_report)
    text = dispatcher.build_text_email(sample_report)

    assert "INC-TEST-001" in html
    assert "MEMORY_LEAK" in html
    assert "CRITICAL" in html
    assert "kubectl rollout restart" in html

    assert "INC-TEST-001" in text
    assert "ROOT CAUSE" in text


def test_throttling_cooldown(dispatcher):
    dispatcher._last_sent_timestamps["memory_leak"] = 0.0
    assert not dispatcher.is_throttled("memory_leak")

    # Mark as sent now
    import time
    dispatcher._last_sent_timestamps["memory_leak"] = time.time()
    assert dispatcher.is_throttled("memory_leak")


def test_dry_run_dispatch(dispatcher):
    sample_report = {
        "incident_id": "INC-TEST-002",
        "severity": "HIGH",
        "anomaly_type": "cpu_spike",
        "root_cause": "CPU Exhaustion",
        "mechanism": "Spike to 490m",
        "imminent_risk": "CFS throttling",
        "telemetry_evidence": {
            "current_vector": {
                "cpu_cores": 0.49,
                "memory_mb": 140.0,
                "error_rate_pct": 0.0,
                "p95_latency_ms": 25.0,
                "active_pods": 2
            }
        },
        "immediate_mitigation": ["kubectl scale deployment/aiops-backend --replicas=4 -n dev"],
        "is_anomaly": True
    }

    # In dry-run mode (default without credentials)
    res = dispatcher.send_rca_alert(sample_report, force=True)
    assert res is True
    # Preview html file should exist
    preview_file = os.path.join(dispatcher.settings.SNAPSHOT_DIR, "rca_reports", "email_INC-TEST-002.html")
    assert os.path.exists(preview_file)
