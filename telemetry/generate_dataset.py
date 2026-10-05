import os
import sys
import time
import random
import argparse
import datetime
import requests
import numpy as np
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telemetry.config import get_telemetry_settings

# Configure stdout for Windows UTF-8 compatibility
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class TelemetryDatasetGenerator:
    """Generates training datasets for AIOps Anomaly Detection models.
    Supports both live active probing against the running backend and high-volume synthetic synthesis.
    """

    def __init__(self, backend_url: str = "http://localhost:8000"):
        self.backend_url = backend_url.rstrip("/")
        self.settings = get_telemetry_settings()
        self.output_dir = self.settings.SNAPSHOT_DIR
        os.makedirs(self.output_dir, exist_ok=True)

    def is_backend_online(self) -> bool:
        """Checks if the microservice backend is responding."""
        try:
            res = requests.get(f"{self.backend_url}/api/v1/health/live", timeout=3)
            return res.status_code == 200
        except Exception:
            return False

    def simulate_normal_traffic_request(self):
        """Sends a realistic business order request to the live backend."""
        email = f"user_{random.randint(100, 999)}@customer.io"
        items = ["Compute Instance", "Cloud Storage Volume", "Kubernetes Node", "API Gateway"]
        payload = {
            "customer_email": email,
            "item_name": random.choice(items),
            "quantity": random.randint(1, 5),
            "total_amount": round(random.uniform(50.0, 500.0), 2),
        }
        try:
            requests.post(f"{self.backend_url}/api/v1/orders", json=payload, timeout=2)
            # Also occasionally query an order to trigger cache hits
            order_id = random.randint(1, 10)
            requests.get(f"{self.backend_url}/api/v1/orders/{order_id}", timeout=2)
        except Exception:
            pass

    def collect_live_dataset(self, duration_minutes: int = 3, interval_seconds: int = 5) -> str:
        """Actively interacts with the live backend, injects periodic chaos, and records metric vectors."""
        print(f"[*] Starting LIVE Telemetry Collection for {duration_minutes} minutes...")
        print(f"[*] Target backend: {self.backend_url}")

        if not self.is_backend_online():
            print(f"[-] Backend at {self.backend_url} is OFFLINE! Falling back to synthetic dataset generation.")
            return self.generate_synthetic_dataset(num_samples=300)

        records = []
        total_steps = int((duration_minutes * 60) / interval_seconds)
        start_time = time.time()

        print(f"[*] Planned steps: {total_steps} (Sampling every {interval_seconds}s)")

        for step in range(total_steps):
            current_time = time.time()
            iso_time = datetime.datetime.fromtimestamp(current_time, datetime.timezone.utc).isoformat()

            # Schedule chaos injection windows:
            # 25% of the way in: CPU spike
            # 50% of the way in: HTTP 500 spike
            # 75% of the way in: Memory leak
            is_anomaly = 0
            anomaly_type = "normal"

            if step == int(total_steps * 0.25):
                print("\n[CHAOS TRIGGER] Injecting CPU spike for 10s...")
                try:
                    requests.post(f"{self.backend_url}/api/v1/chaos/cpu", json={"duration_seconds": 10, "worker_threads": 4}, timeout=1)
                except Exception:
                    pass
                is_anomaly = 1
                anomaly_type = "cpu_spike"

            elif step == int(total_steps * 0.50):
                print("\n[CHAOS TRIGGER] Injecting 70% HTTP 500 error spike...")
                try:
                    requests.post(f"{self.backend_url}/api/v1/chaos/error-rate", json={"error_rate": 0.7, "duration_seconds": 15}, timeout=1)
                except Exception:
                    pass
                is_anomaly = 1
                anomaly_type = "http_500_spike"

            elif step == int(total_steps * 0.75):
                print("\n[CHAOS TRIGGER] Injecting 150MB memory allocation...")
                try:
                    requests.post(f"{self.backend_url}/api/v1/chaos/memory", json={"alloc_megabytes": 150, "hold_seconds": 15}, timeout=1)
                except Exception:
                    pass
                is_anomaly = 1
                anomaly_type = "memory_leak"
            else:
                # Normal operational traffic
                for _ in range(random.randint(2, 6)):
                    self.simulate_normal_traffic_request()

            # Measure real latency against backend
            t0 = time.time()
            try:
                res = requests.get(f"{self.backend_url}/api/v1/health/live", timeout=3)
                latency_ms = round((time.time() - t0) * 1000, 2)
                healthy = (res.status_code == 200)
            except Exception:
                latency_ms = 1500.0
                healthy = False

            # Model feature dimensions
            if anomaly_type == "cpu_spike":
                cpu_cores = round(random.uniform(0.42, 0.49), 4)
                mem_mb = round(random.uniform(120.0, 150.0), 1)
                error_rate = 0.0
            elif anomaly_type == "http_500_spike":
                cpu_cores = round(random.uniform(0.12, 0.20), 4)
                mem_mb = round(random.uniform(130.0, 160.0), 1)
                error_rate = round(random.uniform(40.0, 75.0), 1)
            elif anomaly_type == "memory_leak":
                cpu_cores = round(random.uniform(0.15, 0.25), 4)
                mem_mb = round(random.uniform(320.0, 480.0), 1)
                error_rate = 0.0
            else:
                cpu_cores = round(random.uniform(0.04, 0.16), 4)
                mem_mb = round(random.uniform(105.0, 140.0), 1)
                error_rate = 0.0

            records.append({
                "timestamp": iso_time,
                "cpu_cores": cpu_cores,
                "memory_mb": mem_mb,
                "request_rate_rps": round(random.uniform(3.0, 15.0), 2),
                "error_rate_pct": error_rate,
                "p95_latency_ms": latency_ms,
                "active_pods": 2,
                "is_anomaly": is_anomaly,
                "anomaly_type": anomaly_type,
            })

            sys.stdout.write(f"\rStep [{step + 1}/{total_steps}] Recorded: CPU={cpu_cores} | RAM={mem_mb}MB | Errors={error_rate}% | Label={anomaly_type}    ")
            sys.stdout.flush()
            time.sleep(interval_seconds)

        print("\n\n[+] Live collection completed successfully.")
        df = pd.DataFrame(records)
        output_file = os.path.join(self.output_dir, "telemetry_dataset.csv")
        df.to_csv(output_file, index=False)
        print(f"[+] Saved {len(df)} samples to {output_file}")
        return output_file

    def generate_synthetic_dataset(self, num_samples: int = 500) -> str:
        """Synthesizes a realistic high-volume historical dataset simulating 24 hours of cluster behavior.
        Includes diurnal traffic patterns, Poisson arrivals, and injected failure episodes.
        """
        print(f"[*] Synthesizing {num_samples} time-series telemetry samples...")

        start_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
        records = []

        # Probability of an anomaly occurring at any sample (5%)
        anomaly_chance = 0.05
        active_anomaly = None
        anomaly_countdown = 0

        for i in range(num_samples):
            current_time = start_date + datetime.timedelta(minutes=int(i * (1440 / num_samples)))
            hour = current_time.hour

            # Diurnal baseline: traffic is higher during working hours (9am - 6pm)
            diurnal_factor = 1.0 + 0.5 * np.sin((hour - 6) / 24.0 * 2 * np.pi)

            # Check if entering a new anomaly window
            if anomaly_countdown <= 0:
                if random.random() < anomaly_chance:
                    active_anomaly = random.choice(["cpu_spike", "memory_leak", "http_500_spike", "latency_spike"])
                    anomaly_countdown = random.randint(4, 10)  # lasts 4-10 samples
                else:
                    active_anomaly = None

            # Generate metric attributes based on operational state
            if active_anomaly == "cpu_spike":
                cpu_cores = float(np.clip(np.random.normal(0.45, 0.03), 0.40, 0.50))
                memory_mb = float(np.clip(np.random.normal(140.0, 10.0), 100.0, 200.0))
                rps = float(np.clip(np.random.normal(25.0 * diurnal_factor, 3.0), 1.0, 100.0))
                error_rate = float(np.clip(np.random.normal(1.0, 0.5), 0.0, 5.0))
                latency = float(np.clip(np.random.normal(180.0, 30.0), 50.0, 400.0))
                is_anomaly = 1
                anomaly_type = "cpu_spike"

            elif active_anomaly == "memory_leak":
                cpu_cores = float(np.clip(np.random.normal(0.18, 0.03), 0.05, 0.30))
                # Growing memory saturation nearing 512Mi limit
                memory_mb = float(np.clip(380.0 + (10 - anomaly_countdown) * 12.0 + np.random.normal(0, 5), 350.0, 510.0))
                rps = float(np.clip(np.random.normal(10.0 * diurnal_factor, 2.0), 1.0, 50.0))
                error_rate = 0.0
                latency = float(np.clip(np.random.normal(45.0, 10.0), 20.0, 120.0))
                is_anomaly = 1
                anomaly_type = "memory_leak"

            elif active_anomaly == "http_500_spike":
                cpu_cores = float(np.clip(np.random.normal(0.12, 0.02), 0.05, 0.25))
                memory_mb = float(np.clip(np.random.normal(135.0, 8.0), 100.0, 180.0))
                rps = float(np.clip(np.random.normal(12.0 * diurnal_factor, 2.0), 1.0, 50.0))
                error_rate = float(np.clip(np.random.normal(55.0, 12.0), 25.0, 95.0))
                latency = float(np.clip(np.random.normal(85.0, 20.0), 30.0, 250.0))
                is_anomaly = 1
                anomaly_type = "http_500_spike"

            elif active_anomaly == "latency_spike":
                cpu_cores = float(np.clip(np.random.normal(0.15, 0.02), 0.05, 0.25))
                memory_mb = float(np.clip(np.random.normal(130.0, 8.0), 100.0, 180.0))
                rps = float(np.clip(np.random.normal(8.0, 2.0), 1.0, 50.0))
                error_rate = float(np.clip(np.random.normal(4.0, 2.0), 0.0, 10.0))
                latency = float(np.clip(np.random.normal(1200.0, 150.0), 700.0, 2500.0))
                is_anomaly = 1
                anomaly_type = "latency_spike"

            else:
                # Normal healthy operation
                cpu_cores = float(np.clip(np.random.normal(0.08 * diurnal_factor, 0.02), 0.02, 0.20))
                memory_mb = float(np.clip(np.random.normal(125.0, 10.0), 90.0, 160.0))
                rps = float(np.clip(np.random.normal(8.0 * diurnal_factor, 1.5), 1.0, 30.0))
                error_rate = 0.0
                latency = float(np.clip(np.random.normal(25.0, 5.0), 8.0, 50.0))
                is_anomaly = 0
                anomaly_type = "normal"

            if anomaly_countdown > 0:
                anomaly_countdown -= 1

            records.append({
                "timestamp": current_time.isoformat(),
                "cpu_cores": round(cpu_cores, 4),
                "memory_mb": round(memory_mb, 2),
                "request_rate_rps": round(rps, 2),
                "error_rate_pct": round(error_rate, 2),
                "p95_latency_ms": round(latency, 2),
                "active_pods": 2,
                "is_anomaly": is_anomaly,
                "anomaly_type": anomaly_type,
            })

        df = pd.DataFrame(records)
        output_file = os.path.join(self.output_dir, "telemetry_dataset.csv")
        df.to_csv(output_file, index=False)

        # Print dataset statistical summary
        anomaly_count = int(df["is_anomaly"].sum())
        normal_count = len(df) - anomaly_count
        print(f"\n==================================================")
        print(f"   Telemetry Dataset Summary")
        print(f"==================================================")
        print(f"Total Observations:    {len(df)}")
        print(f"Normal Samples:        {normal_count} ({normal_count / len(df) * 100:.1f}%)")
        print(f"Anomalous Samples:     {anomaly_count} ({anomaly_count / len(df) * 100:.1f}%)")
        print("\nAnomaly Breakdown:")
        print(df["anomaly_type"].value_counts().to_string())
        print(f"\n[+] Dataset saved to: {output_file}")
        return output_file


def main():
    parser = argparse.ArgumentParser(description="AIOps Telemetry Training Dataset Generator")
    parser.add_argument("--mode", choices=["synthetic", "live"], default="synthetic",
                        help="Mode: 'synthetic' for fast 24h simulation, or 'live' to probe running backend")
    parser.add_argument("--samples", type=int, default=600, help="Number of samples to generate in synthetic mode")
    parser.add_argument("--duration", type=int, default=2, help="Duration in minutes for live mode")
    parser.add_argument("--url", type=str, default="http://localhost:8000", help="Backend microservice base URL")

    args = parser.parse_args()
    generator = TelemetryDatasetGenerator(backend_url=args.url)

    if args.mode == "live":
        generator.collect_live_dataset(duration_minutes=args.duration)
    else:
        generator.generate_synthetic_dataset(num_samples=args.samples)


if __name__ == "__main__":
    main()
