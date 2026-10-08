# Meridyen Secure MCP Tunnel — prepare 3 private stdio MCP servers on Windows.
# Does not create Platform tunnel IDs or install any OpenAI API secret.
[CmdletBinding()]
param(
  [string]$Root = (Join-Path $HOME "MeridyenSecureTunnel"),
  [string]$TunnelClientExe = (Join-Path $HOME "Downloads\tunnel-client.exe"),
  [string]$YFinanceTunnelId = "",
  [string]$SocialTunnelId = "",
  [string]$OpenBBTunnelId = "",
  [switch]$SkipDependencies
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git for Windows is required" }
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher py is required (Python 3.11 recommended)" }

$items = @(
  @{ Name="yfinance"; Branch="deploy/yfinance-mcp-render-free"; Folder="integrations/yfinance-mcp"; Entry="local_tunnel_stdio.py"; Id=$YFinanceTunnelId; Build=$false },
  @{ Name="social"; Branch="deploy/social-v5-render-free"; Folder="social-v5-render"; Entry="local_tunnel_stdio.py"; Id=$SocialTunnelId; Build=$false },
  @{ Name="openbb"; Branch="deploy/openbb-v5-mcp-render-free"; Folder="openbb-v5-render"; Entry="local_tunnel_stdio.py"; Id=$OpenBBTunnelId; Build=$true }
)
New-Item -ItemType Directory -Force -Path $Root | Out-Null
foreach ($item in $items) {
  $repo = Join-Path $Root $item.Name
  if (-not (Test-Path $repo)) {
    & git clone --single-branch --depth 1 --branch $item.Branch "https://github.com/sertactan/M10.git" $repo
    if ($LASTEXITCODE -ne 0) { throw "Git clone failed: $($item.Name)" }
  } else {
    Write-Host "Existing checkout kept unchanged: $repo"
  }
  $module = Join-Path $repo $item.Folder
  $entry = Join-Path $module $item.Entry
  if (-not (Test-Path $entry)) { throw "Missing local MCP entry: $entry" }
  $venv = Join-Path $module ".venv"
  if (-not (Test-Path $venv)) {
    & py -3.11 -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Install Python 3.11 and retry" }
  }
  $python = Join-Path $venv "Scripts\python.exe"
  if (-not $SkipDependencies) {
    & $python -m pip install --disable-pip-version-check -r (Join-Path $module "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "Dependency install failed: $($item.Name)" }
    if ($item.Build) {
      $builder = Join-Path $venv "Scripts\openbb-build.exe"
      if (Test-Path $builder) {
        & $builder
        if ($LASTEXITCODE -ne 0) { throw "OpenBB build failed" }
      } else { Write-Warning "OpenBB build executable not found; check OpenBB installation." }
    }
  }
  if ($item.Id) {
    if ($item.Id -notmatch '^tunnel_[A-Za-z0-9_-]{16,}$') {
      throw "Unexpected OpenAI tunnel ID format for $($item.Name). Verify in Platform settings."
    }
    if (-not (Test-Path $TunnelClientExe)) {
      throw "Download tunnel-client.exe from the official OpenAI release and pass -TunnelClientExe."
    }
    $command = ('"{0}" "{1}"' -f $python, $entry)
    & $TunnelClientExe init --sample sample_mcp_stdio_local --profile ("meridyen-" + $item.Name) --tunnel-id $item.Id --mcp-command $command
    if ($LASTEXITCODE -ne 0) { throw "tunnel-client init failed: $($item.Name)" }
  }
  Write-Host ("Prepared [{0}] at {1}" -f $item.Name, $entry)
}
Write-Host "All 3 MCP sources prepared. Do not change Render public endpoints until ChatGPT tunnel validation succeeds."
Write-Host "To run: .\Run-MeridyenTunnel.ps1 -Service yfinance -TunnelClientExe '<path to tunnel-client.exe>'"
