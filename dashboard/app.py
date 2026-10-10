import os
import sys
import time
import json
import glob
import random
import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Configure project root
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

# Custom Catchy Cyberpunk / Glassmorphism CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;800&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    code, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Main background */
    .stApp {
        background: radial-gradient(circle at 12% 10%, #0d1527 0%, #060913 100%);
        color: #f1f5f9;
    }

    /* Header styling */
    .podguard-header {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.75) 0%, rgba(15, 23, 42, 0.95) 100%);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 16px;
        padding: 22px 28px;
        margin-bottom: 22px;
        box-shadow: 0 10px 30px -10px rgba(14, 165, 233, 0.25);
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
        box-shadow: 0 0 15px rgba(16, 185, 129, 0.25);
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
        animation: pulse 1.6s infinite;
        box-shadow: 0 0 20px rgba(239, 68, 68, 0.35);
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.85; transform: scale(1.02); }
    }

    /* Metric cards */
    .metric-card {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 16px 18px;
        backdrop-filter: blur(8px);
        transition: transform 0.2s ease, border-color 0.2s ease;
        margin-bottom: 8px;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(56, 189, 248, 0.4);
    }
    .metric-label {
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94a3b8;
        margin-bottom: 4px;
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
        background: linear-gradient(180deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%);
        border: 1px solid #ef4444;
        border-radius: 14px;
        padding: 22px;
        margin-top: 14px;
        margin-bottom: 14px;
        box-shadow: 0 10px 25px -5px rgba(239, 68, 68, 0.25);
    }
    .rca-box-normal {
        background: linear-gradient(180deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
        border: 1px solid rgba(16, 185, 129, 0.4);
        border-radius: 14px;
        padding: 22px;
        margin-top: 14px;
        margin-bottom: 14px;
    }

    /* Tabs custom aesthetic */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        padding-bottom: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        background: rgba(30, 41, 59, 0.4);
        border-radius: 8px 8px 0 0;
        padding: 8px 18px;
        color: #94a3b8;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(56, 189, 248, 0.15) !important;
        color: #38bdf8 !important;
        border-bottom: 2px solid #38bdf8 !important;
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

if "last_reported_anomaly" not in st.session_state:
    st.session_state.last_reported_anomaly = "normal"


# ---------------------------------------------------------
# Sidebar Controls & Live Chaos Generator
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("### 🎛️ **PodGuard SRE Controls**")
    backend_mode = st.radio(
        "Telemetry Stream Mode",
        ["Interactive Chaos Simulator", "Live File / Telemetry Backend"],
        index=0,
        help="Switch between live Prometheus polling and interactive simulation mode"
    )

    backend_url = st.text_input("FastAPI Backend URL", value="http://localhost:8000")

    st.markdown("---")
    st.markdown("### ⚡ **Chaos Fault Injection Lab**")
    st.caption("Click to trigger simulated production incidents & test AI detection:")

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        if st.button("💧 Memory Leak", width="stretch", help="Simulate memory leak climbing to 488 MB (near 512 MB limit)"):
            st.session_state.chaos_state = "MEMORY_LEAK"
            st.session_state.simulated_metrics.update({
                "cpu_cores": 0.178,
                "memory_mb": 488.6,
                "request_rate_rps": 14.5,
                "error_rate_pct": 0.0,
                "p95_latency_ms": 68.2,
            })
            try:
                requests.post(f"{backend_url}/api/v1/chaos/memory", json={"megabytes": 350, "duration_seconds": 60}, timeout=1)
            except Exception:
                pass
            st.toast("⚡ Injected Memory Leak Chaos!", icon="⚠️")

        if st.button("🔥 CPU Exhaust", width="stretch", help="Spike compute usage to 492m cores (quota 500m)"):
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
            st.toast("🔥 Injected CPU Saturation Spike!", icon="🔥")

    with col_c2:
        if st.button("💥 500 Cascade", width="stretch", help="Trigger 46.5% HTTP 500 server error rate"):
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

        if st.button("⏱️ High Latency", width="stretch", help="Inject 540ms response latency degradation"):
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

    if st.button("🔄 Heal & Reset Cluster", width="stretch", type="primary"):
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
        st.toast("✅ Cluster Restored to Steady-State Baseline", icon="✅")

    st.markdown("---")
    auto_refresh = st.checkbox("Live Auto-Refresh", value=True)
    refresh_rate = st.slider("Poll Interval (seconds)", 2, 15, 4)
    st.caption("Engine: Fine-Tuned Qwen2-7B AIOps")


# ---------------------------------------------------------
# Telemetry Data Gathering & History Management
# ---------------------------------------------------------
current_metrics = st.session_state.simulated_metrics.copy()

if backend_mode == "Live File / Telemetry Backend":
    snapshot_path = os.path.join(PROJECT_ROOT, "data", "telemetry_latest.json")
    if os.path.exists(snapshot_path):
        try:
            with open(snapshot_path, "r", encoding="utf-8") as f:
                snap = json.load(f)
            if snap.get("latest_metrics"):
                current_metrics = snap["latest_metrics"]
        except Exception:
            pass

# Add subtle telemetry fluctuations for realistic monitoring
if st.session_state.chaos_state == "NORMAL":
    current_metrics["cpu_cores"] = max(0.02, round(current_metrics["cpu_cores"] + random.uniform(-0.008, 0.008), 4))
    current_metrics["memory_mb"] = max(50.0, round(current_metrics["memory_mb"] + random.uniform(-1.5, 1.5), 1))
    current_metrics["request_rate_rps"] = max(1.0, round(current_metrics["request_rate_rps"] + random.uniform(-0.4, 0.4), 1))

# Append to history
current_metrics["timestamp"] = time.strftime("%H:%M:%S")
st.session_state.history_buffer.append(current_metrics)
if len(st.session_state.history_buffer) > 40:
    st.session_state.history_buffer.pop(0)

history_df = pd.DataFrame(st.session_state.history_buffer)

# Determine if state transitioned into an anomaly to control disk/email triggers
raw_eval = engine.detector.evaluate_vector(current_metrics)
new_anomaly_state = raw_eval.anomaly_type
should_persist = (new_anomaly_state != "normal" and new_anomaly_state != st.session_state.last_reported_anomaly)

rca_report = engine.diagnose(
    current_metrics,
    recent_logs=[],
    history_df=history_df,
    persist_incident=should_persist,
    dispatch_email=should_persist
)
st.session_state.last_reported_anomaly = new_anomaly_state
is_anomaly = rca_report.get("is_anomaly", False)


# ---------------------------------------------------------
# Header & Global Status Banner
# ---------------------------------------------------------
st.markdown(f"""
<div class="podguard-header">
    <div>
        <h1 class="podguard-title">🛡️ PodGuard AI</h1>
        <div class="podguard-subtitle">Autonomous Kubernetes SRE Telemetry Monitor & LLM Root Cause Intelligence</div>
    </div>
    <div>
        <span class="{'status-pill-alert' if is_anomaly else 'status-pill-ok'}">
            {'⚠️ ' + rca_report.get('anomaly_type', '').upper() + ' ACTIVE' if is_anomaly else '● CLUSTER HEALTHY (STEADY-STATE)'}
        </span>
    </div>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# Top Level KPI Vitals Bar
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
        <div class="metric-label">CPU Cores</div>
        <div class="metric-value" style="color: {'#ef4444' if cpu_val > 0.4 else '#38bdf8'};">{cpu_val:.4f}</div>
        <div class="metric-sub">{cpu_pct}% of 500m Limit</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    mem_pct = min(100, int((mem_val / 512.0) * 100))
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Memory RSS</div>
        <div class="metric-value" style="color: {'#ef4444' if mem_val > 440 else '#38bdf8'};">{mem_val:.1f} MB</div>
        <div class="metric-sub">{mem_pct}% of 512MiB Quota</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">HTTP 5xx Errors</div>
        <div class="metric-value" style="color: {'#ef4444' if err_val > 2.0 else '#10b981'};">{err_val:.1f}%</div>
        <div class="metric-sub">{'CRITICAL SPIKE' if err_val > 5 else 'Steady-State (< 2%)'}</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">P95 Latency</div>
        <div class="metric-value" style="color: {'#f59e0b' if lat_val > 250 else '#38bdf8'};">{lat_val:.1f} ms</div>
        <div class="metric-sub">{'DEGRADED' if lat_val > 250 else 'Normal (< 40ms)'}</div>
    </div>
    """, unsafe_allow_html=True)

with col5:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Active Pods</div>
        <div class="metric-value" style="color: #c084fc;">{pod_val} Replicas</div>
        <div class="metric-sub">Namespace: dev (aiops)</div>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------
# PodGuard Tabbed Navigation
# ---------------------------------------------------------
tab_monitor, tab_playground, tab_llm, tab_reports, tab_email = st.tabs([
    "🚨 Live Incident Monitor",
    "🧪 Interactive AI Playground",
    "🧠 Fine-Tuned LLM & ChatML",
    "📁 Incident Post-Mortem Archive",
    "📧 Automated Alert Server"
])


# =========================================================
# TAB 1: Live SRE Incident Monitor
# =========================================================
with tab_monitor:
    st.markdown("<br>", unsafe_allow_html=True)
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        fig_mem = go.Figure()
        fig_mem.add_trace(go.Scatter(
            x=history_df["timestamp"], y=history_df["memory_mb"],
            mode="lines+markers", name="Memory (MB)",
            line=dict(color="#38bdf8", width=3),
            fill="tozeroy", fillcolor="rgba(56, 189, 248, 0.12)"
        ))
        fig_mem.add_hline(y=512, line_dash="dash", line_color="#ef4444", annotation_text="Container Limit (512MB)", annotation_position="top right")
        fig_mem.update_layout(
            title="<b>Memory Working Set Trajectory</b>",
            paper_bgcolor="rgba(15, 23, 42, 0.6)",
            plot_bgcolor="rgba(15, 23, 42, 0.2)",
            font=dict(color="#94a3b8"),
            margin=dict(l=20, r=20, t=40, b=20),
            height=250,
            yaxis=dict(gridcolor="rgba(255, 255, 255, 0.05)"),
            xaxis=dict(gridcolor="rgba(255, 255, 255, 0.05)")
        )
        st.plotly_chart(fig_mem, width="stretch")

    with col_chart2:
        fig_cpu = go.Figure()
        fig_cpu.add_trace(go.Scatter(
            x=history_df["timestamp"], y=history_df["cpu_cores"],
            mode="lines+markers", name="CPU (Cores)",
            line=dict(color="#c084fc", width=3),
            fill="tozeroy", fillcolor="rgba(192, 132, 252, 0.12)"
        ))
        fig_cpu.add_hline(y=0.5, line_dash="dash", line_color="#ef4444", annotation_text="Quota (0.5 cores)", annotation_position="top right")
        fig_cpu.update_layout(
            title="<b>CPU Cores Saturation</b>",
            paper_bgcolor="rgba(15, 23, 42, 0.6)",
            plot_bgcolor="rgba(15, 23, 42, 0.2)",
            font=dict(color="#94a3b8"),
            margin=dict(l=20, r=20, t=40, b=20),
            height=250,
            yaxis=dict(gridcolor="rgba(255, 255, 255, 0.05)"),
            xaxis=dict(gridcolor="rgba(255, 255, 255, 0.05)")
        )
        st.plotly_chart(fig_cpu, width="stretch")

    # Active Incident Diagnosis
    st.markdown("### 🧠 **Autonomous RCA Intelligence Feed**")

    if is_anomaly:
        st.markdown(f"""
        <div class="rca-box">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <span style="font-size: 13px; font-weight: 700; color: #f87171; letter-spacing: 0.05em; text-transform: uppercase;">
                    🚨 ACTIVE INCIDENT • {rca_report.get('incident_id')}
                </span>
                <span style="background: #ef4444; color: #fff; padding: 4px 12px; border-radius: 6px; font-size: 12px; font-weight: 800;">
                    {rca_report.get('severity')} SEVERITY
                </span>
            </div>
            <h2 style="margin: 0 0 10px 0; color: #f8fafc; font-size: 22px;">{rca_report.get('root_cause')}</h2>
            <p style="color: #cbd5e1; font-size: 14px; line-height: 1.6; margin-bottom: 14px;">
                <strong>Technical Mechanism:</strong><br>{rca_report.get('mechanism')}
            </p>
            <div style="background: rgba(239, 68, 68, 0.12); border-left: 4px solid #ef4444; padding: 10px 14px; border-radius: 4px; font-size: 13px; color: #fca5a5;">
                <strong>⚠️ Imminent Risk:</strong> {rca_report.get('imminent_risk')}
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_mit, col_perm = st.columns([3, 2])
        with col_mit:
            st.markdown("#### 🛠️ **Mitigation Runbook Commands**")
            for cmd in rca_report.get("immediate_mitigation", []):
                st.code(cmd, language="bash")

        with col_perm:
            st.markdown("#### 🎯 **Architectural Fixes**")
            for res in rca_report.get("permanent_resolution", []):
                st.markdown(f"- {res}")

            if st.button("📧 Dispatch Immediate SRE Alert Email", type="secondary", width="stretch"):
                success = dispatcher.send_rca_alert(rca_report, force=True)
                if success:
                    st.success("✅ Email alert successfully rendered and dispatched!")
                else:
                    st.error("Failed to dispatch alert.")

    else:
        st.markdown("""
        <div class="rca-box-normal">
            <h3 style="margin: 0 0 6px 0; color: #34d399; font-size: 18px;">✅ Steady-State Baseline Normal</h3>
            <p style="color: #94a3b8; font-size: 14px; margin: 0;">
                All metrics are operating within safe bounds.
                Use the sidebar <strong>Chaos Fault Injection</strong> buttons or the <strong>Interactive AI Playground</strong> to test custom incident scenarios.
            </p>
        </div>
        """, unsafe_allow_html=True)


# =========================================================
# TAB 2: Interactive AI SRE Playground (Custom Tester)
# =========================================================
with tab_playground:
    st.markdown("### 🧪 **Interactive AI Diagnostic Lab**")
    st.caption("Freely adjust container metrics and error traces to evaluate the Anomaly Detector and Qwen2 RCA Model live.")

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        p_cpu = st.slider("Container CPU Usage (cores)", 0.01, 1.0, 0.485, 0.005)
        p_mem = st.slider("Memory RSS (MB - Limit 512MB)", 50.0, 600.0, 495.0, 1.0)
        p_pods = st.slider("Active Pod Replicas", 1, 8, 2)

    with col_p2:
        p_err = st.slider("HTTP 5xx Error Rate (%)", 0.0, 100.0, 0.0, 0.5)
        p_lat = st.slider("P95 Latency (ms)", 5.0, 2000.0, 45.0, 5.0)
        p_rps = st.slider("Throughput (req/s)", 1.0, 200.0, 18.0, 1.0)

    st.markdown("#### 📝 **Correlated Container Logs (Optional)**")
    sample_log_choice = st.selectbox(
        "Load Pre-Configured Outage Log Template:",
        [
            "Custom Log Trace",
            "OOM Killer / Memory Leak Trace",
            "Database Connection Pool Saturation",
            "Cgroup CPU Throttling Warning",
            "Uncaught Null Pointer Exception (500 Cascade)"
        ]
    )

    default_log_text = ""
    if sample_log_choice == "OOM Killer / Memory Leak Trace":
        default_log_text = (
            "[21:30:10] [WARNING] app.cache: Memory cache size exceeded 450MB.\n"
            "[21:30:14] [ERROR] kernel: Task worker invocation invoked oom-killer: gfp_mask=0x100cca(GFP_HIGHUSER_MOVABLE)\n"
            "[21:30:15] [FATAL] app.core: Pod received SIGKILL from kubelet (ExitCode: 137, OOMKilled)."
        )
    elif sample_log_choice == "Database Connection Pool Saturation":
        default_log_text = (
            "[21:30:10] [WARNING] db.pool: Active DB connections reached pool capacity (50/50).\n"
            "[21:30:12] [ERROR] sqlalchemy.exc.TimeoutError: QueuePool limit of size 50 overflow 10 reached, connection timed out.\n"
            "[21:30:15] [ERROR] uvicorn.error: HTTP 504 Gateway Timeout while waiting for DB connection."
        )
    elif sample_log_choice == "Cgroup CPU Throttling Warning":
        default_log_text = (
            "[21:30:05] [INFO] worker.math: Heavy batch computation thread started.\n"
            "[21:30:10] [WARNING] cgroup.cpu: CFS quota throttled 85% of CPU periods over 10s.\n"
            "[21:30:12] [WARNING] kubelet: Node compute pressure detected."
        )
    elif sample_log_choice == "Uncaught Null Pointer Exception (500 Cascade)":
        default_log_text = (
            "[21:30:01] [ERROR] app.routes: AttributeError: 'NoneType' object has no attribute 'get_user_account'\n"
            "[21:30:02] [ERROR] starlette.middleware: Unhandled 500 Internal Server Error in /api/v1/checkout\n"
            "[21:30:04] [ERROR] starlette.middleware: Unhandled 500 Internal Server Error in /api/v1/checkout"
        )

    user_logs_input = st.text_area("Container Error Logs (one line per entry):", value=default_log_text, height=120)

    if st.button("⚡ Execute Qwen2 AI Diagnosis & Generate RCA", type="primary", width="stretch"):
        test_vector = {
            "cpu_cores": p_cpu,
            "memory_mb": p_mem,
            "request_rate_rps": p_rps,
            "error_rate_pct": p_err,
            "p95_latency_ms": p_lat,
            "active_pods": p_pods
        }

        # Format input logs
        parsed_logs = []
        if user_logs_input.strip():
            for line in user_logs_input.strip().split("\n"):
                if line.strip():
                    parsed_logs.append({"timestamp": time.strftime("%H:%M:%S"), "level": "ERROR", "message": line.strip()})

        with st.spinner("🤖 Running AI Anomaly Detection & Qwen2 SRE Analysis..."):
            playground_report = engine.diagnose(
                test_vector,
                recent_logs=parsed_logs,
                persist_incident=True,
                dispatch_email=False
            )

        st.success(f"Diagnosis Complete! Incident Tag: {playground_report['incident_id']}")

        # Show Output Box
        p_is_anom = playground_report["is_anomaly"]
        st.markdown(f"""
        <div class="{'rca-box' if p_is_anom else 'rca-box-normal'}">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <span style="font-weight: 700; color: {'#f87171' if p_is_anom else '#34d399'};">
                    CLASSIFICATION: {playground_report['anomaly_type'].upper()} ({playground_report.get('severity', 'LOW')} SEVERITY)
                </span>
                <span style="font-size: 13px; color: #94a3b8;">
                    Confidence: {playground_report.get('confidence', 1.0):.2f}
                </span>
            </div>
            <h3 style="margin: 0 0 10px 0; color: #f8fafc;">{playground_report.get('root_cause')}</h3>
            <p style="color: #cbd5e1; font-size: 14px; margin-bottom: 12px;">{playground_report.get('mechanism')}</p>
            <div style="font-size: 13px; color: #fca5a5; margin-bottom: 10px;">
                <strong>Imminent Risk:</strong> {playground_report.get('imminent_risk')}
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_p_res1, col_p_res2 = st.columns(2)
        with col_p_res1:
            st.markdown("##### 🛠️ Prescribed Mitigation Runbook:")
            for cmd in playground_report.get("immediate_mitigation", []):
                st.code(cmd, language="bash")

        with col_p_res2:
            st.markdown("##### 🎯 Architectural Recommendations:")
            for r in playground_report.get("permanent_resolution", []):
                st.markdown(f"- {r}")


# =========================================================
# TAB 3: Fine-Tuned LLM & ChatML Inspector
# =========================================================
with tab_llm:
    st.markdown("### 🧠 **Fine-Tuned LLM Architecture & ChatML Engine**")
    st.caption("Deep inspection of the fine-tuned Qwen2-7B AIOps model weights and ChatML formatting.")

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Base Architecture</div>
            <div class="metric-value" style="color: #38bdf8;">Qwen2-7B</div>
            <div class="metric-sub">Causal Language Model</div>
        </div>
        """, unsafe_allow_html=True)
    with col_m2:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Parameters</div>
            <div class="metric-value" style="color: #818cf8;">7.61 Billion</div>
            <div class="metric-sub">28 Hidden Layers, 3584 Dim</div>
        </div>
        """, unsafe_allow_html=True)
    with col_m3:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Context Window</div>
            <div class="metric-value" style="color: #c084fc;">32,768</div>
            <div class="metric-sub">Full Sequence Tokens</div>
        </div>
        """, unsafe_allow_html=True)
    with col_m4:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Model Weights Size</div>
            <div class="metric-value" style="color: #34d399;">15.2 GB</div>
            <div class="metric-sub">4 Shards (SafeTensors)</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 💬 **Live ChatML Prompt Generation Inspector**")
    st.caption("PodGuard dynamically transforms Kubernetes metrics and log traces into the exact ChatML format expected by the model:")

    # Get prompt from inference engine
    prompt_sample = engine.llm.build_chatml_prompt(
        current_metrics,
        recent_logs=[
            {"timestamp": time.strftime("%H:%M:%S"), "level": "WARNING", "message": "High allocation detected in container memory pool."},
            {"timestamp": time.strftime("%H:%M:%S"), "level": "ERROR", "message": "Health check degraded: pod responding > 300ms."}
        ],
        anomaly_type=rca_report.get("anomaly_type", "normal")
    )

    st.code(prompt_sample, language="markdown")

    st.markdown("#### 📦 **Model Storage & Verification**")
    model_dir = os.path.join(PROJECT_ROOT, "telemetry_rca_model")
    if os.path.exists(model_dir):
        files_in_model = sorted(os.listdir(model_dir))
        file_stats = []
        for f in files_in_model:
            fp = os.path.join(model_dir, f)
            size_mb = os.path.getsize(fp) / (1024 * 1024)
            file_stats.append({"File": f, "Size (MB)": f"{size_mb:.2f} MB", "Type": "Weights Shard" if f.endswith(".safetensors") else "Configuration / Tokenizer"})
        st.dataframe(pd.DataFrame(file_stats), width="stretch")
    else:
        st.warning("Model directory not detected on disk.")


# =========================================================
# TAB 4: Incident Post-Mortem Archive
# =========================================================
with tab_reports:
    st.markdown("### 📁 **Historical Incident Post-Mortems**")
    st.caption("Audit trail of all autonomous incident post-mortems generated by PodGuard.")

    reports_dir = os.path.join(PROJECT_ROOT, "data", "rca_reports")
    report_files = sorted(glob.glob(os.path.join(reports_dir, "INC-*.md")), reverse=True)

    if report_files:
        selected_file = st.selectbox(
            "Select Incident Report to Inspect:",
            report_files,
            format_func=lambda x: f"📄 {os.path.basename(x)}"
        )
        if selected_file and os.path.exists(selected_file):
            with open(selected_file, "r", encoding="utf-8") as f:
                content = f.read()

            st.download_button(
                "⬇️ Download Markdown Post-Mortem",
                data=content,
                file_name=os.path.basename(selected_file),
                mime="text/markdown"
            )
            st.markdown("---")
            st.markdown(content)
    else:
        st.info("No saved incident reports found in data/rca_reports/.")


# =========================================================
# TAB 5: Automated Alert Server
# =========================================================
with tab_email:
    st.markdown("### 📧 **Automated SRE Email Alert Dispatcher**")
    st.caption("Configured email dispatcher with anti-spam cooldown and rich HTML incident formatting.")

    col_e1, col_e2, col_e3 = st.columns(3)
    with col_e1:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Alert Target</div>
            <div class="metric-value" style="font-size: 18px; color: #38bdf8;">sre-oncall@company.com</div>
            <div class="metric-sub">Configurable via TELEMETRY_ALERT_RECIPIENT</div>
        </div>
        """, unsafe_allow_html=True)
    with col_e2:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Anti-Spam Throttling</div>
            <div class="metric-value" style="font-size: 18px; color: #10b981;">300 Seconds</div>
            <div class="metric-sub">Cooldown per Anomaly Category</div>
        </div>
        """, unsafe_allow_html=True)
    with col_e3:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Delivery Mode</div>
            <div class="metric-value" style="font-size: 18px; color: #c084fc;">SMTP / HTML Dry-Run</div>
            <div class="metric-sub">Zero-Crash Resilient Dispatcher</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚀 Trigger Test Alert Dispatch", type="primary", width="stretch"):
        test_rca = {
            "incident_id": f"INC-TEST-{int(time.time())}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "anomaly_type": "memory_leak",
            "severity": "CRITICAL",
            "root_cause": "Container Memory Leak / Impending OOMKilled Event",
            "mechanism": "Heap allocation climbing continuously past safe operational limits (488 MB / 512 MB).",
            "imminent_risk": "Imminent Pod OOMKilled by Linux kernel (ExitCode 137), triggering cluster cascading failure.",
            "immediate_mitigation": [
                "kubectl rollout restart deployment/aiops-backend -n dev",
                "kubectl top pod -l app=aiops-backend -n dev"
            ],
            "permanent_resolution": [
                "Audit uncollected memory caches and background asyncio tasks.",
                "Adjust pod memory limit from 512Mi to 1Gi in deployment manifests."
            ],
            "telemetry_evidence": {
                "cpu_cores": "0.1780 cores",
                "memory_mb": "488.6 MB",
                "error_rate_pct": "0.0%",
                "p95_latency_ms": "68.2 ms",
                "active_pods": 2
            }
        }
        sent = dispatcher.send_rca_alert(test_rca, force=True)
        if sent:
            st.success("✅ Test Alert generated and saved to data/rca_reports/!")
        else:
            st.error("Failed to trigger alert.")

    # Show preview of latest HTML email
    st.markdown("#### 📬 **Rendered HTML Email Preview (What SREs Receive):**")
    html_emails = sorted(glob.glob(os.path.join(reports_dir, "email_*.html")), reverse=True)
    if html_emails:
        with open(html_emails[0], "r", encoding="utf-8") as f:
            email_html = f.read()
        st.components.v1.html(email_html, height=520, scrolling=True)
    else:
        st.info("No generated email templates found yet. Click 'Trigger Test Alert Dispatch' above to generate one!")


# ---------------------------------------------------------
# Auto-refresh loop
# ---------------------------------------------------------
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
