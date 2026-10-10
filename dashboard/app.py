import os
import sys
import time
import json
import glob
import random
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Configure project path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from telemetry.config import get_telemetry_settings
from telemetry.anomaly_detector import AnomalyDetector
from telemetry.llm_inference import LLMRCAInference
from telemetry.rca_engine import RCAEngine
from telemetry.email_dispatcher import EmailAlertDispatcher

# ---------------------------------------------------------
# Page Configuration & Futuristic SRE Styling
# ---------------------------------------------------------
st.set_page_config(
    page_title="PodGuard AI | Kubernetes SRE Command Center",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Catchy CSS (Glassmorphism, Neon Glow, Cyberpunk SRE)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;800&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    code, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Main background & glass effects */
    .stApp {
        background: radial-gradient(circle at 10% 10%, #0d1527 0%, #060913 100%);
        color: #f1f5f9;
    }

    /* Header styling */
    .podguard-header {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 16px;
        padding: 24px 32px;
        margin-bottom: 24px;
        box-shadow: 0 10px 30px -10px rgba(14, 165, 233, 0.2);
        backdrop-filter: blur(12px);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .podguard-title {
        font-size: 32px;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8 0%, #818cf8 50%, #c084fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        letter-spacing: -0.02em;
    }
    .podguard-subtitle {
        color: #94a3b8;
        font-size: 14px;
        margin-top: 4px;
    }

    /* Status badge pill */
    .status-pill-ok {
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid #10b981;
        color: #34d399;
        padding: 6px 16px;
        border-radius: 9999px;
        font-size: 13px;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        box-shadow: 0 0 15px rgba(16, 185, 129, 0.3);
    }
    .status-pill-alert {
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid #ef4444;
        color: #f87171;
        padding: 6px 16px;
        border-radius: 9999px;
        font-size: 13px;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        animation: pulse 1.5s infinite;
        box-shadow: 0 0 20px rgba(239, 68, 68, 0.4);
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.85; transform: scale(1.02); }
    }

    /* Metric cards */
    .metric-card {
        background: rgba(15, 23, 42, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 18px 20px;
        backdrop-filter: blur(8px);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(56, 189, 248, 0.4);
    }
    .metric-label {
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #94a3b8;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 26px;
        font-weight: 800;
        color: #f8fafc;
        margin-bottom: 4px;
    }
    .metric-sub {
        font-size: 12px;
        color: #64748b;
    }

    /* RCA Box styling */
    .rca-box {
        background: linear-gradient(180deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.95) 100%);
        border: 1px solid #ef4444;
        border-radius: 14px;
        padding: 24px;
        margin-top: 16px;
        box-shadow: 0 10px 25px -5px rgba(239, 68, 68, 0.25);
    }
    .rca-box-normal {
        background: linear-gradient(180deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
        border: 1px solid rgba(16, 185, 129, 0.4);
        border-radius: 14px;
        padding: 24px;
        margin-top: 16px;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# State Initialization & Engine Singletons
# ---------------------------------------------------------
@st.cache_resource
def get_rca_engine():
    return RCAEngine()

@st.cache_resource
def get_email_dispatcher():
    return EmailAlertDispatcher()

engine = get_rca_engine()
dispatcher = get_email_dispatcher()

if "chaos_state" not in st.session_state:
    st.session_state.chaos_state = "NORMAL"

if "simulated_metrics" not in st.session_state:
    st.session_state.simulated_metrics = {
        "cpu_cores": 0.112,
        "memory_mb": 138.4,
        "request_rate_rps": 11.2,
        "error_rate_pct": 0.0,
        "p95_latency_ms": 23.5,
        "active_pods": 2
    }

if "history_buffer" not in st.session_state:
    st.session_state.history_buffer = []


# ---------------------------------------------------------
# Sidebar Controls & Live Chaos Generator
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("### 🎛️ **PodGuard Telemetry Controls**")
    backend_mode = st.radio(
        "Data Source Mode",
        ["Live Telemetry / Active Backend", "Interactive Chaos Simulator"],
        index=1,
        help="Switch between live Prometheus / FastAPI polling and instant browser simulation"
    )

    backend_url = st.text_input("FastAPI Backend URL", value="http://localhost:8000")

    st.markdown("---")
    st.markdown("### ⚡ **Chaos Fault Injection**")
    st.caption("Click to simulate live production outages and evaluate the AI detector:")

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        if st.button("💧 Memory Leak", use_container_width=True, help="Simulate uncollected cache climbing to 485MB"):
            st.session_state.chaos_state = "MEMORY_LEAK"
            st.session_state.simulated_metrics.update({
                "cpu_cores": 0.178,
                "memory_mb": 488.6,
                "request_rate_rps": 14.5,
                "error_rate_pct": 0.0,
                "p95_latency_ms": 68.2,
            })
            # Also send to live backend if reachable
            try:
                requests.post(f"{backend_url}/api/v1/chaos/memory", json={"megabytes": 350, "duration_seconds": 60}, timeout=1)
            except Exception:
                pass
            st.toast("⚡ Injected Memory Leak Chaos!", icon="⚠️")

        if st.button("🔥 CPU Burn", use_container_width=True, help="Spike compute usage to 490m cores"):
            st.session_state.chaos_state = "CPU_SPIKE"
            st.session_state.simulated_metrics.update({
                "cpu_cores": 0.492,
                "memory_mb": 155.0,
                "request_rate_rps": 38.0,
                "error_rate_pct": 0.0,
                "p95_latency_ms": 290.0,
            })
            try:
                requests.post(f"{backend_url}/api/v1/chaos/cpu", json={"threads": 4, "duration_seconds": 30}, timeout=1)
            except Exception:
                pass
            st.toast("🔥 Injected CPU Exhaustion!", icon="🔥")

    with col_c2:
        if st.button("💥 500 Cascade", use_container_width=True, help="Trigger 45% HTTP 500 error cascade"):
            st.session_state.chaos_state = "HTTP_500_SPIKE"
            st.session_state.simulated_metrics.update({
                "cpu_cores": 0.135,
                "memory_mb": 142.0,
                "request_rate_rps": 16.0,
                "error_rate_pct": 46.5,
                "p95_latency_ms": 52.0,
            })
            try:
                requests.post(f"{backend_url}/api/v1/chaos/error-rate", json={"error_rate_pct": 45.0, "duration_seconds": 60}, timeout=1)
            except Exception:
                pass
            st.toast("💥 Injected HTTP 500 Error Cascade!", icon="💥")

        if st.button("⏱️ High Latency", use_container_width=True, help="Inject 500ms response degradation"):
            st.session_state.chaos_state = "LATENCY_SPIKE"
            st.session_state.simulated_metrics.update({
                "cpu_cores": 0.120,
                "memory_mb": 160.0,
                "request_rate_rps": 8.0,
                "error_rate_pct": 1.5,
                "p95_latency_ms": 540.0,
            })
            try:
                requests.post(f"{backend_url}/api/v1/chaos/latency", json={"latency_ms": 500, "duration_seconds": 60}, timeout=1)
            except Exception:
                pass
            st.toast("⏱️ Injected Network Latency Spike!", icon="⏱️")

    if st.button("🔄 Heal & Reset Cluster", use_container_width=True, type="primary"):
        st.session_state.chaos_state = "NORMAL"
        st.session_state.simulated_metrics.update({
            "cpu_cores": 0.105 + random.uniform(-0.02, 0.02),
            "memory_mb": 130.0 + random.uniform(-5, 5),
            "request_rate_rps": 10.0 + random.uniform(-2, 2),
            "error_rate_pct": 0.0,
            "p95_latency_ms": 22.0 + random.uniform(-3, 3),
        })
        try:
            requests.post(f"{backend_url}/api/v1/chaos/reset", timeout=1)
        except Exception:
            pass
        st.toast("✅ Cluster Healed & Restored to Steady State", icon="✅")

    st.markdown("---")
    auto_refresh = st.checkbox("Auto-Refresh Telemetry", value=True)
    refresh_rate = st.slider("Poll Interval (seconds)", 2, 15, 4)
    st.caption("Engine: Fine-Tuned Qwen2-7B AIOps")


# ---------------------------------------------------------
# Telemetry Retrieval
# ---------------------------------------------------------
current_metrics = st.session_state.simulated_metrics.copy()

if backend_mode == "Live Telemetry / Active Backend":
    snapshot_path = os.path.join(PROJECT_ROOT, "data", "telemetry_latest.json")
    if os.path.exists(snapshot_path):
        try:
            with open(snapshot_path, "r", encoding="utf-8") as f:
                snap = json.load(f)
            if snap.get("latest_metrics"):
                current_metrics = snap["latest_metrics"]
        except Exception:
            pass

# Add noise for realistic live telemetry
if st.session_state.chaos_state == "NORMAL":
    current_metrics["cpu_cores"] = max(0.02, round(current_metrics["cpu_cores"] + random.uniform(-0.01, 0.01), 4))
    current_metrics["memory_mb"] = max(50.0, round(current_metrics["memory_mb"] + random.uniform(-2.0, 2.0), 1))
    current_metrics["request_rate_rps"] = max(1.0, round(current_metrics["request_rate_rps"] + random.uniform(-0.5, 0.5), 1))

# Append to history
current_metrics["timestamp"] = time.strftime("%H:%M:%S")
st.session_state.history_buffer.append(current_metrics)
if len(st.session_state.history_buffer) > 40:
    st.session_state.history_buffer.pop(0)

history_df = pd.DataFrame(st.session_state.history_buffer)

# ---------------------------------------------------------
# Run Anomaly Detection & AI RCA Evaluation
# ---------------------------------------------------------
rca_report = engine.diagnose(current_metrics, recent_logs=[])
is_anomaly = rca_report.get("is_anomaly", False)


# ---------------------------------------------------------
# Top Header & Status Banner
# ---------------------------------------------------------
st.markdown(f"""
<div class="podguard-header">
    <div>
        <h1 class="podguard-title">🛡️ PodGuard AI</h1>
        <div class="podguard-subtitle">Autonomous Kubernetes SRE Telemetry Monitor & LLM Root Cause Intelligence</div>
    </div>
    <div>
        <span class="{'status-pill-alert' if is_anomaly else 'status-pill-ok'}">
            {'⚠️ ' + rca_report.get('anomaly_type').upper() + ' DETECTED' if is_anomaly else '● CLUSTER HEALTHY (STEADY-STATE)'}
        </span>
    </div>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# Section 1: KPI Vitals Bar
# ---------------------------------------------------------
col1, col2, col3, col4, col5 = st.columns(5)

cpu_val = current_metrics.get("cpu_cores", 0.0)
mem_val = current_metrics.get("memory_mb", 0.0)
err_val = current_metrics.get("error_rate_pct", 0.0)
lat_val = current_metrics.get("p95_latency_ms", 0.0)
pod_val = current_metrics.get("active_pods", 2)

with col1:
    cpu_pct = min(100, int((cpu_val / 0.5) * 100))
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">CPU Utilization</div>
        <div class="metric-value" style="color: {'#ef4444' if cpu_val > 0.4 else '#38bdf8'};">{cpu_val:.4f} <span style="font-size: 16px;">cores</span></div>
        <div class="metric-sub">{cpu_pct}% of 500m Limit</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    mem_pct = min(100, int((mem_val / 512.0) * 100))
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Memory Working Set</div>
        <div class="metric-value" style="color: {'#ef4444' if mem_val > 440 else '#38bdf8'};">{mem_val:.1f} <span style="font-size: 16px;">MB</span></div>
        <div class="metric-sub">{mem_pct}% of 512MiB Quota</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">HTTP 5xx Error Rate</div>
        <div class="metric-value" style="color: {'#ef4444' if err_val > 2.0 else '#10b981'};">{err_val:.1f} <span style="font-size: 16px;">%</span></div>
        <div class="metric-sub">{'CRITICAL' if err_val > 5 else 'OK (< 2% target)'}</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">P95 Response Latency</div>
        <div class="metric-value" style="color: {'#f59e0b' if lat_val > 250 else '#38bdf8'};">{lat_val:.1f} <span style="font-size: 16px;">ms</span></div>
        <div class="metric-sub">{'DEGRADED' if lat_val > 250 else 'Normal (< 100ms)'}</div>
    </div>
    """, unsafe_allow_html=True)

with col5:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Active Pods</div>
        <div class="metric-value" style="color: #a855f7;">{pod_val} <span style="font-size: 16px;">Replicas</span></div>
        <div class="metric-sub">Namespace: dev (aiops)</div>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------
# Section 2: Real-time Telemetry Trend Charts
# ---------------------------------------------------------
st.markdown("<br>", unsafe_allow_html=True)
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    fig_res = go.Figure()
    fig_res.add_trace(go.Scatter(
        x=history_df["timestamp"], y=history_df["memory_mb"],
        mode="lines+markers", name="Memory (MB)",
        line=dict(color="#38bdf8", width=3),
        fill="tozeroy", fillcolor="rgba(56, 189, 248, 0.1)"
    ))
    # Container Limit Line
    fig_res.add_hline(y=512, line_dash="dash", line_color="#ef4444", annotation_text="Pod Limit (512MB)", annotation_position="top right")
    fig_res.update_layout(
        title="<b>Memory Working Set Trajectory</b>",
        paper_bgcolor="rgba(15, 23, 42, 0.6)",
        plot_bgcolor="rgba(15, 23, 42, 0.2)",
        font=dict(color="#94a3b8"),
        margin=dict(l=20, r=20, t=40, b=20),
        height=260,
        yaxis=dict(gridcolor="rgba(255, 255, 255, 0.05)"),
        xaxis=dict(gridcolor="rgba(255, 255, 255, 0.05)")
    )
    st.plotly_chart(fig_res, use_container_width=True)

with col_chart2:
    fig_perf = go.Figure()
    fig_perf.add_trace(go.Scatter(
        x=history_df["timestamp"], y=history_df["cpu_cores"],
        mode="lines+markers", name="CPU (Cores)",
        line=dict(color="#c084fc", width=3),
        fill="tozeroy", fillcolor="rgba(192, 132, 252, 0.1)"
    ))
    fig_perf.add_hline(y=0.5, line_dash="dash", line_color="#ef4444", annotation_text="CPU Quota (0.5 cores)", annotation_position="top right")
    fig_perf.update_layout(
        title="<b>CPU Cores Saturation</b>",
        paper_bgcolor="rgba(15, 23, 42, 0.6)",
        plot_bgcolor="rgba(15, 23, 42, 0.2)",
        font=dict(color="#94a3b8"),
        margin=dict(l=20, r=20, t=40, b=20),
        height=260,
        yaxis=dict(gridcolor="rgba(255, 255, 255, 0.05)"),
        xaxis=dict(gridcolor="rgba(255, 255, 255, 0.05)")
    )
    st.plotly_chart(fig_perf, use_container_width=True)


# ---------------------------------------------------------
# Section 3: Fine-Tuned Qwen2 LLM Root Cause Analysis (RCA)
# ---------------------------------------------------------
st.markdown("### 🧠 **AI Root Cause Analysis & Automated Remediation**")

if is_anomaly:
    st.markdown(f"""
    <div class="rca-box">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <span style="font-size: 13px; font-weight: 700; color: #f87171; letter-spacing: 0.05em; text-transform: uppercase;">
                🚨 ACTIVE SRE INCIDENT • {rca_report.get('incident_id')}
            </span>
            <span style="background: #ef4444; color: #fff; padding: 4px 12px; border-radius: 6px; font-size: 12px; font-weight: 800;">
                {rca_report.get('severity')} SEVERITY
            </span>
        </div>
        <h2 style="margin: 0 0 10px 0; color: #f8fafc; font-size: 22px;">{rca_report.get('root_cause')}</h2>
        <p style="color: #cbd5e1; font-size: 14px; line-height: 1.6; margin-bottom: 16px;">
            <strong>Technical Failure Mechanism:</strong><br>{rca_report.get('mechanism')}
        </p>
        <div style="background: rgba(239, 68, 68, 0.1); border-left: 4px solid #ef4444; padding: 10px 14px; border-radius: 4px; margin-bottom: 16px; font-size: 13px; color: #fca5a5;">
            <strong>⚠️ Imminent Risk:</strong> {rca_report.get('imminent_risk')}
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_rca1, col_rca2 = st.columns([3, 2])
    with col_rca1:
        st.markdown("#### 🛠️ **Prescribed Mitigation Runbook**")
        for i, cmd in enumerate(rca_report.get("immediate_mitigation", [])):
            st.code(cmd, language="bash")

    with col_rca2:
        st.markdown("#### 🎯 **Permanent Architectural Resolution**")
        for res in rca_report.get("permanent_resolution", []):
            st.markdown(f"- {res}")

        if st.button("📧 Dispatch SRE Alert Email Now", type="secondary", use_container_width=True):
            success = dispatcher.send_rca_alert(rca_report, force=True)
            if success:
                st.success("Alert email successfully prepared & dispatched!")
            else:
                st.error("Failed to dispatch alert.")

else:
    st.markdown("""
    <div class="rca-box-normal">
        <h3 style="margin: 0 0 6px 0; color: #34d399; font-size: 18px;">✅ Steady-State Baseline Normal</h3>
        <p style="color: #94a3b8; font-size: 14px; margin: 0;">
            Isolation Forest ML and SRE boundary heuristics indicate all pod containers are operating inside safe operational bounds.
            Trigger a chaos fault from the sidebar to observe the AI Root Cause Analysis engine in action.
        </p>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------
# Section 4: Incident History Archive
# ---------------------------------------------------------
st.markdown("<br>", unsafe_allow_html=True)
with st.expander("📁 **Incident Reports & Post-Mortem Audit Archive**", expanded=False):
    reports_dir = os.path.join(PROJECT_ROOT, "data", "rca_reports")
    report_files = sorted(glob.glob(os.path.join(reports_dir, "INC-*.md")), reverse=True)
    if report_files:
        selected_file = st.selectbox("Select Incident Post-Mortem to View", report_files, format_func=lambda x: os.path.basename(x))
        if selected_file and os.path.exists(selected_file):
            with open(selected_file, "r", encoding="utf-8") as f:
                content = f.read()
            st.markdown(content)
    else:
        st.info("No saved incident reports found in data/rca_reports/.")


# ---------------------------------------------------------
# Auto-refresh loop
# ---------------------------------------------------------
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
