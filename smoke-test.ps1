#!/usr/bin/env pwsh
# Local smoke test script - replicates GitHub Actions smoke test

Write-Host "🔨 Building Docker image..." -ForegroundColor Cyan
docker build -t relife-financial:smoke-test .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker build failed" -ForegroundColor Red
    exit 1
}

Write-Host "`n🚀 Starting API container..." -ForegroundColor Cyan
$containerId = docker run -d `
  --name relife-api `
  -p 9090:9090 `
  -e API_HOST=0.0.0.0 `
  -e API_PORT=9090 `
  -e SUPABASE_URL=http://localhost:54321 `
  -e SUPABASE_KEY=dummy-key-for-testing `
  -e KEYCLOAK_CLIENT_ID=test-client `
  -e KEYCLOAK_CLIENT_SECRET=test-secret `
  relife-financial:smoke-test

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to start container" -ForegroundColor Red
    exit 1
}

Write-Host "Container ID: $containerId" -ForegroundColor Gray

Write-Host "`n⏳ Waiting for API to be ready..." -ForegroundColor Cyan
$maxAttempts = 30
$success = $false

for ($i = 1; $i -le $maxAttempts; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:9090/docs" -TimeoutSec 1 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ API is ready! OpenAPI docs accessible (attempt $i/$maxAttempts)" -ForegroundColor Green
            $success = $true
            break
        }
    } catch {
        Write-Host "Attempt $i/$maxAttempts: API not ready yet..." -ForegroundColor Yellow
    }
    Start-Sleep -Seconds 1
}

Write-Host "`n📋 Container logs:" -ForegroundColor Cyan
docker logs relife-api

Write-Host "`n🧹 Cleaning up..." -ForegroundColor Cyan
docker stop relife-api | Out-Null
docker rm relife-api | Out-Null

if ($success) {
    Write-Host "`n✅ SMOKE TEST PASSED" -ForegroundColor Green
    exit 0
} else {
    Write-Host "`n❌ SMOKE TEST FAILED - API did not start within 30 seconds" -ForegroundColor Red
    exit 1
}
