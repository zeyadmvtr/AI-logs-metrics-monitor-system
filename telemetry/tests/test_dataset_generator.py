import os
import unittest
import pandas as pd
from telemetry.generate_dataset import TelemetryDatasetGenerator


class TestDatasetGenerator(unittest.TestCase):

    def setUp(self):
        self.generator = TelemetryDatasetGenerator(backend_url="http://localhost:8000")

    def test_synthetic_dataset_generation(self):
        output_file = self.generator.generate_synthetic_dataset(num_samples=50)
        self.assertTrue(os.path.exists(output_file))

        df = pd.read_csv(output_file)
        self.assertEqual(len(df), 50)
        self.assertIn("cpu_cores", df.columns)
        self.assertIn("memory_mb", df.columns)
        self.assertIn("error_rate_pct", df.columns)
        self.assertIn("p95_latency_ms", df.columns)
        self.assertIn("is_anomaly", df.columns)
        self.assertIn("anomaly_type", df.columns)


if __name__ == "__main__":
    unittest.main()
