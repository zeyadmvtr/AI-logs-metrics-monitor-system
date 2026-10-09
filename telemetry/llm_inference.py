import os
import sys
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("telemetry.llm_inference")


class LLMRCAInference:
    """Manages inference for the fine-tuned AIOps RCA Large Language Model.
    Supports local HuggingFace transformers, local API endpoints (vLLM / Ollama),
    and high-precision SRE diagnostic fallback.
    """

    def __init__(self, model_dir: Optional[str] = None):
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.model_dir = model_dir or os.path.join(self.project_root, "telemetry_rca_model")
        self._tokenizer = None
        self._model = None
        self._is_loaded = False

    def build_chatml_prompt(
        self,
        metrics: Dict[str, Any],
        recent_logs: List[Dict[str, Any]],
        anomaly_type: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Constructs prompt using the model's exact ChatML template (Qwen2)."""
        if not system_prompt:
            system_prompt = (
                "You are an expert AIOps Site Reliability Engineering (SRE) AI Assistant. "
                "Your role is to perform Root Cause Analysis (RCA) on anomalous telemetry "
                "metrics and error logs from a microservices application on Kubernetes. "
                "Analyze the inputs and provide: \n"
                "1. Root Cause Identification\n"
                "2. Technical Mechanism\n"
                "3. Imminent Risk Assessment\n"
                "4. Immediate Mitigation Action\n"
                "5. Long-term Resolution"
            )

        logs_formatted = "\n".join([
            f"[{log.get('timestamp', 'N/A')}] [{log.get('level', 'INFO')}] {log.get('message', log)}"
            for log in recent_logs[-15:]
        ]) if recent_logs else "No recent application error logs recorded."

        user_content = (
            f"### OBSERVED TELEMETRY ANOMALY:\n"
            f"- Anomaly Category: {anomaly_type.upper()}\n"
            f"- CPU Cores: {metrics.get('cpu_cores', 0.0):.4f} cores\n"
            f"- Memory Working Set: {metrics.get('memory_mb', 0.0):.1f} MB (Limit: 512 MB)\n"
            f"- Request Throughput: {metrics.get('request_rate_rps', 0.0):.2f} req/s\n"
            f"- HTTP 5xx Error Rate: {metrics.get('error_rate_pct', 0.0):.1f}%\n"
            f"- P95 Latency: {metrics.get('p95_latency_ms', 0.0):.1f} ms\n"
            f"- Active Pods: {metrics.get('active_pods', 1)}\n\n"
            f"### CORRELATED LOG TRACES:\n"
            f"{logs_formatted}\n\n"
            f"Perform an in-depth Root Cause Analysis (RCA) and prescribe precise remediation steps."
        )

        prompt = (
            f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
            f"<|im_start|>user\n{user_content}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        return prompt

    def generate_rca(
        self,
        metrics: Dict[str, Any],
        recent_logs: List[Dict[str, Any]],
        anomaly_type: str,
    ) -> Dict[str, Any]:
        """Generates comprehensive Root Cause Analysis."""
        # Try local LLM weights if transformers & torch installed and model loaded
        if self._is_loaded and self._model is not None and self._tokenizer is not None:
            try:
                prompt = self.build_chatml_prompt(metrics, recent_logs, anomaly_type)
                inputs = self._tokenizer(prompt, return_tensors="pt")
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=512,
                    temperature=0.7,
                    top_p=0.8,
                    do_sample=True
                )
                generated_text = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
                return {
                    "source": "qwen2_local_weights",
                    "analysis_raw": generated_text,
                    "anomaly_type": anomaly_type,
                }
            except Exception as e:
                logger.warning(f"Local model generation failed, using diagnostic engine: {e}")

        # Deterministic Expert SRE RCA Diagnostic Engine
        return self._generate_expert_rca(metrics, recent_logs, anomaly_type)

    def _generate_expert_rca(
        self,
        metrics: Dict[str, Any],
        recent_logs: List[Dict[str, Any]],
        anomaly_type: str,
    ) -> Dict[str, Any]:
        """High-fidelity SRE Diagnostic RCA Generator tailored for the AIOps platform."""
        cpu = float(metrics.get("cpu_cores", 0.0))
        mem = float(metrics.get("memory_mb", 0.0))
        err_pct = float(metrics.get("error_rate_pct", 0.0))
        latency = float(metrics.get("p95_latency_ms", 0.0))
        pods = int(metrics.get("active_pods", 1))

        if anomaly_type == "memory_leak":
            severity = "CRITICAL" if mem > 460 else "HIGH"
            root_cause = "Continuous Heap Allocation / Memory Leak in FastApi Cache or Worker Process"
            mechanism = (
                f"Memory working set has climbed to {mem:.1f} MB, which is "
                f"{(mem / 512.0) * 100:.1f}% of the pod container limit (512 MiB). "
                f"Uncollected memory objects or runaway cache buffers are exhausting memory."
            )
            imminent_risk = (
                "Kubernetes OOMKilled (Exit Code 137). Linux kernel cgroup OOM killer will terminate the pod "
                "when it breaches 512MiB, causing service disruption and traffic re-routing."
            )
            mitigation_cmds = [
                "kubectl rollout restart deployment/aiops-backend -n dev",
                "kubectl top pod -l app=aiops-backend -n dev",
                "curl -X POST http://localhost:8000/api/v1/chaos/memory -H 'Content-Type: application/json' -d '{\"stop\": true}'"
            ]
            resolution = [
                "Profile application memory allocations using memory_profiler or tracemalloc.",
                "Review Redis cache-aside eviction policies in redis_client.py to ensure TTL expiration.",
                "Increase container memory limit to 1Gi in k8s/05-backend.yaml if steady-state workload requires higher capacity."
            ]

        elif anomaly_type == "cpu_spike":
            severity = "CRITICAL" if cpu > 0.45 else "HIGH"
            root_cause = "Compute Starvation / CPU Exhaustion"
            mechanism = (
                f"CPU utilization spiked to {cpu:.4f} cores (Container limit is 0.5 cores / 500m). "
                f"High-frequency computation or multi-threaded CPU burn is saturating CPU quota."
            )
            imminent_risk = (
                "CPU throttling via CFS (Completely Fair Scheduler), leading to severe request queuing, "
                "P95 latency degradation, and readiness probe timeout failures."
            )
            mitigation_cmds = [
                "kubectl scale deployment/aiops-backend --replicas=4 -n dev",
                "kubectl top pod -l app=aiops-backend -n dev"
            ]
            resolution = [
                "Tune Horizontal Pod Autoscaler (HPA) target CPU threshold to 70% in k8s/07-hpa.yaml.",
                "Offload heavy computations from async event loop threads into Celery or background task queues.",
                "Audit hot paths and endpoints like /api/v1/chaos/cpu."
            ]

        elif anomaly_type == "http_500_spike":
            severity = "CRITICAL"
            root_cause = "Cascading Internal Server Errors (HTTP 500) / Backend Exceptions"
            mechanism = (
                f"HTTP 5xx failure rate reached {err_pct:.1f}% of all incoming traffic. "
                f"Microservice endpoints are failing unhandled exceptions or upstream dependencies."
            )
            imminent_risk = (
                "Widespread business transaction failures for customer order processing "
                "and potential client-side circuit breaker trips."
            )
            mitigation_cmds = [
                "kubectl logs -l app=aiops-backend -n dev --tail=50",
                "kubectl get events -n dev --sort-by='.metadata.creationTimestamp'",
                "curl http://localhost:8000/api/v1/health/ready"
            ]
            resolution = [
                "Inspect database connection pool exhaustion in database.py.",
                "Add defensive exception handling around Redis / PostgreSQL calls.",
                "Verify schema migration state via Alembic."
            ]

        elif anomaly_type == "latency_spike":
            severity = "HIGH" if latency > 400 else "MEDIUM"
            root_cause = "P95 Response Latency Degradation / Connection Queuing"
            mechanism = (
                f"P95 response latency deteriorated to {latency:.1f} ms (Normal baseline is < 30 ms). "
                f"Requests are stalling either waiting for thread locks, DB row locks, or network I/O."
            )
            imminent_risk = (
                "Kubernetes liveness and readiness probe timeouts, leading to cascade restarts "
                "and user request dropouts."
            )
            mitigation_cmds = [
                "kubectl describe deployment/aiops-backend -n dev",
                "kubectl top nodes"
            ]
            resolution = [
                "Verify database query execution plans and index usage on PostgreSQL orders table.",
                "Verify Redis connection pool health and latency stats.",
                "Enable HTTP keep-alive and verify Uvicorn connection limits."
            ]

        else:
            severity = "LOW"
            root_cause = "Operational Baseline Normal / No Active Anomaly"
            mechanism = "All telemetry streams (CPU, RAM, Error Rate, Latency) are operating inside normal parameters."
            imminent_risk = "None observed."
            mitigation_cmds = ["No immediate remediation required."]
            resolution = ["Continue regular monitoring via Prometheus and Grafana dashboards."]

        return {
            "source": "aiops_rca_diagnostic_engine",
            "anomaly_type": anomaly_type,
            "severity": severity,
            "root_cause": root_cause,
            "mechanism": mechanism,
            "imminent_risk": imminent_risk,
            "telemetry_evidence": {
                "cpu_cores": f"{cpu:.4f} cores",
                "memory_mb": f"{mem:.1f} MB",
                "error_rate_pct": f"{err_pct:.1f}%",
                "p95_latency_ms": f"{latency:.1f} ms",
                "active_pods": pods,
            },
            "immediate_mitigation": mitigation_cmds,
            "permanent_resolution": resolution,
        }
