import os
import json
import pytest
import pandas as pd
from telemetry.anomaly_detector import AnomalyDetector
from telemetry.llm_inference import LLMRCAInference
from telemetry.rca_engine import RCAEngine


@pytest.fixture
def rca_engine():
    return RCAEngine()


def test_anomaly_detector_normal(rca_engine):
    normal_vector = {
        "cpu_cores": 0.08,
        "memory_mb": 110.0,
        "request_rate_rps": 10.0,
        "error_rate_pct": 0.0,
        "p95_latency_ms": 18.0,
        "active_pods": 2
    }
    report = rca_engine.detector.evaluate_vector(normal_vector)
    assert not report.is_anomaly
    assert report.anomaly_type == "normal"


def test_anomaly_detector_memory_leak(rca_engine):
    leak_vector = {
        "cpu_cores": 0.12,
        "memory_mb": 490.0,
        "request_rate_rps": 12.0,
        "error_rate_pct": 0.0,
        "p95_latency_ms": 30.0,
        "active_pods": 2
    }
    report = rca_engine.detector.evaluate_vector(leak_vector)
    assert report.is_anomaly
    assert report.anomaly_type == "memory_leak"
    assert "memory_mb" in report.deviant_metrics


def test_anomaly_detector_cpu_spike(rca_engine):
    cpu_vector = {
        "cpu_cores": 0.49,
        "memory_mb": 130.0,
        "request_rate_rps": 25.0,
        "error_rate_pct": 0.0,
        "p95_latency_ms": 40.0,
        "active_pods": 2
    }
    report = rca_engine.detector.evaluate_vector(cpu_vector)
    assert report.is_anomaly
    assert report.anomaly_type == "cpu_spike"


def test_anomaly_detector_http_500_spike(rca_engine):
    err_vector = {
        "cpu_cores": 0.10,
        "memory_mb": 120.0,
        "request_rate_rps": 15.0,
        "error_rate_pct": 25.0,
        "p95_latency_ms": 25.0,
        "active_pods": 2
    }
    report = rca_engine.detector.evaluate_vector(err_vector)
    assert report.is_anomaly
    assert report.anomaly_type == "http_500_spike"


def test_chatml_prompt_builder():
    llm = LLMRCAInference()
    metrics = {"cpu_cores": 0.45, "memory_mb": 500.0, "error_rate_pct": 10.0, "p95_latency_ms": 300.0}
    prompt = llm.build_chatml_prompt(metrics, recent_logs=[], anomaly_type="memory_leak")
    assert "<|im_start|>system" in prompt
    assert "<|im_start|>user" in prompt
    assert "<|im_start|>assistant" in prompt
    assert "MEMORY_LEAK" in prompt


def test_rca_engine_diagnose_and_save(rca_engine):
    leak_vector = {
        "cpu_cores": 0.15,
        "memory_mb": 495.0,
        "request_rate_rps": 12.0,
        "error_rate_pct": 0.0,
        "p95_latency_ms": 35.0,
        "active_pods": 2
    }
    report = rca_engine.diagnose(leak_vector, recent_logs=[{"level": "ERROR", "message": "OOM warning"}])
    assert report["is_anomaly"] is True
    assert report["anomaly_type"] == "memory_leak"
    assert report["severity"] == "CRITICAL"
    assert len(report["immediate_mitigation"]) > 0

    # Verify JSON report file was written
    inc_id = report["incident_id"]
    json_path = os.path.join(rca_engine.reports_dir, f"{inc_id}.json")
    md_path = os.path.join(rca_engine.reports_dir, f"{inc_id}.md")
    assert os.path.exists(json_path)
    assert os.path.exists(md_path)
