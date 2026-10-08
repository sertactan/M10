# Run one existing OpenAI Secure MCP Tunnel profile; API key is not saved to disk.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)]
 [ValidateSet("yfinance", "social", "openbb")]
 [string]$Service,
 [string]$TunnelClientExe = (Join-Path $HOME "Downloads\tunnel-client.exe")
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path $TunnelClientExe)) {
  throw "Download official tunnel-client.exe and pass -TunnelClientExe"
}
Write-Host "Enter your OpenAI Platform runtime API key (input hidden; never paste in chat)."
$secret = Read-Host -AsSecureString "CONTROL_PLANE_API_KEY"
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
  $env:CONTROL_PLANE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  & $TunnelClientExe doctor --profile ("meridyen-" + $Service) --explain
  if ($LASTEXITCODE -ne 0) { throw "Tunnel doctor failed. Check ID, platform roles and MCP source." }
  & $TunnelClientExe run --profile ("meridyen-" + $Service)
  if ($LASTEXITCODE -ne 0) { throw "Tunnel client stopped with an error" }
} finally {
  Remove-Item Env:\CONTROL_PLANE_API_KEY -ErrorAction SilentlyContinue
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
