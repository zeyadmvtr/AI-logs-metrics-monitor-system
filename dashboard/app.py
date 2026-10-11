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
# Page Configuration & Metadata
# ---------------------------------------------------------
st.set_page_config(
    page_title="AnomIQ — Autonomous AIOps Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------
# AnomIQ Design System CSS (Obsidian Canvas, Cyan & Blue Glows)
# ---------------------------------------------------------
st.html("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    :root {
        --bg-canvas: #05070d;
        --bg-canvas-subtle: #080b13;
        --bg-surface: #0c101b;
        --bg-surface-elevated: #111726;
        --bg-card: rgba(13, 18, 30, 0.75);
        --bg-card-hover: rgba(18, 25, 42, 0.9);
        --bg-glass-input: rgba(10, 14, 24, 0.8);

        --accent-cyan: #06b6d4;
        --accent-cyan-bright: #38bdf8;
        --accent-cyan-glow: rgba(56, 189, 248, 0.25);
        --accent-blue: #3b82f6;
        --accent-blue-deep: #1d4ed8;
        --accent-violet: #8b5cf6;
        --accent-violet-glow: rgba(139, 92, 246, 0.2);

        --status-emerald: #10b981;
        --status-emerald-bright: #34d399;
        --status-emerald-bg: rgba(16, 185, 129, 0.12);
        --status-emerald-border: rgba(16, 185, 129, 0.28);

        --status-rose: #f43f5e;
        --status-rose-bright: #fb7185;
        --status-rose-bg: rgba(244, 63, 94, 0.14);
        --status-rose-border: rgba(244, 63, 94, 0.35);

        --status-amber: #f59e0b;
        --status-amber-bright: #fbbf24;

        --text-primary: #f8fafc;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        --border-subtle: rgba(255, 255, 255, 0.08);
        --border-glass: rgba(255, 255, 255, 0.12);
        --border-glow-cyan: rgba(56, 189, 248, 0.35);

        --font-sans: 'Plus Jakarta Sans', sans-serif;
        --font-mono: 'JetBrains Mono', monospace;
    }

    html, body, [class*="css"], .stApp {
        font-family: var(--font-sans);
        background-color: var(--bg-canvas) !important;
        color: var(--text-primary);
    }
    code, pre {
        font-family: var(--font-mono) !important;
    }

    /* Ambient Background Glows */
    .ambient-glow {
        position: fixed;
        border-radius: 50%;
        pointer-events: none;
        filter: blur(140px);
        z-index: 0;
        opacity: 0.35;
    }
    .glow-top-left {
        top: -140px;
        left: -100px;
        width: 650px;
        height: 650px;
        background: radial-gradient(circle, rgba(56, 189, 248, 0.25) 0%, rgba(37, 99, 235, 0.12) 50%, transparent 70%);
    }
    .glow-top-right {
        top: -80px;
        right: -80px;
        width: 600px;
        height: 600px;
        background: radial-gradient(circle, rgba(139, 92, 246, 0.18) 0%, rgba(59, 130, 246, 0.1) 60%, transparent 70%);
    }
    .glow-center-navy {
        top: 40%;
        left: 25%;
        width: 750px;
        height: 750px;
        background: radial-gradient(circle, rgba(6, 182, 212, 0.12) 0%, transparent 70%);
    }

    /* SaaS Grid Pattern */
    .saas-grid-pattern {
        position: fixed;
        inset: 0;
        pointer-events: none;
        z-index: 0;
        background-image: 
            linear-gradient(to right, rgba(255, 255, 255, 0.02) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
        background-size: 64px 64px;
        mask-image: radial-gradient(ellipse at 50% 15%, black 40%, transparent 85%);
    }

    /* AnomIQ Header */
    .site-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 16px 28px;
        margin-bottom: 24px;
        background: rgba(7, 10, 17, 0.88);
        backdrop-filter: blur(24px);
        border: 1px solid var(--border-subtle);
        border-radius: 16px;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.6);
        position: relative;
        z-index: 10;
    }
    .header-left {
        display: flex;
        align-items: center;
        gap: 18px;
    }
    .brand-icon-box {
        width: 42px;
        height: 42px;
        border-radius: 12px;
        background: linear-gradient(135deg, rgba(56, 189, 248, 0.25), rgba(139, 92, 246, 0.3));
        border: 1px solid rgba(56, 189, 248, 0.4);
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.25);
    }
    .brand-name {
        font-size: 22px;
        font-weight: 800;
        letter-spacing: -0.5px;
        color: #fff;
        line-height: 1.1;
    }
    .brand-highlight {
        background: linear-gradient(135deg, var(--accent-cyan-bright), var(--accent-blue));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .brand-tagline {
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.5px;
        color: var(--text-muted);
        text-transform: uppercase;
        margin-top: 2px;
    }

    /* Beacons */
    .status-beacon-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        position: relative;
    }
    .beacon-cyan {
        background: var(--accent-cyan-bright);
        box-shadow: 0 0 10px var(--accent-cyan-bright);
    }
    .beacon-rose {
        background: var(--status-rose-bright);
        box-shadow: 0 0 12px var(--status-rose-bright);
        animation: pulseRose 1.5s infinite;
    }
    .beacon-emerald {
        background: var(--status-emerald-bright);
        box-shadow: 0 0 10px var(--status-emerald-bright);
    }
    @keyframes pulseRose {
        0%, 100% { transform: scale(1); opacity: 1; }
        50% { transform: scale(1.4); opacity: 0.7; }
    }

    /* Cards */
    .saas-card {
        background: var(--bg-card);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid var(--border-subtle);
        border-radius: 18px;
        padding: 22px;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.6);
        position: relative;
        overflow: hidden;
        margin-bottom: 18px;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .saas-card:hover {
        background: var(--bg-card-hover);
        border-color: rgba(56, 189, 248, 0.3);
        transform: translateY(-2px);
    }
    .card-ambient-highlight {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent 5%, rgba(56, 189, 248, 0.45) 30%, rgba(59, 130, 246, 0.45) 70%, transparent 95%);
        pointer-events: none;
    }
    .card-header-clean {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 14px;
    }
    .card-title {
        font-size: 16px;
        font-weight: 700;
        color: #fff;
        letter-spacing: -0.2px;
    }
    .card-subtitle {
        font-size: 13px;
        color: var(--text-muted);
        margin-top: 2px;
    }

    /* KPI Cards */
    .kpi-clean-card {
        padding: 22px 24px;
        border-radius: 16px;
        min-height: 145px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .kpi-header-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .kpi-label {
        font-size: 12px;
        font-weight: 700;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }
    .kpi-pill-badge {
        font-size: 11px;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 6px;
    }
    .pill-rose {
        background: var(--status-rose-bg);
        color: var(--status-rose-bright);
        border: 1px solid var(--status-rose-border);
    }
    .pill-cyan {
        background: rgba(56, 189, 248, 0.12);
        color: var(--accent-cyan-bright);
        border: 1px solid rgba(56, 189, 248, 0.28);
    }
    .pill-emerald {
        background: var(--status-emerald-bg);
        color: var(--status-emerald-bright);
        border: 1px solid var(--status-emerald-border);
    }
    .kpi-number-row {
        display: flex;
        align-items: baseline;
        gap: 10px;
        margin: 10px 0 4px;
    }
    .kpi-value-huge {
        font-size: 34px;
        font-weight: 800;
        color: #fff;
        letter-spacing: -1px;
        line-height: 1;
    }
    .kpi-meta-text {
        font-size: 13px;
        color: var(--text-muted);
    }
    .kpi-footer-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 12px;
        color: var(--text-secondary);
        border-top: 1px solid var(--border-subtle);
        padding-top: 10px;
        margin-top: 8px;
    }

    /* AI Pipeline Track */
    .ai-pipeline-track {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-bottom: 24px;
    }
    .pipeline-step-card {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 16px;
        padding: 20px;
        position: relative;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 160px;
    }
    .pipeline-step-card.active-focus {
        border-color: rgba(56, 189, 248, 0.45);
        background: rgba(14, 22, 38, 0.85);
        box-shadow: 0 0 25px rgba(56, 189, 248, 0.18);
    }
    .step-num-pill {
        font-size: 10px;
        font-weight: 800;
        color: var(--accent-cyan-bright);
        background: rgba(56, 189, 248, 0.12);
        padding: 3px 8px;
        border-radius: 6px;
    }
    .step-stage-name {
        font-size: 14px;
        font-weight: 700;
        color: #fff;
        margin: 8px 0 4px;
    }
    .step-stage-desc {
        font-size: 12px;
        color: var(--text-secondary);
        line-height: 1.45;
    }

    /* Service Grid */
    .service-health-grid {
        display: grid;
        grid-template-columns: repeat(6, 1fr);
        gap: 12px;
        margin-bottom: 24px;
    }
    .svc-card {
        padding: 14px 16px;
        border-radius: 12px;
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        display: flex;
        flex-direction: column;
        gap: 6px;
    }
    .svc-card.alert {
        border-color: var(--status-rose-border);
        background: rgba(244, 63, 94, 0.08);
    }
    .svc-name {
        font-size: 12px;
        font-weight: 700;
        color: #fff;
    }
    .svc-latency {
        font-size: 11px;
        color: var(--text-muted);
    }

    /* Node Chips */
    .node-matrix-container {
        display: grid;
        grid-template-columns: repeat(8, 1fr);
        gap: 10px;
        margin: 14px 0;
    }
    .node-chip-box {
        aspect-ratio: 1.15;
        border-radius: 8px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid var(--border-subtle);
        padding: 6px;
    }
    .node-chip-box.pressure {
        background: rgba(244, 63, 94, 0.15);
        border-color: var(--status-rose-border);
    }
    .node-chip-name {
        font-size: 10px;
        font-weight: 700;
        color: #fff;
    }
    .node-chip-load {
        font-size: 9px;
        color: var(--text-muted);
        font-weight: 600;
    }

    /* Terminal stream */
    .clean-log-terminal {
        background: #060912;
        border: 1px solid var(--border-subtle);
        border-radius: 10px;
        padding: 14px 16px;
        font-family: var(--font-mono);
        font-size: 12px;
        color: #cbd5e1;
        max-height: 220px;
        overflow-y: auto;
    }
    .clean-log-line {
        padding: 3px 0;
        line-height: 1.4;
    }
    .clean-log-line.error { color: #f87171; }
    .clean-log-line.culprit { color: #fb7185; font-weight: 700; background: rgba(244, 63, 94, 0.12); padding: 3px 6px; border-radius: 4px; }
    .clean-log-line.warn { color: #fbbf24; }
    .clean-log-line.info { color: #38bdf8; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        display: flex;
        align-items: center;
        gap: 8px;
        background: rgba(14, 19, 32, 0.7);
        padding: 6px;
        border-radius: 12px;
        border: 1px solid var(--border-subtle);
        margin-bottom: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 9px 20px;
        border-radius: 8px;
        background: transparent;
        color: var(--text-secondary);
        font-size: 13px;
        font-weight: 600;
        border: none;
        transition: all 0.2s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #fff;
        background: rgba(255, 255, 255, 0.04);
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(56, 189, 248, 0.16), rgba(59, 130, 246, 0.16)) !important;
        color: #fff !important;
        border: 1px solid rgba(56, 189, 248, 0.35) !important;
        box-shadow: 0 0 16px rgba(56, 189, 248, 0.15) !important;
    }
</style>

<div class="ambient-glow glow-top-left" aria-hidden="true"></div>
<div class="ambient-glow glow-top-right" aria-hidden="true"></div>
<div class="ambient-glow glow-center-navy" aria-hidden="true"></div>
<div class="saas-grid-pattern" aria-hidden="true"></div>
""")


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

if "selected_cluster" not in st.session_state:
    st.session_state.selected_cluster = "Global Mesh (All Regions)"

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
# Sidebar: Chaos Fault Lab & Cluster Controls
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("### 🌐 **AnomIQ Cluster Fleet**")
    cluster_selection = st.selectbox(
        "Active Kubernetes Mesh",
        [
            "Global Mesh (All Regions)",
            "us-east-k8s-prod (N. Virginia · 48 Nodes)",
            "eu-west-k8s-prod (Frankfurt · 36 Nodes)",
            "ap-east-k8s-edge (Tokyo · 44 Nodes)"
        ],
        index=0
    )
    st.session_state.selected_cluster = cluster_selection

    st.markdown("---")
    st.markdown("### ⚡ **Chaos Fault Injection Lab**")
    st.caption("Inject production outages to evaluate the AI Anomaly Detector & LLM RCA:")

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        if st.button("💧 Memory Leak", width="stretch", help="Simulate heap memory leak climbing to 488 MB (near 512 MB limit)"):
            st.session_state.chaos_state = "MEMORY_LEAK"
            st.session_state.simulated_metrics.update({
                "cpu_cores": 0.178,
                "memory_mb": 488.6,
                "request_rate_rps": 14.5,
                "error_rate_pct": 0.0,
                "p95_latency_ms": 68.2,
            })
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
            st.toast("🔥 Injected CPU Saturation Spike!", icon="🔥")

    with col_c2:
        if st.button("💥 500 Cascade", width="stretch", help="Trigger 46.5% HTTP 500 server error cascade"):
            st.session_state.chaos_state = "HTTP_500_SPIKE"
            st.session_state.simulated_metrics.update({
                "cpu_cores": 0.135,
                "memory_mb": 142.0,
                "request_rate_rps": 16.0,
                "error_rate_pct": 46.5,
                "p95_latency_ms": 52.0,
            })
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
            st.toast("⏱️ Injected Network Latency Spike!", icon="⏱️")

    if st.button("🔄 Restore Nominal State", width="stretch", type="primary"):
        st.session_state.chaos_state = "NORMAL"
        st.session_state.simulated_metrics.update({
            "cpu_cores": 0.105 + random.uniform(-0.02, 0.02),
            "memory_mb": 130.0 + random.uniform(-5, 5),
            "request_rate_rps": 10.0 + random.uniform(-2, 2),
            "error_rate_pct": 0.0,
            "p95_latency_ms": 22.0 + random.uniform(-3, 3),
        })
        st.toast("✅ Cluster Restored to Nominal State", icon="✅")

    st.markdown("---")
    auto_refresh = st.checkbox("Live Auto-Refresh", value=True)
    refresh_rate = st.slider("Poll Interval (seconds)", 2, 12, 4)
    st.caption("Engine: Fine-Tuned Qwen2-7B AIOps RCA")


# ---------------------------------------------------------
# Telemetry Stream Gathering
# ---------------------------------------------------------
current_metrics = st.session_state.simulated_metrics.copy()

if st.session_state.chaos_state == "NORMAL":
    current_metrics["cpu_cores"] = max(0.02, round(current_metrics["cpu_cores"] + random.uniform(-0.008, 0.008), 4))
    current_metrics["memory_mb"] = max(50.0, round(current_metrics["memory_mb"] + random.uniform(-1.5, 1.5), 1))
    current_metrics["request_rate_rps"] = max(1.0, round(current_metrics["request_rate_rps"] + random.uniform(-0.4, 0.4), 1))

# Append to history buffer
current_metrics["timestamp"] = time.strftime("%H:%M:%S")
st.session_state.history_buffer.append(current_metrics)
if len(st.session_state.history_buffer) > 40:
    st.session_state.history_buffer.pop(0)

history_df = pd.DataFrame(st.session_state.history_buffer)

# State transition evaluation
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
# Header Bar (Matching AnomIQ Header)
# ---------------------------------------------------------
beacon_class = "beacon-rose" if is_anomaly else "beacon-cyan"
cluster_name_short = st.session_state.selected_cluster.split(' ')[0]
system_status_text = "P1 CRITICAL ANOMALY" if is_anomaly else "ALL SYSTEMS HEALTHY"
system_status_bg = "rgba(244, 63, 94, 0.15)" if is_anomaly else "rgba(16, 185, 129, 0.15)"
system_status_border = "#f43f5e" if is_anomaly else "#10b981"
system_status_color = "#fb7185" if is_anomaly else "#34d399"

st.html(f"""
<header class="site-header">
    <div class="header-left">
        <div class="brand-icon-box">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#38bdf8" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                <path d="M2 17l10 5 10-5"></path>
                <path d="M2 12l10 5 10-5"></path>
            </svg>
        </div>
        <div>
            <div class="brand-name">Anom<span class="brand-highlight">IQ</span></div>
            <div class="brand-tagline">Detect · Diagnose · Recover</div>
        </div>
    </div>
    <div style="display: flex; align-items: center; gap: 16px;">
        <div style="background: rgba(17, 24, 39, 0.7); border: 1px solid var(--border-subtle); border-radius: 10px; padding: 6px 14px; font-size: 12px; font-weight: 600; display: flex; align-items: center; gap: 8px;">
            <span class="status-beacon-dot {beacon_class}"></span>
            <span>{cluster_name_short}</span>
        </div>
        <div style="background: {system_status_bg}; border: 1px solid {system_status_border}; color: {system_status_color}; padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 700; display: flex; align-items: center; gap: 8px;">
            <span class="status-beacon-dot {beacon_class}"></span>
            <span>{system_status_text}</span>
        </div>
    </div>
</header>
""")


# ---------------------------------------------------------
# Tabbed Navigation (Clean, AnomIQ Style)
# ---------------------------------------------------------
tab_overview, tab_monitoring, tab_rca, tab_lab, tab_llm, tab_archive = st.tabs([
    "🌐 Overview",
    "📊 Monitoring",
    "🧠 RCA (Root Cause)",
    "🧪 AI Diagnostic Lab",
    "🤖 LLM Architecture",
    "📁 Incident Archive & Alerts"
])


# =========================================================
# PAGE 1: OVERVIEW DASHBOARD (WITH REAL 3D HOLOGRAPHIC GLOBE)
# =========================================================
with tab_overview:
    col_hero_left, col_hero_right = st.columns([1.35, 1])

    with col_hero_left:
        # Status Badge & Heading
        hero_badge_bg = "var(--status-rose-bg)" if is_anomaly else "var(--status-emerald-bg)"
        hero_badge_border = "var(--status-rose-border)" if is_anomaly else "var(--status-emerald-border)"
        hero_badge_color = "var(--status-rose-bright)" if is_anomaly else "var(--status-emerald-bright)"
        hero_badge_beacon = "beacon-rose" if is_anomaly else "beacon-emerald"
        hero_badge_title = "System Anomaly Detected" if is_anomaly else "Global Fleet Steady-State"

        st.html(f"""
        <div class="saas-card" style="padding-bottom: 8px; margin-bottom: 12px;">
            <div class="card-ambient-highlight"></div>
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                <div style="background: {hero_badge_bg}; border: 1px solid {hero_badge_border}; color: {hero_badge_color}; padding: 5px 14px; border-radius: 20px; font-size: 11px; font-weight: 700; display: inline-flex; align-items: center; gap: 8px;">
                    <span class="status-beacon-dot {hero_badge_beacon}"></span>
                    <span>{hero_badge_title}</span>
                </div>
            </div>
            <h1 style="font-size: 24px; font-weight: 800; color: #fff; margin: 4px 0 6px;">Infrastructure Mesh</h1>
            <p style="font-size: 13px; color: var(--text-secondary); margin: 0;">
                AnomIQ is autonomously monitoring all Kubernetes services in real time across 128 nodes and 1,482 pods. Drag & rotate the interactive 3D Globe to inspect cluster topology.
            </p>
        </div>
        """)

        # -----------------------------------------------------
        # 3D HOLOGRAPHIC GLOBE COMPONENT (Real Client-Side Canvas)
        # -----------------------------------------------------
        us_status = 'critical' if is_anomaly else 'healthy'
        us_color = '#f43f5e' if is_anomaly else '#10b981'
        us_lat = '428ms' if is_anomaly else '22ms'

        # Read globe.js content
        globe_js_path = os.path.join(PROJECT_ROOT, "dashboard", "assets", "globe.js")
        if os.path.exists(globe_js_path):
            with open(globe_js_path, "r", encoding="utf-8") as f:
                globe_js_code = f.read()
        else:
            globe_js_code = ""

        # Embed complete HTML5 Canvas 3D Globe
        globe_component_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
          * {{ margin: 0; padding: 0; box-sizing: border-box; }}
          body, html {{
            width: 100%;
            height: 100%;
            overflow: hidden;
            background: #060913;
            border-radius: 14px;
            font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
          }}
          #globeContainer {{
            position: relative;
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: grab;
          }}
          #globeContainer:active {{ cursor: grabbing; }}
          canvas {{ width: 100%; height: 100%; display: block; }}
          .globe-saas-tooltip {{
            position: absolute;
            width: 240px;
            background: rgba(12, 17, 28, 0.95);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(56, 189, 248, 0.45);
            border-radius: 12px;
            padding: 14px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8), 0 0 25px rgba(56, 189, 248, 0.2);
            pointer-events: none;
            opacity: 0;
            transform: scale(0.95);
            transition: opacity 0.2s, transform 0.2s;
            z-index: 50;
            color: #fff;
            font-size: 12px;
            display: none;
          }}
          .globe-saas-tooltip.visible {{ display: block; opacity: 1; transform: scale(1); }}
          .tooltip-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            padding-bottom: 6px;
            border-bottom: 1px solid rgba(255,255,255,0.08);
          }}
          .tooltip-cluster-name {{ font-weight: 700; color: #fff; font-size: 13px; }}
          .tooltip-badge {{ font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; }}
          .badge-crit {{ background: rgba(244, 63, 94, 0.2); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.4); }}
          .badge-ok {{ background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }}
          .tooltip-row {{ display: flex; justify-content: space-between; margin-bottom: 4px; color: #94a3b8; font-size: 11px; }}
        </style>
        </head>
        <body>
        <div id="globeContainer">
          <canvas id="holoGlobeCanvas"></canvas>
          <div class="globe-saas-tooltip" id="globeNodeTooltip">
            <div class="tooltip-top">
              <span class="tooltip-cluster-name" id="tooltipCluster">us-east-k8s-prod</span>
              <span class="tooltip-badge badge-crit" id="tooltipStatus">P1 Active</span>
            </div>
            <div class="tooltip-row"><span>Region</span><strong id="tooltipRegion" style="color:#fff;">US East</strong></div>
            <div class="tooltip-row"><span>Capacity</span><strong id="tooltipPods" style="color:#fff;">584 Pods</strong></div>
            <div class="tooltip-row"><span>Latency P99</span><strong id="tooltipLatency" style="color:#38bdf8;">{us_lat}</strong></div>
          </div>
        </div>
        <script>
        {globe_js_code}

        // Initialize engine with dynamic cluster health
        window.addEventListener('DOMContentLoaded', () => {{
          const engine = new HoloGlobeEngine('holoGlobeCanvas');
          if (engine && engine.clusters && engine.clusters.length > 0) {{
            engine.clusters[0].status = '{us_status}';
            engine.clusters[0].color = '{us_color}';
            engine.clusters[0].latency = '{us_lat}';
          }}
        }});
        </script>
        </body>
        </html>
        """
        st.components.v1.html(globe_component_html, height=330)

        # Region status quick cards below globe
        us_card_bg = "var(--status-rose-bg)" if is_anomaly else "rgba(255, 255, 255, 0.03)"
        us_card_border = "var(--status-rose-border)" if is_anomaly else "var(--border-subtle)"
        us_card_beacon = "beacon-rose" if is_anomaly else "beacon-cyan"
        us_card_lat = "428ms" if is_anomaly else "22ms"

        st.html(f"""
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 10px;">
            <div style="background: {us_card_bg}; border: 1px solid {us_card_border}; border-radius: 12px; padding: 12px 14px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <span style="font-size: 12px; font-weight: 700; color: #fff;">US East</span>
                    <span class="status-beacon-dot {us_card_beacon}"></span>
                </div>
                <div style="font-size: 11px; color: var(--text-muted);">584 Pods · Latency {us_card_lat}</div>
            </div>
            <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border-subtle); border-radius: 12px; padding: 12px 14px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <span style="font-size: 12px; font-weight: 700; color: #fff;">EU Central</span>
                    <span class="status-beacon-dot beacon-cyan"></span>
                </div>
                <div style="font-size: 11px; color: var(--text-muted);">462 Pods · Latency 34ms</div>
            </div>
            <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border-subtle); border-radius: 12px; padding: 12px 14px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <span style="font-size: 12px; font-weight: 700; color: #fff;">AP East</span>
                    <span class="status-beacon-dot beacon-cyan"></span>
                </div>
                <div style="font-size: 11px; color: var(--text-muted);">436 Pods · Latency 41ms</div>
            </div>
        </div>
        """)

    with col_hero_right:
        # KPI 1: Active Incidents
        kpi1_badge_class = "pill-rose" if is_anomaly else "pill-emerald"
        kpi1_badge_text = "P1 Critical" if is_anomaly else "Zero Incidents"
        kpi1_count = "1" if is_anomaly else "0"
        kpi1_service = "checkout-gateway-svc" if is_anomaly else "fleet nominal"
        kpi1_root = rca_report.get('root_cause', 'Nominal steady-state')
        kpi1_link_color = "#fb7185" if is_anomaly else "#34d399"
        kpi1_link_text = "Active Investigation →" if is_anomaly else "Healthy"

        st.html(f"""
        <div class="saas-card kpi-clean-card">
            <div class="card-ambient-highlight"></div>
            <div class="kpi-header-row">
                <span class="kpi-label">Active Incidents</span>
                <span class="kpi-pill-badge {kpi1_badge_class}">{kpi1_badge_text}</span>
            </div>
            <div class="kpi-number-row">
                <span class="kpi-value-huge">{kpi1_count}</span>
                <span class="kpi-meta-text">{kpi1_service}</span>
            </div>
            <div class="kpi-footer-row">
                <span>{kpi1_root}</span>
                <strong style="color: {kpi1_link_color};">{kpi1_link_text}</strong>
            </div>
        </div>
        """)

        # KPI 2: Detected Anomalies
        st.html("""
        <div class="saas-card kpi-clean-card">
            <div class="card-ambient-highlight"></div>
            <div class="kpi-header-row">
                <span class="kpi-label">Detected Anomalies</span>
                <span class="kpi-pill-badge pill-cyan">Past 24 Hours</span>
            </div>
            <div class="kpi-number-row">
                <span class="kpi-value-huge">3</span>
                <span class="kpi-meta-text">2 auto-mitigated by AI</span>
            </div>
            <div class="kpi-footer-row">
                <span>Neural model confidence</span>
                <strong style="color: #38bdf8;">98.4% Confidence</strong>
            </div>
        </div>
        """)

        # KPI 3: System Uptime
        st.html("""
        <div class="saas-card kpi-clean-card">
            <div class="card-ambient-highlight"></div>
            <div class="kpi-header-row">
                <span class="kpi-label">System Uptime</span>
                <span class="kpi-pill-badge pill-emerald">Four Nines</span>
            </div>
            <div class="kpi-number-row">
                <span class="kpi-value-huge">99.994%</span>
                <span class="kpi-meta-text">30-day rolling SLA</span>
            </div>
            <div class="kpi-footer-row">
                <span>Error budget remaining</span>
                <strong style="color: #34d399;">88.2% (38m remaining)</strong>
            </div>
        </div>
        """)

    # Bottom Row: AI Health Score + Telemetry Waveforms + Cluster Workloads
    col_b1, col_b2, col_b3 = st.columns([1, 1.4, 1.1])

    with col_b1:
        health_num = 72.4 if is_anomaly else 94.2
        stroke_color = "#f43f5e" if is_anomaly else "#38bdf8"
        dash_offset = 69.1 if is_anomaly else 14.5
        risk_color = "#fb7185" if is_anomaly else "#34d399"
        risk_text = "Elevated (1 Service)" if is_anomaly else "Nominal"

        st.html(f"""
        <div class="saas-card" style="height: 100%; display: flex; flex-direction: column; justify-content: space-between;">
            <div class="card-ambient-highlight"></div>
            <div class="card-header-clean">
                <div>
                    <div class="card-title">AI Health Score</div>
                    <div class="card-subtitle">Real-time autonomous stability index</div>
                </div>
            </div>
            <div style="display: flex; justify-content: center; align-items: center; margin: 12px 0;">
                <div style="position: relative; width: 130px; height: 130px;">
                    <svg viewBox="0 0 100 100" style="width: 100%; height: 100%; transform: rotate(-90deg);">
                        <circle cx="50" cy="50" r="40" fill="none" stroke="rgba(255,255,255,0.07)" stroke-width="8" />
                        <circle cx="50" cy="50" r="40" fill="none" stroke="{stroke_color}" stroke-width="8" stroke-linecap="round" stroke-dasharray="251.32" stroke-dashoffset="{dash_offset}" style="filter: drop-shadow(0 0 10px {stroke_color});" />
                    </svg>
                    <div style="position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center;">
                        <span style="font-size: 30px; font-weight: 800; color: #fff;">{health_num}</span>
                        <span style="font-size: 11px; color: var(--text-muted); font-weight: 600;">/ 100</span>
                    </div>
                </div>
            </div>
            <div style="display: flex; flex-direction: column; gap: 8px; font-size: 12px; color: var(--text-secondary);">
                <div style="display: flex; justify-content: space-between;">
                    <span>Mean Time to Detect (MTTD)</span>
                    <strong style="color: #fff;">420 ms</strong>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span>Autonomous Recovery Rate</span>
                    <strong style="color: #fff;">96.8%</strong>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span>Current Anomaly Risk</span>
                    <strong style="color: {risk_color};">{risk_text}</strong>
                </div>
            </div>
        </div>
        """)

    with col_b2:
        st.html("""
        <div class="saas-card" style="padding-bottom: 10px;">
            <div class="card-ambient-highlight"></div>
            <div class="card-header-clean">
                <div>
                    <div class="card-title">Resource Telemetry</div>
                    <div class="card-subtitle">Real-time compute & memory allocation</div>
                </div>
                <span class="status-beacon-dot beacon-cyan"></span>
            </div>
        </div>
        """)

        fig_cpu = go.Figure()
        fig_cpu.add_trace(go.Scatter(
            x=history_df["timestamp"], y=history_df["cpu_cores"],
            mode="lines", name="CPU (Cores)",
            line=dict(color="#38bdf8", width=2.5, shape="spline"),
            fill="tozeroy", fillcolor="rgba(56, 189, 248, 0.12)"
        ))
        fig_cpu.add_hline(y=0.5, line_dash="dash", line_color="#ef4444", annotation_text="Quota 0.5 cores")
        fig_cpu.update_layout(
            paper_bgcolor="rgba(13, 18, 30, 0)",
            plot_bgcolor="rgba(13, 18, 30, 0)",
            font=dict(color="#94a3b8", family="Plus Jakarta Sans"),
            margin=dict(l=10, r=10, t=10, b=10),
            height=110,
            showlegend=False,
            yaxis=dict(gridcolor="rgba(255, 255, 255, 0.04)", zeroline=False),
            xaxis=dict(showgrid=False, showticklabels=False)
        )
        st.plotly_chart(fig_cpu, width="stretch", key="overview_chart_cpu")

        fig_mem = go.Figure()
        fig_mem.add_trace(go.Scatter(
            x=history_df["timestamp"], y=history_df["memory_mb"],
            mode="lines", name="Memory (MB)",
            line=dict(color="#8b5cf6", width=2.5, shape="spline"),
            fill="tozeroy", fillcolor="rgba(139, 92, 246, 0.12)"
        ))
        fig_mem.add_hline(y=512, line_dash="dash", line_color="#ef4444", annotation_text="Limit 512MB")
        fig_mem.update_layout(
            paper_bgcolor="rgba(13, 18, 30, 0)",
            plot_bgcolor="rgba(13, 18, 30, 0)",
            font=dict(color="#94a3b8", family="Plus Jakarta Sans"),
            margin=dict(l=10, r=10, t=10, b=10),
            height=110,
            showlegend=False,
            yaxis=dict(gridcolor="rgba(255, 255, 255, 0.04)", zeroline=False),
            xaxis=dict(showgrid=False, showticklabels=False)
        )
        st.plotly_chart(fig_mem, width="stretch", key="overview_chart_mem")

    with col_b3:
        faulty_pods = 8 if is_anomaly else 0
        healthy_width = 95 if is_anomaly else 100
        faulty_width = 5 if is_anomaly else 0
        nodes_degraded_text = '1 Degraded' if is_anomaly else 'Ready'
        faulty_color = '#fb7185' if is_anomaly else '#34d399'

        st.html(f"""
        <div class="saas-card" style="height: 100%; display: flex; flex-direction: column; justify-content: space-between;">
            <div class="card-ambient-highlight"></div>
            <div class="card-header-clean">
                <div>
                    <div class="card-title">Cluster Workloads</div>
                    <div class="card-subtitle">Kubernetes fleet capacity</div>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px;">
                <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border-subtle); border-radius: 12px; padding: 12px;">
                    <div style="font-size: 24px; font-weight: 800; color: #fff;">128</div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">Nodes ({nodes_degraded_text})</div>
                </div>
                <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border-subtle); border-radius: 12px; padding: 12px;">
                    <div style="font-size: 24px; font-weight: 800; color: #fff;">1,482</div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">Workload Pods</div>
                </div>
            </div>
            <div>
                <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--text-secondary); margin-bottom: 6px;">
                    <span>1,471 Running</span>
                    <span style="color: {faulty_color};">{faulty_pods} CrashLoopBackOff</span>
                </div>
                <div style="height: 7px; border-radius: 4px; background: rgba(255,255,255,0.06); display: flex; overflow: hidden;">
                    <div style="width: {healthy_width}%; background: var(--status-emerald);"></div>
                    <div style="width: {faulty_width}%; background: var(--status-rose);"></div>
                </div>
            </div>
            <div style="margin-top: 14px; padding-top: 10px; border-top: 1px solid var(--border-subtle); font-size: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0;">
                    <span style="color: #fff; font-weight: 600;">Redis Shard-04 Eviction</span>
                    <span style="font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 4px; background: var(--status-emerald-bg); color: var(--status-emerald-bright);">Auto-Healed</span>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0;">
                    <span style="color: #fff; font-weight: 600;">Kafka Consumer Lag</span>
                    <span style="font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 4px; background: var(--status-emerald-bg); color: var(--status-emerald-bright);">Auto-Resolved</span>
                </div>
            </div>
        </div>
        """)


# =========================================================
# PAGE 2: MONITORING (CLUSTER DETAILS)
# =========================================================
with tab_monitoring:
    st.html("""
    <div style="margin-bottom: 20px;">
        <h1 style="font-size: 24px; font-weight: 800; color: #fff; letter-spacing: -0.5px; margin: 0 0 4px;">Cluster Fleet & Workloads</h1>
        <p style="font-size: 14px; color: var(--text-secondary); margin: 0;">Real-time compute pressure, microservice health, and container runtime telemetry.</p>
    </div>
    """)

    # Top 4 Clean Stats Row
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.html("""
        <div class="saas-card" style="padding: 18px 22px; border-radius: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Clusters</span>
                <span class="status-beacon-dot beacon-cyan"></span>
            </div>
            <div style="font-size: 28px; font-weight: 800; color: #fff;">4</div>
            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">Across 4 global cloud regions</div>
        </div>
        """)
    with col_m2:
        st.html("""
        <div class="saas-card" style="padding: 18px 22px; border-radius: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Active Nodes</span>
                <span class="status-beacon-dot beacon-cyan"></span>
            </div>
            <div style="font-size: 28px; font-weight: 800; color: #fff;">128</div>
            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">127 Ready · 1 Pressure</div>
        </div>
        """)
    with col_m3:
        st.html("""
        <div class="saas-card" style="padding: 18px 22px; border-radius: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Monitored Pods</span>
                <span class="status-beacon-dot beacon-cyan"></span>
            </div>
            <div style="font-size: 28px; font-weight: 800; color: #fff;">1,482</div>
            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">99.2% healthy containers</div>
        </div>
        """)
    with col_m4:
        st.html("""
        <div class="saas-card" style="padding: 18px 22px; border-radius: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Containers</span>
                <span class="status-beacon-dot beacon-cyan"></span>
            </div>
            <div style="font-size: 28px; font-weight: 800; color: #fff;">4,120</div>
            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">containerd 1.7 runtime</div>
        </div>
        """)

    # 16-Node Compute Pressure Matrix & Throughput
    col_mat_left, col_mat_right = st.columns([1, 1])
    with col_mat_left:
        chips_html = ""
        for i in range(1, 17):
            is_node_pressure = (i == 8 and is_anomaly)
            load_pct = random.randint(84, 94) if is_node_pressure else random.randint(28, 62)
            node_color = '#fb7185' if is_node_pressure else 'var(--text-muted)'
            node_chip_class = "node-chip-box pressure" if is_node_pressure else "node-chip-box"
            chips_html += f'<div class="{node_chip_class}"><div class="node-chip-name">node-{i:02d}</div><div class="node-chip-load" style="color: {node_color};">{load_pct}%</div></div>'

        node_status_text = 'MemoryPressure' if is_anomaly else 'Ready'
        node_status_color = '#fb7185' if is_anomaly else '#34d399'

        st.html(f"""
        <div class="saas-card">
            <div class="card-ambient-highlight"></div>
            <div class="card-header-clean">
                <div>
                    <div class="card-title">Compute Node Pressure Matrix</div>
                    <div class="card-subtitle">16 core nodes in selected cluster</div>
                </div>
            </div>
            <div class="node-matrix-container">
                {chips_html}
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; background: rgba(0,0,0,0.3); padding: 10px 14px; border-radius: 8px; border: 1px solid var(--border-subtle); color: var(--text-secondary);">
                <span>Node: <strong style="color: #fff;">node-us-east-worker-08</strong></span>
                <span>Load: CPU 84% · MEM 91%</span>
                <span style="color: {node_status_color};">Status: {node_status_text}</span>
            </div>
        </div>
        """)

    with col_mat_right:
        st.html("""
        <div class="saas-card" style="padding-bottom: 10px;">
            <div class="card-ambient-highlight"></div>
            <div class="card-header-clean">
                <div>
                    <div class="card-title">Live Ingress Throughput</div>
                    <div class="card-subtitle">Actual requests vs predictive neural corridor</div>
                </div>
                <strong style="color: #38bdf8;">142,400 req/s</strong>
            </div>
        </div>
        """)

        fig_thru = go.Figure()
        fig_thru.add_trace(go.Scatter(
            x=history_df["timestamp"], y=history_df["request_rate_rps"],
            mode="lines", name="RPS",
            line=dict(color="#38bdf8", width=3, shape="spline"),
            fill="tozeroy", fillcolor="rgba(56, 189, 248, 0.15)"
        ))
        fig_thru.update_layout(
            paper_bgcolor="rgba(13, 18, 30, 0)",
            plot_bgcolor="rgba(13, 18, 30, 0)",
            font=dict(color="#94a3b8"),
            margin=dict(l=10, r=10, t=10, b=10),
            height=210,
            yaxis=dict(gridcolor="rgba(255, 255, 255, 0.04)"),
            xaxis=dict(gridcolor="rgba(255, 255, 255, 0.04)")
        )
        st.plotly_chart(fig_thru, width="stretch", key="mon_chart_throughput")

    # Service Health Status Grid (6 Microservices)
    checkout_card_class = "svc-card alert" if is_anomaly else "svc-card"
    checkout_name_color = "#fb7185" if is_anomaly else "#fff"
    checkout_beacon = "beacon-rose" if is_anomaly else "beacon-cyan"
    checkout_latency_text = "4,280ms · High Latency" if is_anomaly else "22ms · Nominal"
    checkout_latency_color = "#fb7185" if is_anomaly else "var(--text-muted)"

    st.html(f"""
    <div class="service-health-grid">
        <div class="svc-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="svc-name">API Gateway</span>
                <span class="status-beacon-dot beacon-cyan"></span>
            </div>
            <span class="svc-latency">12ms · 48k rps</span>
        </div>

        <div class="svc-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="svc-name">Auth Service</span>
                <span class="status-beacon-dot beacon-cyan"></span>
            </div>
            <span class="svc-latency">6ms · 42k rps</span>
        </div>

        <div class="{checkout_card_class}">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="svc-name" style="color: {checkout_name_color};">Checkout Svc</span>
                <span class="status-beacon-dot {checkout_beacon}"></span>
            </div>
            <span class="svc-latency" style="color: {checkout_latency_color};">{checkout_latency_text}</span>
        </div>

        <div class="svc-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="svc-name">Kafka Stream</span>
                <span class="status-beacon-dot beacon-cyan"></span>
            </div>
            <span class="svc-latency">18ms · Nominal</span>
        </div>

        <div class="svc-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="svc-name">Redis Cache</span>
                <span class="status-beacon-dot beacon-cyan"></span>
            </div>
            <span class="svc-latency">2ms · 99.8% hit</span>
        </div>

        <div class="svc-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="svc-name">Postgres DB</span>
                <span class="status-beacon-dot beacon-cyan"></span>
            </div>
            <span class="svc-latency">4ms · 12 conns</span>
        </div>
    </div>
    """)

    # Kubernetes Fleet Pods Table
    st.html("""
    <div class="saas-card">
        <div class="card-ambient-highlight"></div>
        <div class="card-header-clean">
            <div>
                <div class="card-title">Kubernetes Fleet Workloads</div>
                <div class="card-subtitle">Active pods running in monitored namespaces</div>
            </div>
            <span class="kpi-pill-badge pill-cyan">14 Replicas Monitored</span>
        </div>
    </div>
    """)

    pod_table_data = [
        {"Pod Name": "checkout-gateway-78f9-xk8p", "Namespace": "payments", "Node": "node-08", "Status": "CrashLoopBackOff" if is_anomaly else "Running", "Restarts": 6 if is_anomaly else 0, "CPU": "92%", "Memory": "99.5%", "Age": "14m"},
        {"Pod Name": "checkout-gateway-78f9-mn2q", "Namespace": "payments", "Node": "node-08", "Status": "CrashLoopBackOff" if is_anomaly else "Running", "Restarts": 4 if is_anomaly else 0, "CPU": "88%", "Memory": "97.2%", "Age": "12m"},
        {"Pod Name": "api-gateway-55cb-99xz", "Namespace": "ingress", "Node": "node-02", "Status": "Running", "Restarts": 0, "CPU": "24%", "Memory": "42.0%", "Age": "4d"},
        {"Pod Name": "auth-service-67ba-44ty", "Namespace": "identity", "Node": "node-03", "Status": "Running", "Restarts": 0, "CPU": "18%", "Memory": "38.5%", "Age": "6d"},
        {"Pod Name": "order-processor-12ac-55op", "Namespace": "orders", "Node": "node-05", "Status": "Running", "Restarts": 0, "CPU": "32%", "Memory": "54.1%", "Age": "2d"},
        {"Pod Name": "redis-master-0", "Namespace": "data", "Node": "node-06", "Status": "Running", "Restarts": 0, "CPU": "12%", "Memory": "29.4%", "Age": "18d"},
        {"Pod Name": "postgres-cluster-0", "Namespace": "data", "Node": "node-07", "Status": "Running", "Restarts": 0, "CPU": "45%", "Memory": "68.0%", "Age": "22d"},
    ]
    st.dataframe(pd.DataFrame(pod_table_data), width="stretch")


# =========================================================
# PAGE 3: ROOT CAUSE ANALYSIS (RCA)
# =========================================================
with tab_rca:
    inc_id = rca_report.get("incident_id", "INC-8921")
    inc_severity = rca_report.get("severity", "CRITICAL")
    inc_root = rca_report.get("root_cause", "Payment Gateway Kernel Latency Spike & Pod OOMCascades")
    inc_mechanism = rca_report.get("mechanism", "Direct buffer memory leak triggered by uncollected channel buffers.")
    inc_risk = rca_report.get("imminent_risk", "Cascading pod OOMKills and checkout API failure.")
    inc_badge_bg = "var(--status-rose-bg)" if is_anomaly else "var(--status-emerald-bg)"
    inc_badge_color = "var(--status-rose-bright)" if is_anomaly else "var(--status-emerald-bright)"
    inc_badge_border = "var(--status-rose-border)" if is_anomaly else "var(--status-emerald-border)"

    # Incident Master Banner
    st.html(f"""
    <div class="saas-card" style="padding: 28px; margin-bottom: 24px;">
        <div class="card-ambient-highlight"></div>
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;">
            <div style="max-width: 70%;">
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                    <span style="font-size: 11px; font-weight: 800; padding: 4px 10px; border-radius: 6px; background: {inc_badge_bg}; color: {inc_badge_color}; border: 1px solid {inc_badge_border};">
                        {inc_severity} · {inc_id}
                    </span>
                    <span class="kpi-pill-badge pill-cyan">checkout-gateway-svc</span>
                    <span style="font-size: 12px; color: var(--text-muted);">Detected {rca_report.get('timestamp', 'just now')}</span>
                </div>
                <h2 style="font-size: 24px; font-weight: 800; color: #fff; margin: 0 0 8px; letter-spacing: -0.5px;">{inc_root}</h2>
                <p style="font-size: 14px; color: var(--text-secondary); margin: 0; line-height: 1.5;">
                    AI Autonomous Reasoning Engine has identified high-confidence root cause in <code>checkout-gateway:v2.14.0</code>. 98.7% neural correlation consensus.
                </p>
            </div>
            <div>
                <span style="background: linear-gradient(135deg, var(--accent-cyan-bright), var(--accent-blue)); color: #fff; padding: 10px 18px; border-radius: 10px; font-weight: 700; font-size: 13px; display: inline-flex; align-items: center; gap: 8px;">
                    ⚡ Autonomous Reasoning Active
                </span>
            </div>
        </div>
    </div>
    """)

    # Connected 4-Step AI Pipeline Track
    current_anom_cat = current_metrics.get('anomaly_type', rca_report.get('anomaly_type', 'anomaly')).upper()
    lat_val_p95 = current_metrics.get('p95_latency_ms', 0)
    mem_val_curr = current_metrics.get('memory_mb', 0)

    st.html(f"""
    <div class="ai-pipeline-track">
        <!-- Step 1: Anomaly -->
        <div class="pipeline-step-card">
            <div class="card-ambient-highlight"></div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="step-num-pill">Step 01</span>
                <span class="status-beacon-dot beacon-rose"></span>
            </div>
            <div class="step-stage-name">Detected Anomaly</div>
            <p class="step-stage-desc">
                {current_anom_cat}: P99 latency deteriorated to {lat_val_p95:.1f}ms. Replicas failing probes.
            </p>
        </div>

        <!-- Step 2: Evidence -->
        <div class="pipeline-step-card">
            <div class="card-ambient-highlight"></div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="step-num-pill">Step 02</span>
                <span class="status-beacon-dot beacon-cyan"></span>
            </div>
            <div class="step-stage-name">Correlated Evidence</div>
            <p class="step-stage-desc">
                Resident memory slope jumped to {mem_val_curr:.1f}MB. eBPF intercepted kernel OOM signals.
            </p>
        </div>

        <!-- Step 3: Root Cause (Active Focus) -->
        <div class="pipeline-step-card active-focus">
            <div class="card-ambient-highlight"></div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="step-num-pill">Step 03</span>
                <span class="status-beacon-dot beacon-rose"></span>
            </div>
            <div class="step-stage-name">Probable Root Cause</div>
            <p class="step-stage-desc">
                {inc_mechanism}
            </p>
        </div>

        <!-- Step 4: Recommended Action -->
        <div class="pipeline-step-card">
            <div class="card-ambient-highlight"></div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="step-num-pill">Step 04</span>
                <span class="status-beacon-dot beacon-emerald"></span>
            </div>
            <div class="step-stage-name">AI Recommendation</div>
            <p class="step-stage-desc">
                Execute automated playbook rollback with Envoy dynamic traffic rerouting. Zero downtime expected.
            </p>
        </div>
    </div>
    """)

    # Runbook & Logs
    col_rca_l, col_rca_r = st.columns([1.1, 0.9])

    with col_rca_l:
        st.markdown("#### 🛠️ **Prescribed Mitigation Runbook**")
        for cmd in rca_report.get("immediate_mitigation", []):
            st.code(cmd, language="bash")

        st.markdown("#### 🎯 **Permanent Architectural Resolution**")
        for res in rca_report.get("permanent_resolution", []):
            st.markdown(f"- {res}")

        if st.button("📧 Dispatch Immediate SRE Alert Email", width="stretch", type="primary"):
            sent = dispatcher.send_rca_alert(rca_report, force=True)
            if sent:
                st.success("✅ Email alert successfully rendered & dispatched to SRE on-call!")
            else:
                st.error("Email dispatch failed.")

    with col_rca_r:
        st.markdown("#### 📜 **Correlated Container Logs**")
        mem_mb_val = current_metrics.get('memory_mb', 140)
        st.html(f"""
        <div class="clean-log-terminal">
            <div class="clean-log-line info">[io.netty.bootstrap] Started HTTP microservice on port :8080</div>
            <div class="clean-log-line info">[payments.router] Ingress batch processing active #89104</div>
            <div class="clean-log-line warn">[io.netty.buffer] Memory RSS climbing: {mem_mb_val:.1f}MB / 512MB limit</div>
            <div class="clean-log-line culprit">java.lang.OutOfMemoryError: Java heap space [NettyEpollWorker-4-8]</div>
            <div class="clean-log-line error">[kubelet] Container checkout-gateway failed liveness probe, restarting...</div>
            <div class="clean-log-line error">[starlette.middleware] HTTP 504 Gateway Timeout while waiting for pod response</div>
        </div>
        """)


# =========================================================
# PAGE 4: INTERACTIVE AI DIAGNOSTIC LAB
# =========================================================
with tab_lab:
    st.html("""
    <div style="margin-bottom: 20px;">
        <h1 style="font-size: 24px; font-weight: 800; color: #fff; margin: 0 0 4px;">Interactive AI Diagnostic Lab</h1>
        <p style="font-size: 14px; color: var(--text-secondary); margin: 0;">Adjust telemetry sliders and error logs manually to test the Anomaly Detector and Qwen2 RCA live.</p>
    </div>
    """)

    col_l1, col_l2 = st.columns(2)
    with col_l1:
        l_cpu = st.slider("CPU Usage (cores)", 0.01, 1.0, 0.485, 0.005)
        l_mem = st.slider("Resident Memory (MB - Limit 512MB)", 50.0, 600.0, 492.0, 2.0)
        l_pods = st.slider("Active Pods", 1, 8, 2)

    with col_l2:
        l_err = st.slider("HTTP 5xx Error Rate (%)", 0.0, 100.0, 0.0, 0.5)
        l_lat = st.slider("P95 Latency (ms)", 5.0, 2000.0, 48.0, 5.0)
        l_rps = st.slider("Throughput (req/s)", 1.0, 200.0, 18.0, 1.0)

    log_preset = st.selectbox(
        "Load Outage Error Log Template:",
        [
            "Custom Log",
            "OOM Killer / Memory Leak Trace",
            "Database Connection Pool Saturation",
            "Cgroup CPU CFS Throttling",
            "Null Pointer Exception (500 Cascade)"
        ]
    )
    preset_text = ""
    if log_preset == "OOM Killer / Memory Leak Trace":
        preset_text = "[21:30:10] [WARNING] app.cache: Memory cache size exceeded 450MB.\n[21:30:14] [ERROR] kernel: Task worker invocation invoked oom-killer (ExitCode: 137, OOMKilled)."
    elif log_preset == "Database Connection Pool Saturation":
        preset_text = "[21:30:10] [WARNING] db.pool: Active DB connections reached pool capacity (50/50).\n[21:30:12] [ERROR] sqlalchemy.exc.TimeoutError: QueuePool limit reached."
    elif log_preset == "Cgroup CPU CFS Throttling":
        preset_text = "[21:30:05] [INFO] worker.batch: Heavy thread started.\n[21:30:10] [WARNING] cgroup.cpu: CFS quota throttled 85% of CPU periods over 10s."
    elif log_preset == "Null Pointer Exception (500 Cascade)":
        preset_text = "[21:30:01] [ERROR] app.routes: AttributeError: 'NoneType' object has no attribute 'get_user_account'\n[21:30:04] [ERROR] 500 Internal Server Error in /api/v1/checkout."

    lab_log_input = st.text_area("Container Error Logs:", value=preset_text, height=100)

    if st.button("⚡ Execute Qwen2 AI Diagnosis & Generate RCA", type="primary", width="stretch"):
        test_vec = {
            "cpu_cores": l_cpu,
            "memory_mb": l_mem,
            "request_rate_rps": l_rps,
            "error_rate_pct": l_err,
            "p95_latency_ms": l_lat,
            "active_pods": l_pods
        }
        parsed_l = []
        if lab_log_input.strip():
            for line in lab_log_input.strip().split("\n"):
                if line.strip():
                    parsed_l.append({"timestamp": time.strftime("%H:%M:%S"), "level": "ERROR", "message": line.strip()})

        with st.spinner("🤖 Running AI Anomaly Detection & Qwen2 SRE Analysis..."):
            diag_res = engine.diagnose(test_vec, recent_logs=parsed_l, persist_incident=True, dispatch_email=False)

        st.success(f"Diagnosis Complete! Incident Tag: {diag_res['incident_id']}")

        d_anom = diag_res["is_anomaly"]
        diag_border = "var(--status-rose-border)" if d_anom else "var(--status-emerald-border)"
        diag_class_color = "#fb7185" if d_anom else "#34d399"

        st.html(f"""
        <div class="saas-card" style="border-color: {diag_border};">
            <div class="card-ambient-highlight"></div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <span style="font-weight: 800; color: {diag_class_color};">
                    CLASSIFICATION: {diag_res['anomaly_type'].upper()} ({diag_res.get('severity', 'LOW')} SEVERITY)
                </span>
                <span style="font-size: 13px; color: #94a3b8;">Confidence: {diag_res.get('confidence', 1.0):.2f}</span>
            </div>
            <h3 style="margin: 0 0 8px 0; color: #fff;">{diag_res.get('root_cause')}</h3>
            <p style="color: #cbd5e1; font-size: 14px; margin-bottom: 10px;">{diag_res.get('mechanism')}</p>
            <div style="font-size: 13px; color: #fca5a5;">
                <strong>Imminent Risk:</strong> {diag_res.get('imminent_risk')}
            </div>
        </div>
        """)

        col_lr1, col_lr2 = st.columns(2)
        with col_lr1:
            st.markdown("##### 🛠️ Mitigation Runbook:")
            for cmd in diag_res.get("immediate_mitigation", []):
                st.code(cmd, language="bash")
        with col_lr2:
            st.markdown("##### 🎯 Architectural Resolution:")
            for r in diag_res.get("permanent_resolution", []):
                st.markdown(f"- {r}")


# =========================================================
# PAGE 5: LLM ARCHITECTURE & CHATML INSPECTOR
# =========================================================
with tab_llm:
    st.html("""
    <div style="margin-bottom: 20px;">
        <h1 style="font-size: 24px; font-weight: 800; color: #fff; margin: 0 0 4px;">Fine-Tuned LLM & ChatML Architecture</h1>
        <p style="font-size: 14px; color: var(--text-secondary); margin: 0;">Inspection of the Qwen2-7B fine-tuned causal model weights and ChatML formatting.</p>
    </div>
    """)

    col_w1, col_w2, col_w3, col_w4 = st.columns(4)
    with col_w1:
        st.html("""
        <div class="saas-card" style="padding: 18px 20px;">
            <div class="card-ambient-highlight"></div>
            <div class="kpi-label">Base Model</div>
            <div style="font-size: 24px; font-weight: 800; color: #38bdf8; margin: 4px 0;">Qwen2-7B</div>
            <div style="font-size: 12px; color: var(--text-muted);">Causal Language Model</div>
        </div>
        """)
    with col_w2:
        st.html("""
        <div class="saas-card" style="padding: 18px 20px;">
            <div class="card-ambient-highlight"></div>
            <div class="kpi-label">Parameters</div>
            <div style="font-size: 24px; font-weight: 800; color: #818cf8; margin: 4px 0;">7.61 Billion</div>
            <div style="font-size: 12px; color: var(--text-muted);">28 Layers · 3584 Hidden</div>
        </div>
        """)
    with col_w3:
        st.html("""
        <div class="saas-card" style="padding: 18px 20px;">
            <div class="card-ambient-highlight"></div>
            <div class="kpi-label">Context Window</div>
            <div style="font-size: 24px; font-weight: 800; color: #c084fc; margin: 4px 0;">32,768</div>
            <div style="font-size: 12px; color: var(--text-muted);">Full Sequence Tokens</div>
        </div>
        """)
    with col_w4:
        st.html("""
        <div class="saas-card" style="padding: 18px 20px;">
            <div class="card-ambient-highlight"></div>
            <div class="kpi-label">Model Weights</div>
            <div style="font-size: 24px; font-weight: 800; color: #34d399; margin: 4px 0;">15.2 GB</div>
            <div style="font-size: 12px; color: var(--text-muted);">4 Shards (SafeTensors)</div>
        </div>
        """)

    st.markdown("#### 💬 **Live ChatML Prompt Generation Inspector**")
    prompt_sample = engine.llm.build_chatml_prompt(
        current_metrics,
        recent_logs=[
            {"timestamp": time.strftime("%H:%M:%S"), "level": "WARNING", "message": "High allocation detected in container memory pool."},
            {"timestamp": time.strftime("%H:%M:%S"), "level": "ERROR", "message": "Health check degraded: pod responding > 300ms."}
        ],
        anomaly_type=rca_report.get("anomaly_type", "normal")
    )
    st.code(prompt_sample, language="markdown")

    st.markdown("#### 📦 **Model Storage & Shard Verification**")
    model_dir = os.path.join(PROJECT_ROOT, "telemetry_rca_model")
    if os.path.exists(model_dir):
        files_in_m = sorted(os.listdir(model_dir))
        f_stats = []
        for f in files_in_m:
            fp = os.path.join(model_dir, f)
            sz = os.path.getsize(fp) / (1024 * 1024)
            f_stats.append({"File": f, "Size (MB)": f"{sz:.2f} MB", "Type": "Weights Shard" if f.endswith(".safetensors") else "Config / Tokenizer"})
        st.dataframe(pd.DataFrame(f_stats), width="stretch")


# =========================================================
# PAGE 6: INCIDENT POST-MORTEM ARCHIVE & EMAIL ALERTS
# =========================================================
with tab_archive:
    st.html("""
    <div style="margin-bottom: 20px;">
        <h1 style="font-size: 24px; font-weight: 800; color: #fff; margin: 0 0 4px;">Incident Post-Mortems & SRE Alerts</h1>
        <p style="font-size: 14px; color: var(--text-secondary); margin: 0;">Audit trail of all autonomous RCA reports and HTML notification alerts.</p>
    </div>
    """)

    col_em1, col_em2 = st.columns([1, 1])

    with col_em1:
        st.markdown("#### 📁 **Incident Post-Mortem Audit Archive**")
        reports_dir = os.path.join(PROJECT_ROOT, "data", "rca_reports")
        report_files = sorted(glob.glob(os.path.join(reports_dir, "INC-*.md")), reverse=True)
        if report_files:
            chosen_file = st.selectbox("Select Incident Post-Mortem:", report_files, format_func=lambda x: f"📄 {os.path.basename(x)}")
            if chosen_file and os.path.exists(chosen_file):
                with open(chosen_file, "r", encoding="utf-8") as f:
                    content_md = f.read()
                st.download_button("⬇️ Download Markdown Report", data=content_md, file_name=os.path.basename(chosen_file), mime="text/markdown")
                st.markdown(content_md)
        else:
            st.info("No incident reports found yet in data/rca_reports/.")

    with col_em2:
        st.markdown("#### 📧 **Automated SRE Email Alert Dispatcher**")
        if st.button("🚀 Trigger Test Alert Dispatch", type="primary", width="stretch"):
            test_rca = {
                "incident_id": f"INC-TEST-{int(time.time())}",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "anomaly_type": "memory_leak",
                "severity": "CRITICAL",
                "root_cause": "Container Memory Leak / Impending OOMKilled Event",
                "mechanism": "Heap allocation climbing continuously past safe operational limits (488 MB / 512 MB).",
                "imminent_risk": "Imminent Pod OOMKilled by Linux kernel (ExitCode 137).",
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
                st.success("✅ Test Alert generated and saved!")

        html_emails = sorted(glob.glob(os.path.join(reports_dir, "email_*.html")), reverse=True)
        if html_emails:
            st.caption("Latest Rendered HTML Email Preview:")
            with open(html_emails[0], "r", encoding="utf-8") as f:
                html_code = f.read()
            st.components.v1.html(html_code, height=480, scrolling=True)


# ---------------------------------------------------------
# Auto-refresh loop
# ---------------------------------------------------------
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
