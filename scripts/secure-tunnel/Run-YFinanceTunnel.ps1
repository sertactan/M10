# Start the prepared private Meridyen YFinance MCP tunnel.
# API key is copied locally from clipboard at the time of prompting; never passed in CLI args or written to disk.
[CmdletBinding()]
param(
  [string]$TunnelClientExe = "C:\Meridyen\Tunel\tunnel-client-v0.0.16-windows-amd64\tunnel-client.exe"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $TunnelClientExe -PathType Leaf)) { throw "tunnel-client.exe not found" }
Write-Host "Before proceeding, revoke any previously exposed API keys in the OpenAI Platform."
Read-Host "Copy a NEW OpenAI runtime API key in your browser, return and press Enter here"
$key = Get-Clipboard -Raw
# PowerShell 5.1 rejects an empty clipboard assignment, so use one space instead.
Set-Clipboard -Value " "
if (-not $key) { throw "No text was found in the Windows clipboard." }
$key = $key.Trim()
if (-not $key.StartsWith("sk-") -or $key.Length -lt 40) {
  throw "Clipboard does not contain an OpenAI runtime API key. No network calls made."
}
try {
  $env:CONTROL_PLANE_API_KEY = $key
  $key = $null
  & $TunnelClientExe doctor --profile meridyen-yfinance --explain
  if ($LASTEXITCODE -ne 0) { throw "Tunnel doctor preflight failed. Verify Python dependencies, tunnel ID and API key permissions." }
  Write-Host "Starting real read-only YFinance MCP. Leave this terminal open."
  & $TunnelClientExe run --profile meridyen-yfinance --health.listen-addr 127.0.0.1:8091
  if ($LASTEXITCODE -ne 0) { throw "Tunnel exited with an error." }
} finally {
  Remove-Item Env:\CONTROL_PLANE_API_KEY -ErrorAction SilentlyContinue
  $key = $null
}
