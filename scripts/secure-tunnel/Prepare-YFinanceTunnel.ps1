# Prepare the existing read-only Meridyen YFinance MCP for an OpenAI Secure MCP Tunnel.
# No API keys are read or stored. Does not affect Render, Social V5, OpenBB, or S-series.
[CmdletBinding()]
param(
  [string]$TunnelClientExe = "C:\Meridyen\Tunel\tunnel-client-v0.0.16-windows-amd64\tunnel-client.exe",
  [string]$InstallFolder = "C:\Meridyen\YFinanceTunnel",
  [string]$TunnelId = ""
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $TunnelClientExe -PathType Leaf)) {
  throw "tunnel-client.exe not found: $TunnelClientExe"
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git for Windows is missing." }
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher (py) not found. Install Python 3.11 x64." }

& py -3.11 --version
if ($LASTEXITCODE -ne 0) { throw "Python 3.11 x64 is required for the prepared local service." }
$branch = "deploy/yfinance-mcp-render-free"
if (-not (Test-Path -LiteralPath $InstallFolder)) {
  & git clone --single-branch --depth 1 --branch $branch "https://github.com/sertactan/M10.git" $InstallFolder
  if ($LASTEXITCODE -ne 0) { throw "Git clone failed. Ensure GitHub repository access." }
} elseif (-not (Test-Path -LiteralPath (Join-Path $InstallFolder ".git"))) {
  throw "InstallFolder already exists and is not a Git checkout. Choose another folder."
} else {
  Write-Host "Using existing checkout without modifying it: $InstallFolder"
}
$module = Join-Path $InstallFolder "integrations\yfinance-mcp"
$entry = Join-Path $module "local_tunnel_stdio.py"
$requirements = Join-Path $module "requirements.txt"
if (-not (Test-Path $entry) -or -not (Test-Path $requirements)) {
  throw "Missing YFinance MCP files. Check deployment branch."
}
$venv = Join-Path $module ".venv"
if (-not (Test-Path -LiteralPath (Join-Path $venv "Scripts\python.exe"))) {
  & py -3.11 -m venv $venv
  if ($LASTEXITCODE -ne 0) { throw "Python virtual environment creation failed." }
}
$python = Join-Path $venv "Scripts\python.exe"
& $python -m pip install --disable-pip-version-check -r $requirements
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
& $python -m py_compile $entry (Join-Path $module "yfinance_readonly.py")
if ($LASTEXITCODE -ne 0) { throw "Python source compilation failed." }

if (-not $TunnelId) { $TunnelId = Read-Host "Enter meridyen-yfinance tunnel ID (tunnel_...)" }
if ($TunnelId -cnotmatch '^tunnel_[0-9a-f]{32}$') {
  throw "Invalid tunnel ID format; copy the ID from the OpenAI Tunnels settings."
}
$command = '"{0}" "{1}"' -f $python, $entry
& $TunnelClientExe init --sample sample_mcp_stdio_local --profile meridyen-yfinance --tunnel-id $TunnelId --mcp-command $command
if ($LASTEXITCODE -ne 0) {
  throw "tunnel-client profile init failed. If profile already exists, inspect: tunnel-client profiles list"
}
Write-Host "SUCCESS: Python 3.11 + six read-only YFinance MCP tool definitions prepared."
Write-Host "SUCCESS: OpenAI profile meridyen-yfinance created."
Write-Host "Next step: stop the demo tunnel process before starting the new profile."
Write-Host "No API secret has been stored."
