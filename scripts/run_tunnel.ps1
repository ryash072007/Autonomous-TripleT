# Starts the OrbitGuard API (port 8000) if needed, then the `orbitguard` Cloudflare Tunnel connector
# (api.<domain> -> localhost:8000). Idempotent. Token lives only in %USERPROFILE%\.cloudflared\orbitguard.token.
$repo = Split-Path -Parent $PSScriptRoot
$tokenFile = Join-Path $env:USERPROFILE ".cloudflared\orbitguard.token"
if (-not (Test-Path $tokenFile)) { Write-Error "Missing $tokenFile"; exit 1 }

if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
  Start-Process python -ArgumentList "scripts/serve.py" -WorkingDirectory $repo -WindowStyle Hidden `
    -RedirectStandardOutput "$env:TEMP\orbitguard-api.log" -RedirectStandardError "$env:TEMP\orbitguard-api.err.log"
}

$running = Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" |
  Where-Object { $_.CommandLine -like "*orbitguard.token*" }
if (-not $running) {
  Start-Process cloudflared -ArgumentList "tunnel","run","--token-file",$tokenFile -WindowStyle Hidden `
    -RedirectStandardOutput "$env:TEMP\orbitguard-tunnel.log" -RedirectStandardError "$env:TEMP\orbitguard-tunnel.err.log"
}
