# ==============================================================================
# verify_telemetry.ps1 - Validates Prometheus & Loki APIs and runs Ingestion Worker
# ==============================================================================

param (
    [string]$PrometheusUrl = "http://localhost:9090",
    [string]$LokiUrl = "http://localhost:3100"
)

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "   AIOps Platform - Telemetry Verification        " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

function Test-Service-Endpoint {
    param ([string]$Name, [string]$Uri)
    Write-Host -NoNewline "[CHECK] $Name ($Uri) ... "
    try {
        $res = Invoke-WebRequest -Uri $Uri -Method Get -TimeoutSec 5 -ErrorAction Stop
        if ($res.StatusCode -eq 200) {
            Write-Host "ONLINE (HTTP 200)" -ForegroundColor Green
            return $true
        } else {
            Write-Host "STATUS $($res.StatusCode)" -ForegroundColor Yellow
            return $false
        }
    } catch {
        Write-Host "OFFLINE ($($_.Exception.Message))" -ForegroundColor Red
        return $false
    }
}

# 1. Check Prometheus Readiness
$promOk = Test-Service-Endpoint "Prometheus API" "$PrometheusUrl/-/ready"

# 2. Check Grafana Health
$grafanaOk = Test-Service-Endpoint "Grafana UI" "http://localhost:3000/api/health"

# 3. Check Loki Readiness
$lokiOk = Test-Service-Endpoint "Loki Log Store" "$LokiUrl/ready"

# 4. Run Telemetry Ingestion Worker in test mode (--once)
Write-Host "`n[TEST] Executing Telemetry Ingestion Worker (--once)..." -ForegroundColor Yellow
$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
$WorkerScript = Join-Path $ProjectRoot "telemetry\ingestion_worker.py"

python $WorkerScript --once

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[+] Ingestion worker executed successfully and recorded telemetry snapshot!" -ForegroundColor Green
} else {
    Write-Host "`n[-] Ingestion worker exited with error code $LASTEXITCODE." -ForegroundColor Red
}

Write-Host "`n=================================================" -ForegroundColor Cyan
Write-Host "   Telemetry Pipeline Verification Completed      " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
