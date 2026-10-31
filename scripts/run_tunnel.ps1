# Starts the Cloudflare Tunnel connector for the OrbitGuard backend.
# The tunnel token lives only in %USERPROFILE%\.cloudflared\orbitguard.token (never committed).
$tokenFile = Join-Path $env:USERPROFILE ".cloudflared\orbitguard.token"
if (-not (Test-Path $tokenFile)) { Write-Error "Missing $tokenFile"; exit 1 }
cloudflared tunnel run --token-file $tokenFile
