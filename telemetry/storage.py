import os
import json
from collections import deque
from typing import List, Dict, Any, Optional
import pandas as pd

from telemetry.config import get_telemetry_settings


class TelemetryBuffer:
    """Sliding-window in-memory and disk buffer for metric vectors and correlated logs."""

    def __init__(self, max_samples: Optional[int] = None):
        settings = get_telemetry_settings()
        self.max_samples = max_samples or settings.SLIDING_WINDOW_SAMPLES
        self.snapshot_dir = settings.SNAPSHOT_DIR
        self._metric_records: deque = deque(maxlen=self.max_samples)
        self._latest_logs: List[Dict[str, Any]] = []

        os.makedirs(self.snapshot_dir, exist_ok=True)

    def append_metric_vector(self, vector: Dict[str, Any]):
        """Adds a new time-series metric observation."""
        self._metric_records.append(vector)

    def update_latest_logs(self, logs: List[Dict[str, Any]]):
        """Updates the recent log cache for RCA correlation."""
        self._latest_logs = logs

    def get_feature_dataframe(self) -> pd.DataFrame:
        """Converts buffered metric samples into a pandas DataFrame for ML models."""
        if not self._metric_records:
            return pd.DataFrame(columns=[
                "timestamp", "cpu_cores", "memory_mb",
                "request_rate_rps", "error_rate_pct", "p95_latency_ms"
            ])
        return pd.DataFrame(list(self._metric_records))

    def save_snapshot(self, filename: str = "telemetry_latest.json"):
        """Saves current buffer state to a JSON snapshot file."""
        snapshot = {
            "record_count": len(self._metric_records),
            "latest_metrics": self._metric_records[-1] if self._metric_records else None,
            "metric_history": list(self._metric_records),
            "recent_logs": self._latest_logs[-20:],
        }
        file_path = os.path.join(self.snapshot_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)

    def load_snapshot(self, filename: str = "telemetry_latest.json") -> bool:
        """Loads a saved snapshot into the buffer."""
        file_path = os.path.join(self.snapshot_dir, filename)
        if not os.path.exists(file_path):
            return False
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                snapshot = json.load(f)
            history = snapshot.get("metric_history", [])
            for item in history:
                self._metric_records.append(item)
            self._latest_logs = snapshot.get("recent_logs", [])
            return True
        except Exception:
            return False
