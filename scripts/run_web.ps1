# Starts the console + API on one origin (port 8001) and the `orbitguard-web` Cloudflare Tunnel connector
# (orbitguard.<domain> -> localhost:8001). Idempotent. Token lives only in %USERPROFILE%\.cloudflared\orbitguard-web.token.
$repo = Split-Path -Parent $PSScriptRoot
$tokenFile = Join-Path $env:USERPROFILE ".cloudflared\orbitguard-web.token"
if (-not (Test-Path $tokenFile)) { Write-Error "Missing $tokenFile"; exit 1 }

if (-not (Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue)) {
  Start-Process python -ArgumentList "scripts/serve.py","--with-web","--port","8001" -WorkingDirectory $repo -WindowStyle Hidden `
    -RedirectStandardOutput "$env:TEMP\orbitguard-web.log" -RedirectStandardError "$env:TEMP\orbitguard-web.err.log"
}

$running = Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" |
  Where-Object { $_.CommandLine -like "*orbitguard-web.token*" }
if (-not $running) {
  Start-Process cloudflared -ArgumentList "tunnel","run","--token-file",$tokenFile -WindowStyle Hidden `
    -RedirectStandardOutput "$env:TEMP\orbitguard-web-tunnel.log" -RedirectStandardError "$env:TEMP\orbitguard-web-tunnel.err.log"
}
