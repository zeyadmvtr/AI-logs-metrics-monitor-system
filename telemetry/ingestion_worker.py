import os
import sys
import time
import signal
import logging
import argparse
from typing import Optional, Callable
import pandas as pd
from tabulate import tabulate

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telemetry.config import get_telemetry_settings
from telemetry.prometheus_client import PrometheusClient
from telemetry.log_client import LogStoreClient
from telemetry.storage import TelemetryBuffer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("telemetry.worker")


class TelemetryIngestionWorker:
    """Background worker that continuously polls Prometheus metrics and log streams."""

    def __init__(
        self,
        poll_interval: Optional[int] = None,
        on_batch_callback: Optional[Callable[[pd.DataFrame, list], None]] = None,
    ):
        self.settings = get_telemetry_settings()
        self.interval = poll_interval or self.settings.POLL_INTERVAL_SECONDS
        self.prom_client = PrometheusClient()
        self.log_client = LogStoreClient()
        self.buffer = TelemetryBuffer()
        self.on_batch_callback = on_batch_callback
        self._running = False

    def poll_once(self) -> dict:
        """Executes a single polling iteration for metrics and logs."""
        # 1. Collect metric vector
        metrics = self.prom_client.get_current_metrics_vector()
        self.buffer.append_metric_vector(metrics)

        # 2. Collect recent error logs
        recent_logs = self.log_client.get_recent_logs(limit=30)
        self.buffer.update_latest_logs(recent_logs)

        # 3. Save snapshot to disk
        self.buffer.save_snapshot()

        # 4. Invoke ML callback if registered (Phase 4 integration hook)
        if self.on_batch_callback:
            df = self.buffer.get_feature_dataframe()
            error_logs = self.log_client.get_error_logs(limit=20)
            self.on_batch_callback(df, error_logs)

        return metrics

    def display_metrics_table(self, metrics: dict):
        """Prints a human-readable telemetry status table."""
        headers = ["Metric Dimension", "Observed Value", "Status"]
        rows = [
            ["Active Backend Pods", f"{metrics.get('active_pods', 0)}", "OK"],
            ["CPU Usage (Cores)", f"{metrics.get('cpu_cores', 0.0):.4f}", "OK" if metrics.get("cpu_cores", 0) < 0.4 else "HIGH"],
            ["Memory Working Set", f"{metrics.get('memory_mb', 0.0):.1f} MB", "OK" if metrics.get("memory_mb", 0) < 400 else "HIGH"],
            ["HTTP Throughput", f"{metrics.get('request_rate_rps', 0.0):.2f} req/s", "OK"],
            ["HTTP 5xx Error Rate", f"{metrics.get('error_rate_pct', 0.0):.1f} %", "OK" if metrics.get("error_rate_pct", 0) < 5.0 else "ALERT"],
            ["P95 Response Latency", f"{metrics.get('p95_latency_ms', 0.0):.1f} ms", "OK" if metrics.get("p95_latency_ms", 0) < 500 else "DEGRADED"],
        ]
        table_output = tabulate(rows, headers=headers, tablefmt="grid")
        print("\n" + "="*58)

        print(f" AIOps Live Telemetry Snapshot - {metrics.get('timestamp_iso')}")
        print("="*58)
        print(table_output)

    def start(self):
        """Starts the continuous background polling loop."""
        self._running = True
        logger.info(f"Starting Telemetry Ingestion Worker (Poll Interval: {self.interval}s)...")
        logger.info(f"Target Prometheus: {self.prom_client.base_url} | Namespace: {self.prom_client.namespace}")

        try:
            while self._running:
                try:
                    metrics = self.poll_once()
                    self.display_metrics_table(metrics)
                except Exception as exc:
                    logger.error(f"Error during telemetry polling cycle: {exc}", exc_info=True)

                time.sleep(self.interval)
        except KeyboardInterrupt:
            logger.info("Telemetry Ingestion Worker stopped by user.")
        finally:
            self._running = False

    def stop(self):
        """Stops the worker daemon."""
        self._running = False


def main():
    parser = argparse.ArgumentParser(description="AIOps Telemetry Ingestion Worker")
    parser.add_argument("--interval", type=int, default=10, help="Poll interval in seconds")
    parser.add_argument("--once", action="store_true", help="Execute single poll and exit")
    parser.add_argument("--enable-rca", action="store_true", help="Enable automatic LLM Root Cause Analysis on anomalies")
    args = parser.parse_args()

    on_batch_cb = None
    if args.enable_rca:
        try:
            from telemetry.rca_engine import RCAEngine
            rca_engine = RCAEngine()

            def rca_callback(df: pd.DataFrame, error_logs: list):
                if df is not None and not df.empty:
                    latest = df.iloc[-1].to_dict()
                    rep = rca_engine.diagnose(latest, recent_logs=error_logs, history_df=df)
                    if rep.get("is_anomaly"):
                        print("\n" + "!" * 58)
                        print(f" [AIOPS RCA ALERT] {rep.get('severity')} - {rep.get('root_cause')}")
                        print(f" Incident: {rep.get('incident_id')} | Report saved to data/rca_reports/")
                        print("!" * 58 + "\n")

            on_batch_cb = rca_callback
            logger.info("AIOps RCA Engine callback registered.")
        except Exception as e:
            logger.warning(f"Could not initialize RCA Engine callback: {e}")

    worker = TelemetryIngestionWorker(poll_interval=args.interval, on_batch_callback=on_batch_cb)

    if args.once:
        logger.info("Executing single telemetry polling cycle (--once)...")
        metrics = worker.poll_once()
        worker.display_metrics_table(metrics)
        logger.info(f"Snapshot written to {worker.settings.SNAPSHOT_DIR}/telemetry_latest.json")
    else:
        # Handle graceful shutdown signals
        signal.signal(signal.SIGINT, lambda s, f: worker.stop())
        signal.signal(signal.SIGTERM, lambda s, f: worker.stop())
        worker.start()


if __name__ == "__main__":
    main()
