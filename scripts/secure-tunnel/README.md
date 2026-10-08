# Meridyen — migrate all 3 existing data MCP services to OpenAI Secure MCP Tunnel

Status: **PREPARED, NOT CONNECTED**. Do not mark LIVE_CONNECTED until ChatGPT calls an actual tool through the tunnel.

## In scope
- YFinance six read-only tools on `deploy/yfinance-mcp-render-free`
- Social V5 four read-only tools on `deploy/social-v5-render-free`
- OpenBB V5 four read-only tools on `deploy/openbb-v5-mcp-render-free`
- S1, S2, S14, S15.3 and S16 calculation logic and M10 project remain untouched.
- Other projects without existing MCP tool servers are not automatically tunneled.

## Important difference
A tunnel **does not make an existing Render public HTTPS service private**. The
private MCP server and tunnel-client must both run on the local/trusted host.
For that reason three local `stdio` MCP entrypoints have been added to the
deployment branches. Do not point a tunnel at the old public Render URLs and
claim privacy.

## OpenAI prerequisites (manual account owner action)
1. Open https://platform.openai.com/ and its Tunnels settings.
2. Confirm Tunnels Read + Manage and Read + Use permissions.
3. Create three tunnels: meridyen-yfinance, meridyen-social, meridyen-openbb.
   Record their `tunnel_...` IDs (these identifiers are not API secrets).
4. Associate each tunnel with the Platform organization and the intended
   ChatGPT workspace.
5. Create a runtime Platform API key; keep it private. API Platform billing
   is separate from ChatGPT Plus. Do not commit the key or paste it into chat.
6. Download the official Windows `tunnel-client.exe` at:
   https://github.com/openai/tunnel-client/releases/latest

## Windows install
Python 3.11, Git for Windows and an up-to-date official tunnel-client.exe required.
Open PowerShell from this `scripts/secure-tunnel` folder and run:

```powershell
.\Setup-MeridyenTunnels.ps1 `
  -TunnelClientExe "C:\path\to\tunnel-client.exe" `
  -YFinanceTunnelId "tunnel_YOUR_YFINANCE_ID" `
  -SocialTunnelId "tunnel_YOUR_SOCIAL_ID" `
  -OpenBBTunnelId "tunnel_YOUR_OPENBB_ID"
```

Run each profile in a separate foreground PowerShell terminal:

```powershell
.\Run-MeridyenTunnel.ps1 -Service yfinance -TunnelClientExe "C:\path\to\tunnel-client.exe"
.\Run-MeridyenTunnel.ps1 -Service social   -TunnelClientExe "C:\path\to\tunnel-client.exe"
.\Run-MeridyenTunnel.ps1 -Service openbb   -TunnelClientExe "C:\path\to\tunnel-client.exe"
```

Each process prompts for the key without printing it. For unattended production
use a properly protected host-managed secret store and service supervisor;
interactive PowerShell is intended for initial validation.

## ChatGPT
ChatGPT Plugins -> + -> Add custom MCP server -> Connection: **Tunnel**.
Select the tunnel ID associated with ChatGPT workspace. Create the connected
plugin, check discovered tools, start a new conversation, run:
- YFinance `get_stock_quote(INOD)`
- Social `social_status()`
- OpenBB `openbb_status()` and optionally `openbb_spy_test()`.

Depending on host/plugin schema, separate tunnel-backed custom plugins might
need to be selected; **do not invent a `mcp.json` tunnel type**. The existing
Meridyen plugin still includes the old remote URLs until tunnel testing
proves the new transport and user approves the cutover.

## Retirement plan AFTER the tunnel works
- Disconnect legacy remote MCP links from Meridyen's portable and legacy
  `mcp.json` when host configuration supports the tunnel replacement.
- Disable old Render public ingress; never remove live services first.
- Remove self-hosted YFinance OAuth password screen *only when its HTTP
  service is no longer used*. The local stdio path has no OAuth screen.
- Preserve the frozen canonical models and historical evidence requirements.

## References
https://developers.openai.com/api/docs/guides/secure-mcp-tunnels
https://developers.openai.com/plugins/deploy/connect-chatgpt
https://github.com/openai/tunnel-client/releases/latest

No paid API is configured by these files. Platform key usage may incur costs;
verify billing in the Platform console before connecting.
