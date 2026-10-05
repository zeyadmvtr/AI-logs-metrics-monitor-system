# ==============================================================================
# test_endpoints.ps1 - Automated Sanity & Health Verification Script
# ==============================================================================

param (
    [string]$BaseUrl = "http://localhost:8000"
)

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "   AIOps Platform - End-to-End API Verification   " -ForegroundColor Cyan
Write-Host "   Target: $BaseUrl" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

function Assert-Endpoint {
    param (
        [string]$Name,
        [scriptblock]$Action
    )
    Write-Host -NoNewline "[TEST] $Name ... "
    try {
        $result = & $Action
        Write-Host "PASSED" -ForegroundColor Green
        return $result
    } catch {
        Write-Host "FAILED" -ForegroundColor Red
        Write-Host "       Error: $($_.Exception.Message)" -ForegroundColor DarkRed
        return $null
    }
}

# 1. Test Root
Assert-Endpoint "Root Endpoint (/)" {
    $res = Invoke-RestMethod -Uri "$BaseUrl/" -Method Get -TimeoutSec 5
    if ($res.service -ne "aiops-backend") { throw "Unexpected service name: $($res.service)" }
    return $res
}

# 2. Test Liveness Probe
Assert-Endpoint "Liveness Probe (/api/v1/health/live)" {
    $res = Invoke-RestMethod -Uri "$BaseUrl/api/v1/health/live" -Method Get -TimeoutSec 5
    if ($res.status -ne "UP") { throw "Liveness status is not UP: $($res.status)" }
    Write-Host "       Uptime: $($res.uptime_seconds)s" -ForegroundColor Gray
    return $res
}

# 3. Test Readiness Probe
Assert-Endpoint "Readiness Probe (/api/v1/health/ready)" {
    $res = Invoke-RestMethod -Uri "$BaseUrl/api/v1/health/ready" -Method Get -TimeoutSec 5
    if ($res.status -ne "READY") { throw "Readiness status is not READY: $($res.status)" }
    Write-Host "       Database: $($res.database.status) | Redis: $($res.redis.status)" -ForegroundColor Gray
    return $res
}

# 4. Test Orders Creation
$createdOrder = Assert-Endpoint "Create Business Order (POST /api/v1/orders)" {
    $body = @{
        customer_email = "aiops-verifier@nti.edu.eg"
        item_name = "Cloud GPU Instance A100"
        quantity = 2
        total_amount = 6500.00
    } | ConvertTo-Json

    $res = Invoke-RestMethod -Uri "$BaseUrl/api/v1/orders" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 5
    if (-not $res.id) { throw "No order ID returned" }
    Write-Host "       Created Order ID: $($res.id) for $($res.customer_email)" -ForegroundColor Gray
    return $res
}

# 5. Test Orders Cache / Retrieval
if ($createdOrder) {
    Assert-Endpoint "Retrieve Order (GET /api/v1/orders/$($createdOrder.id))" {
        $res = Invoke-RestMethod -Uri "$BaseUrl/api/v1/orders/$($createdOrder.id)" -Method Get -TimeoutSec 5
        if ($res.id -ne $createdOrder.id) { throw "Order ID mismatch" }
        return $res
    }
}

# 6. Test Prometheus Metrics
Assert-Endpoint "Prometheus Metrics (/metrics)" {
    $res = Invoke-WebRequest -Uri "$BaseUrl/metrics" -Method Get -TimeoutSec 5 -UseBasicParsing
    if ($res.StatusCode -ne 200) { throw "HTTP $($res.StatusCode)" }

    $content = $res.Content
    if ($content -notmatch "aiops_backend" -and $content -notmatch "http") {
        throw "Expected Prometheus metric identifiers not found"
    }
    $metricLines = ($content -split "`n" | Where-Object { $_ -notmatch "^#" -and $_.Trim() -ne "" }).Count
    Write-Host "       Exported Active Metrics: $metricLines" -ForegroundColor Gray
    return $res
}

Write-Host "`n=================================================" -ForegroundColor Green
Write-Host "   All Sanity Tests Completed!                    " -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Green
