# ==============================================================================
# install_monitoring.ps1 - Automated Monitoring Stack Installer via Helm
# Deploys: Prometheus, Grafana, Loki, Promtail, and ServiceMonitor
# ==============================================================================

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
$MonitoringDir = "$ProjectRoot\monitoring"

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "   AIOps Platform - Monitoring Stack Deployment   " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# 1. Verify Helm Installation
Write-Host "`n[1/5] Checking Helm package manager..." -ForegroundColor Yellow
if (-not (Get-Command helm -ErrorAction SilentlyContinue)) {
    Write-Host "[!] Helm CLI was not found in PATH." -ForegroundColor Yellow
    Write-Host "    Attempting to install Helm automatically via winget..." -ForegroundColor Cyan
    winget install --id Helm.Helm --silent --accept-source-agreements --accept-package-agreements
    
    # Refresh PATH in current process
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    
    if (-not (Get-Command helm -ErrorAction SilentlyContinue)) {
        Write-Host "[-] Could not detect helm after install. Please restart your terminal and re-run." -ForegroundColor Red
        exit 1
    }
}
$helmVersion = (helm version --short)
Write-Host "[+] Helm is available: $helmVersion" -ForegroundColor Green

# 2. Verify Cluster Connection
Write-Host "`n[2/5] Checking Kubernetes cluster connectivity..." -ForegroundColor Yellow
$k8sContext = (kubectl config current-context 2>$null)
if (-not $k8sContext) {
    Write-Host "[-] No active Kubernetes context found! Ensure Minikube / Docker Desktop is running." -ForegroundColor Red
    exit 1
}
Write-Host "[+] Connected to cluster context: $k8sContext" -ForegroundColor Green

# 3. Create Monitoring Namespace
Write-Host "`n[3/5] Ensuring 'monitoring' namespace exists..." -ForegroundColor Yellow
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

# 4. Add & Update Helm Repositories
Write-Host "`n[4/5] Adding Prometheus & Grafana Helm repositories..." -ForegroundColor Yellow
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts --force-update
helm repo add grafana https://grafana.github.io/helm-charts --force-update
helm repo update

# 5. Deploy Prometheus Stack & Loki
Write-Host "`n[5/5] Deploying kube-prometheus-stack and loki-stack..." -ForegroundColor Yellow

$promValues = Join-Path $MonitoringDir "prometheus-values.yaml"
$lokiValues = Join-Path $MonitoringDir "loki-values.yaml"
$serviceMonitor = Join-Path $MonitoringDir "backend-servicemonitor.yaml"

Write-Host "  -> Installing/Upgrading Prometheus & Grafana (kube-prometheus-stack)..." -ForegroundColor Cyan
helm upgrade --install prometheus-stack prometheus-community/kube-prometheus-stack `
    --namespace monitoring `
    -f $promValues `
    --timeout 10m

Write-Host "  -> Installing/Upgrading Loki & Promtail (loki-stack)..." -ForegroundColor Cyan
helm upgrade --install loki-stack grafana/loki-stack `
    --namespace monitoring `
    -f $lokiValues `
    --timeout 5m

Write-Host "  -> Registering ServiceMonitor for aiops-backend..." -ForegroundColor Cyan
kubectl apply -f $serviceMonitor

Write-Host "`n=================================================" -ForegroundColor Green
Write-Host "   Monitoring Stack Successfully Deployed!        " -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Green
Write-Host "`nNext steps to access dashboards:" -ForegroundColor Cyan
Write-Host "  1. Run port-forwarding: .\scripts\port_forward_monitoring.ps1" -ForegroundColor White
Write-Host "  2. Access Prometheus:   http://localhost:9090" -ForegroundColor White
Write-Host "  3. Access Grafana:      http://localhost:3000 (User: admin / Pass: admin)" -ForegroundColor White
Write-Host "  4. Import Dashboard:    Upload monitoring\grafana-dashboard-aiops.json into Grafana" -ForegroundColor White
