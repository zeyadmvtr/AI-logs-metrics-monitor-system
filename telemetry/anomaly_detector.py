import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger("telemetry.anomaly_detector")


class AnomalyReport:
    """Represents the output of the anomaly detection engine."""

    def __init__(
        self,
        is_anomaly: bool,
        anomaly_type: str,
        confidence: float,
        deviant_metrics: Dict[str, Dict[str, Any]],
        summary: str,
    ):
        self.is_anomaly = is_anomaly
        self.anomaly_type = anomaly_type
        self.confidence = round(confidence, 3)
        self.deviant_metrics = deviant_metrics
        self.summary = summary

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_anomaly": self.is_anomaly,
            "anomaly_type": self.anomaly_type,
            "confidence": self.confidence,
            "deviant_metrics": self.deviant_metrics,
            "summary": self.summary,
        }


class AnomalyDetector:
    """Hybrid Anomaly Detection Engine combining Unsupervised ML (Isolation Forest)
    and Domain-specific SRE heuristic rule-bounds.
    """

    FEATURE_COLUMNS = [
        "cpu_cores",
        "memory_mb",
        "request_rate_rps",
        "error_rate_pct",
        "p95_latency_ms",
    ]

    # Kubernetes container resource baseline limits (Requests: 100m / 128Mi; Limits: 500m / 512Mi)
    THRESHOLDS = {
        "cpu_cores": {"warning": 0.35, "critical": 0.45, "normal": 0.10},
        "memory_mb": {"warning": 380.0, "critical": 460.0, "normal": 120.0},
        "error_rate_pct": {"warning": 2.0, "critical": 5.0, "normal": 0.0},
        "p95_latency_ms": {"warning": 250.0, "critical": 450.0, "normal": 25.0},
    }

    def __init__(self, contamination: float = 0.05):
        self.contamination = contamination
        self.model = None
        self._init_ml_model()

    def _init_ml_model(self):
        try:
            from sklearn.ensemble import IsolationForest
            self.model = IsolationForest(
                n_estimators=100,
                contamination=self.contamination,
                random_state=42
            )
        except Exception as e:
            logger.debug(f"IsolationForest initialization deferred: {e}")
            self.model = None

    def fit_baseline(self, historical_df: pd.DataFrame):
        """Fits the Isolation Forest on known normal operational data."""
        if self.model is None or historical_df is None or len(historical_df) < 10:
            return

        valid_cols = [c for c in self.FEATURE_COLUMNS if c in historical_df.columns]
        if len(valid_cols) == len(self.FEATURE_COLUMNS):
            clean_df = historical_df[valid_cols].dropna()
            if len(clean_df) >= 10:
                self.model.fit(clean_df)
                logger.info(f"Fitted IsolationForest on {len(clean_df)} baseline telemetry samples.")

    def evaluate_vector(
        self,
        current_metrics: Dict[str, Any],
        recent_history: Optional[pd.DataFrame] = None
    ) -> AnomalyReport:
        """Evaluates a live telemetry vector against baselines and ML models."""
        deviations: Dict[str, Dict[str, Any]] = {}
        detected_types: List[Tuple[str, float]] = []

        # 1. Rule-based SRE metric boundary evaluation
        for metric, bounds in self.THRESHOLDS.items():
            val = float(current_metrics.get(metric, 0.0))
            if val >= bounds["critical"]:
                deviations[metric] = {
                    "observed": val,
                    "baseline": bounds["normal"],
                    "severity": "CRITICAL",
                    "ratio_to_normal": round(val / max(bounds["normal"], 0.001), 2)
                }
            elif val >= bounds["warning"]:
                deviations[metric] = {
                    "observed": val,
                    "baseline": bounds["normal"],
                    "severity": "WARNING",
                    "ratio_to_normal": round(val / max(bounds["normal"], 0.001), 2)
                }

        # 2. Pinpoint specific anomaly archetype
        if "memory_mb" in deviations and deviations["memory_mb"]["severity"] in ("CRITICAL", "WARNING"):
            detected_types.append(("memory_leak", 0.95 if deviations["memory_mb"]["severity"] == "CRITICAL" else 0.80))

        if "error_rate_pct" in deviations and deviations["error_rate_pct"]["severity"] in ("CRITICAL", "WARNING"):
            detected_types.append(("http_500_spike", 0.98 if deviations["error_rate_pct"]["severity"] == "CRITICAL" else 0.85))

        if "cpu_cores" in deviations and deviations["cpu_cores"]["severity"] in ("CRITICAL", "WARNING"):
            detected_types.append(("cpu_spike", 0.92 if deviations["cpu_cores"]["severity"] == "CRITICAL" else 0.78))

        if "p95_latency_ms" in deviations and deviations["p95_latency_ms"]["severity"] in ("CRITICAL", "WARNING"):
            detected_types.append(("latency_spike", 0.88 if deviations["p95_latency_ms"]["severity"] == "CRITICAL" else 0.72))

        # 3. Isolation Forest ML anomaly scoring if available
        ml_score = 0.0
        ml_anomaly = False
        if self.model is not None and recent_history is not None and len(recent_history) >= 5:
            try:
                row = pd.DataFrame([{col: current_metrics.get(col, 0.0) for col in self.FEATURE_COLUMNS}])
                pred = self.model.predict(row)[0]  # -1 for anomaly, 1 for normal
                decision = self.model.decision_function(row)[0]
                ml_score = round(float(decision), 4)
                if pred == -1:
                    ml_anomaly = True
            except Exception as e:
                logger.debug(f"ML evaluation skipped: {e}")

        # Combine signals
        is_anomaly = bool(deviations or ml_anomaly)
        if not is_anomaly:
            return AnomalyReport(
                is_anomaly=False,
                anomaly_type="normal",
                confidence=0.99,
                deviant_metrics={},
                summary="All telemetry signals operating within steady-state normal bounds."
            )

        # Pick primary anomaly type
        if detected_types:
            detected_types.sort(key=lambda x: x[1], reverse=True)
            primary_type, confidence = detected_types[0]
        else:
            primary_type = "unclassified_anomaly"
            confidence = 0.70

        breached_strs = [f"{k}={v.get('observed')}" for k, v in deviations.items()]
        summary = (
            f"Detected {primary_type.upper()} with {confidence*100:.0f}% confidence. "
            f"Breached metrics: {', '.join(breached_strs)}."
        )

        return AnomalyReport(
            is_anomaly=True,
            anomaly_type=primary_type,
            confidence=confidence,
            deviant_metrics=deviations,
            summary=summary
        )
