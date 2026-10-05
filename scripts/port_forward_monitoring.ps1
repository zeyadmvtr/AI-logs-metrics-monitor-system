# ==============================================================================
# port_forward_monitoring.ps1 - Port forward Prometheus, Grafana, and Loki
# ==============================================================================

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "   AIOps Monitoring Stack - Port Forward Helper   " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# Stop existing port-forward jobs if any
Get-Job -Name "pf-*" -ErrorAction SilentlyContinue | Stop-Job -PassThru | Remove-Job

Write-Host "`nStarting background port-forwarding jobs..." -ForegroundColor Yellow

# 1. Prometheus -> http://localhost:9090
Start-Job -Name "pf-prom" -ScriptBlock {
    kubectl port-forward svc/prometheus-stack-kube-prom-prometheus 9090:9090 -n monitoring
} | Out-Null
Write-Host "[+] Prometheus port-forward started: http://localhost:9090" -ForegroundColor Green

# 2. Grafana -> http://localhost:3000
Start-Job -Name "pf-grafana" -ScriptBlock {
    kubectl port-forward svc/prometheus-stack-grafana 3000:80 -n monitoring
} | Out-Null
Write-Host "[+] Grafana port-forward started:    http://localhost:3000 (admin / admin)" -ForegroundColor Green

# 3. Loki -> http://localhost:3100
Start-Job -Name "pf-loki" -ScriptBlock {
    kubectl port-forward svc/loki-stack 3100:3100 -n monitoring
} | Out-Null
Write-Host "[+] Loki log store port-forward:     http://localhost:3100" -ForegroundColor Green

Write-Host "`nAll 3 monitoring services are active in background jobs." -ForegroundColor Cyan
Write-Host "To terminate background port-forwards later, run:" -ForegroundColor Gray
Write-Host "  Get-Job -Name 'pf-*' | Stop-Job | Remove-Job" -ForegroundColor White
