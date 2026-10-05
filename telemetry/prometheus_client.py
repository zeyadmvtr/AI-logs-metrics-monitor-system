import time
import logging
from typing import Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from telemetry.config import get_telemetry_settings

logger = logging.getLogger("telemetry.prometheus")


class PrometheusClient:
    """Programmatic client for querying the Prometheus HTTP API."""

    def __init__(self, base_url: Optional[str] = None):
        settings = get_telemetry_settings()
        self.base_url = (base_url or settings.PROMETHEUS_URL).rstrip("/")
        self.timeout = settings.PROMETHEUS_TIMEOUT_SECONDS
        self.namespace = settings.K8S_NAMESPACE
        self.app_name = settings.APP_NAME

        # Configure connection pool with fast fail on connect refused
        self.session = requests.Session()
        retries = Retry(
            total=2,
            connect=0,
            backoff_factor=0.2,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False
        )
        self.session.mount("http://", HTTPAdapter(max_retries=retries))
        self.session.mount("https://", HTTPAdapter(max_retries=retries))


    def is_healthy(self) -> bool:
        """Verifies that the Prometheus server is reachable and ready."""
        try:
            res = self.session.get(f"{self.base_url}/-/ready", timeout=3)
            return res.status_code == 200
        except Exception:
            return False

    def query_instant(self, query: str, time_ts: Optional[float] = None) -> Dict[str, Any]:
        """Executes an instant PromQL query at a specific evaluation timestamp."""
        url = f"{self.base_url}/api/v1/query"
        params = {"query": query}
        if time_ts is not None:
            params["time"] = time_ts

        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "success":
                logger.warning(f"Prometheus query returned non-success: {data}")
                return {}
            return data.get("data", {})
        except Exception as exc:
            logger.error(f"Failed to execute instant query '{query}': {exc}")
            return {}

    def query_range(self, query: str, start_ts: float, end_ts: float, step: str = "15s") -> Dict[str, Any]:
        """Executes a range PromQL query over a time window."""
        url = f"{self.base_url}/api/v1/query_range"
        params = {
            "query": query,
            "start": start_ts,
            "end": end_ts,
            "step": step,
        }

        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "success":
                logger.warning(f"Prometheus range query returned non-success: {data}")
                return {}
            return data.get("data", {})
        except Exception as exc:
            logger.error(f"Failed to execute range query '{query}': {exc}")
            return {}

    def _extract_scalar(self, data: Dict[str, Any], default: float = 0.0) -> float:
        """Helper to extract a single float value from a Prometheus query result."""
        results = data.get("result", [])
        if not results:
            return default
        try:
            # Format: [timestamp, "value_string"]
            return float(results[0].get("value", [0, default])[1])
        except (IndexError, ValueError, TypeError):
            return default

    def get_cpu_usage(self) -> float:
        """Current total CPU cores used across backend pods."""
        query = f'sum(rate(container_cpu_usage_seconds_total{{namespace=~"{self.namespace}|aiops",pod=~"{self.app_name}.*",container="backend"}}[1m])) or sum(rate(container_cpu_usage_seconds_total{{pod=~"{self.app_name}.*"}}[1m])) or vector(0)'
        data = self.query_instant(query)
        return round(self._extract_scalar(data), 4)

    def get_memory_usage_mb(self) -> float:
        """Current total working set memory in Megabytes."""
        query = f'sum(container_memory_working_set_bytes{{namespace=~"{self.namespace}|aiops",pod=~"{self.app_name}.*",container="backend"}}) / (1024*1024) or vector(0)'
        data = self.query_instant(query)
        return round(self._extract_scalar(data), 2)

    def get_http_request_rate(self) -> float:
        """Total HTTP requests per second across all endpoints."""
        query = 'sum(rate(aiops_backend_http_requests_total[1m])) or vector(0)'
        data = self.query_instant(query)
        return round(self._extract_scalar(data), 3)

    def get_error_rate_percentage(self) -> float:
        """Percentage of HTTP responses returning 5xx status codes."""
        query = '(sum(rate(aiops_backend_http_requests_total{status_code=~"5.."}[1m])) / (sum(rate(aiops_backend_http_requests_total[1m])) > 0) * 100) or vector(0)'
        data = self.query_instant(query)
        return round(self._extract_scalar(data), 2)

    def get_p95_latency_ms(self) -> float:
        """95th percentile response latency in milliseconds."""
        query = '(histogram_quantile(0.95, sum(rate(aiops_backend_http_request_duration_seconds_bucket[1m])) by (le)) * 1000) or vector(0)'
        data = self.query_instant(query)
        return round(self._extract_scalar(data), 2)

    def get_active_pods(self) -> int:
        """Number of currently running backend pods."""
        query = f'count(kube_pod_status_phase{{phase="Running", pod=~"{self.app_name}.*"}}) or vector(1)'
        data = self.query_instant(query)
        return int(self._extract_scalar(data, default=1.0))

    def get_current_metrics_vector(self) -> Dict[str, Any]:
        """Gathers a unified snapshot vector of all monitored dimensions."""
        now = time.time()
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))

        if not self.is_healthy():
            logger.info(f"Prometheus at {self.base_url} is currently unreachable. Recording baseline zero-metrics.")
            return {
                "timestamp": now,
                "timestamp_iso": now_iso,
                "cpu_cores": 0.0,
                "memory_mb": 0.0,
                "request_rate_rps": 0.0,
                "error_rate_pct": 0.0,
                "p95_latency_ms": 0.0,
                "active_pods": 1,
            }

        return {
            "timestamp": now,
            "timestamp_iso": now_iso,
            "cpu_cores": self.get_cpu_usage(),
            "memory_mb": self.get_memory_usage_mb(),
            "request_rate_rps": self.get_http_request_rate(),
            "error_rate_pct": self.get_error_rate_percentage(),
            "p95_latency_ms": self.get_p95_latency_ms(),
            "active_pods": self.get_active_pods(),
        }

