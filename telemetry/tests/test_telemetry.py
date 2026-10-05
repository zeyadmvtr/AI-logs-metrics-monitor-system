import unittest
from unittest.mock import patch, MagicMock
from telemetry.prometheus_client import PrometheusClient
from telemetry.log_client import LogStoreClient
from telemetry.storage import TelemetryBuffer
from telemetry.ingestion_worker import TelemetryIngestionWorker


class TestTelemetryPipeline(unittest.TestCase):

    def test_prometheus_scalar_extraction(self):
        client = PrometheusClient(base_url="http://mock-prom:9090")
        mock_data = {
            "resultType": "vector",
            "result": [
                {
                    "metric": {},
                    "value": [1700000000, "0.145"]
                }
            ]
        }
        val = client._extract_scalar(mock_data)
        self.assertEqual(val, 0.145)

    def test_log_line_parsing_json(self):
        client = LogStoreClient(base_url="http://mock-loki:3100")
        json_line = '{"timestamp": "2026-10-05T10:00:00Z", "level": "ERROR", "message": "DB timeout", "error_code": 500}'
        parsed = client._parse_log_line(json_line)
        self.assertEqual(parsed.get("level"), "ERROR")
        self.assertEqual(parsed.get("error_code"), 500)

    def test_log_line_parsing_plain_text(self):
        client = LogStoreClient(base_url="http://mock-loki:3100")
        raw_line = "INFO: Uvicorn running on http://0.0.0.0:8000"
        parsed = client._parse_log_line(raw_line)
        self.assertEqual(parsed.get("message"), raw_line)
        self.assertTrue(parsed.get("raw"))

    def test_telemetry_buffer_dataframe(self):
        buffer = TelemetryBuffer(max_samples=10)
        sample = {
            "timestamp": 1700000000,
            "cpu_cores": 0.25,
            "memory_mb": 150.0,
            "request_rate_rps": 12.5,
            "error_rate_pct": 0.0,
            "p95_latency_ms": 45.2,
            "active_pods": 2
        }
        buffer.append_metric_vector(sample)
        df = buffer.get_feature_dataframe()
        self.assertEqual(len(df), 1)
        self.assertEqual(df["cpu_cores"].iloc[0], 0.25)
        self.assertEqual(df["memory_mb"].iloc[0], 150.0)

    @patch.object(PrometheusClient, "get_current_metrics_vector")
    @patch.object(LogStoreClient, "get_recent_logs")
    def test_ingestion_worker_poll_once(self, mock_logs, mock_metrics):
        mock_metrics.return_value = {
            "timestamp": 1700000000,
            "timestamp_iso": "2026-10-05T10:00:00Z",
            "cpu_cores": 0.12,
            "memory_mb": 110.0,
            "request_rate_rps": 5.0,
            "error_rate_pct": 0.0,
            "p95_latency_ms": 25.0,
            "active_pods": 2
        }
        mock_logs.return_value = [{"level": "INFO", "message": "Health check OK"}]

        callback_called = []
        def test_callback(df, logs):
            callback_called.append(True)

        worker = TelemetryIngestionWorker(poll_interval=10, on_batch_callback=test_callback)
        result = worker.poll_once()

        self.assertEqual(result["cpu_cores"], 0.12)
        self.assertEqual(len(callback_called), 1)


if __name__ == "__main__":
    unittest.main()
