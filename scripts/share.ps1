# Share the DreamCatcher shop publicly via a free Cloudflare Quick Tunnel.
#
#   powershell -ExecutionPolicy Bypass -File scripts\share.ps1
#
# Starts the dev server (session cookie allowed over HTTP so the tunnel works) and
# opens a temporary public HTTPS URL (https://<random>.trycloudflare.com).
# No Cloudflare account needed. The link lives only while this script runs and your PC is on.
# Press Ctrl+C to stop both.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$port = 8000
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

# Ensure cloudflared is present (download once if missing).
$cf = Join-Path $root "cloudflared.exe"
if (-not (Test-Path $cf)) {
    Write-Host "Downloading cloudflared..." -ForegroundColor Cyan
    Invoke-WebRequest -UseBasicParsing `
        -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" `
        -OutFile $cf
}

# Start the server (cart needs the session cookie to work over the tunnel's HTTP hop).
$env:SESSION_HTTPS_ONLY = "false"
Write-Host "Starting server on http://127.0.0.1:$port ..." -ForegroundColor Cyan
$server = Start-Process -FilePath $py `
    -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","$port","--log-level","warning" `
    -PassThru -NoNewWindow

Start-Sleep -Seconds 3
Write-Host "Opening Cloudflare tunnel (watch for the https://...trycloudflare.com URL)..." -ForegroundColor Green
try {
    & $cf tunnel --url "http://127.0.0.1:$port" --no-autoupdate
}
finally {
    if ($server -and -not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    Write-Host "Stopped server and tunnel." -ForegroundColor Yellow
}
