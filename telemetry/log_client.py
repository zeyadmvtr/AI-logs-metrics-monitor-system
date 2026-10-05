import json
import logging
import subprocess
from typing import List, Dict, Any, Optional
import requests

from telemetry.config import get_telemetry_settings

logger = logging.getLogger("telemetry.logs")


class LogStoreClient:
    """Programmatic client for querying container logs from Loki with K8s fallback."""

    def __init__(self, base_url: Optional[str] = None):
        settings = get_telemetry_settings()
        self.base_url = (base_url or settings.LOKI_URL).rstrip("/")
        self.timeout = settings.LOKI_TIMEOUT_SECONDS
        self.namespace = settings.K8S_NAMESPACE
        self.app_name = settings.APP_NAME

    def is_loki_healthy(self) -> bool:
        """Checks if the Loki HTTP endpoint is responding."""
        try:
            res = requests.get(f"{self.base_url}/ready", timeout=2)
            return res.status_code == 200
        except Exception:
            return False

    def query_loki(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Queries the Grafana Loki API using LogQL."""
        url = f"{self.base_url}/loki/api/v1/query_range"
        params = {"query": query, "limit": limit}

        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            results: List[Dict[str, Any]] = []
            streams = data.get("data", {}).get("result", [])
            for stream in streams:
                for entry in stream.get("values", []):
                    # entry format: [nano_timestamp_str, "log_string"]
                    raw_text = entry[1]
                    parsed = self._parse_log_line(raw_text)
                    results.append(parsed)
            return results
        except Exception as exc:
            logger.debug(f"Loki query failed, falling back to kubectl: {exc}")
            return []

    def query_kubectl_fallback(self, lines: int = 50) -> List[Dict[str, Any]]:
        """Fallback to direct Kubernetes stdout logs via kubectl CLI."""
        cmd = [
            "kubectl", "logs",
            "-l", f"app.kubernetes.io/name={self.app_name}",
            "-n", self.namespace,
            f"--tail={lines}",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if proc.returncode != 0:
                # Try fallback namespace 'aiops'
                cmd[4] = "aiops"
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if proc.returncode != 0:
                    return []

            parsed_logs = []
            for line in proc.stdout.strip().split("\n"):
                if line.strip():
                    parsed_logs.append(self._parse_log_line(line.strip()))
            return parsed_logs
        except Exception as exc:
            logger.warning(f"Failed to fetch logs via kubectl fallback: {exc}")
            return []

    def _parse_log_line(self, line: str) -> Dict[str, Any]:
        """Parses a raw log line, extracting JSON payload if present."""
        try:
            # Check if line is JSON
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

        # Return structured fallback for plain text lines
        return {
            "level": "INFO",
            "message": line,
            "raw": True,
        }

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetches the most recent container logs, trying Loki first then kubectl."""
        if self.is_loki_healthy():
            logql = f'{{namespace=~"{self.namespace}|aiops", app="{self.app_name}"}}'
            logs = self.query_loki(logql, limit=limit)
            if logs:
                return logs

        # Fallback to direct container logs
        return self.query_kubectl_fallback(lines=limit)

    def get_error_logs(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Filters recent logs for warning and error events (vital for Phase 4 RCA)."""
        all_logs = self.get_recent_logs(limit=limit * 2)
        error_logs = [
            log for log in all_logs
            if str(log.get("level", "")).upper() in ("ERROR", "WARNING", "CRITICAL")
            or "error" in str(log.get("message", "")).lower()
            or "exception" in str(log.get("message", "")).lower()
        ]
        return error_logs[:limit]
