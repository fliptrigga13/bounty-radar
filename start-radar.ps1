Write-Host "=======================================================" -ForegroundColor Green
Write-Host "   🛰️  BOUNTY RADAR: UNIFIED A2A SERVER & POLLER" -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Green

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$env:RADAR_CHANNEL="discord"
if (Test-Path ".env.local") {
  Get-Content .env.local | ForEach-Object {
    if ($_ -match '^([^#=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim().Trim("`"'"), "Process") }
  }
}

Write-Host "• A2A Server Port:   $($env:A2A_PORT ?? '8080')" -ForegroundColor Cyan
Write-Host "• Alert Channel:     $($env:RADAR_CHANNEL)" -ForegroundColor Cyan
Write-Host "• Database:          $($env:RADAR_DB ?? 'radar.db')" -ForegroundColor Cyan
Write-Host "• Health Endpoint:   http://localhost:8080/health" -ForegroundColor Cyan
Write-Host "• Agent Card:        http://localhost:8080/.well-known/agent-card.json" -ForegroundColor Cyan
Write-Host "• A2A RPC Endpoint:  http://localhost:8080/a2a" -ForegroundColor Cyan
Write-Host ""
Write-Host "Launching unified server (A2A + Background Discovery)..." -ForegroundColor Yellow

python a2a_server.py
