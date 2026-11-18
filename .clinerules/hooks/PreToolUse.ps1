# Cline global PreToolUse hook: HYBA-MCP gatekeeper.
# Blocks every tool call in a Cline task until that task has called a tool on
# the 'hyba-mcp' MCP server. Cline 4.x names MCP tools '<server>__<tool>',
# so a hyba-mcp call arrives as toolName 'hyba-mcp__<tool>'.
# Cline runs this as: powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File <this file>
# Input: JSON on stdin. Output: {"cancel":bool,"contextModification":str,"errorMessage":str} on stdout.

$ErrorActionPreference = "Stop"
$hybaServer = "hyba-mcp"
# Tools that only talk to the user stay allowed, so Cline can report a down server.
$alwaysAllowed = @("ask_question", "ask_followup_question", "plan_mode_respond")

function Send-Verdict($obj) {
    [Console]::Out.Write(($obj | ConvertTo-Json -Compress))
    exit 0
}

try { [Console]::InputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$rawInput = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($rawInput)) { Send-Verdict @{ cancel = $false } }

try { $payload = $rawInput | ConvertFrom-Json } catch { Send-Verdict @{ cancel = $false } }

$taskId = [string]$payload.taskId
if ([string]::IsNullOrWhiteSpace($taskId)) { $taskId = "default_session" }
$safeTaskId = $taskId -replace '[^A-Za-z0-9._-]', '_'

$toolName = ""
$params = $null
if ($payload.preToolUse) {
    $toolName = [string]$payload.preToolUse.toolName
    $params = $payload.preToolUse.parameters
}
if (-not $toolName) { $toolName = [string]$payload.toolName }
if (-not $params) { $params = $payload.parameters }

$serverName = ""
if ($params -and $params.PSObject.Properties["server_name"]) { $serverName = [string]$params.server_name }

$isHybaCall = (
    $toolName.StartsWith("$hybaServer" + "__") -or
    (($toolName -eq "use_mcp_tool" -or $toolName -eq "access_mcp_resource") -and $serverName -eq $hybaServer)
)

$stateDir = Join-Path $env:TEMP "hyba_cline_hook_state"
if (-not (Test-Path $stateDir)) { New-Item -ItemType Directory -Force -Path $stateDir | Out-Null }
# Drop markers from tasks older than 30 days.
Get-ChildItem -Path $stateDir -Filter "*.bound" -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
    Remove-Item -Force -ErrorAction SilentlyContinue
$markerFile = Join-Path $stateDir "$safeTaskId.bound"

if ($isHybaCall) {
    Set-Content -Path $markerFile -Value (Get-Date -Format "o") -Encoding ascii
    Send-Verdict @{ cancel = $false }
}

if ((Test-Path $markerFile) -or ($alwaysAllowed -contains $toolName)) {
    Send-Verdict @{ cancel = $false }
}

Send-Verdict @{
    cancel = $true
    errorMessage = "HYBA-MCP gatekeeper blocked '$toolName': call a tool on the '$hybaServer' MCP server first in this task."
    contextModification = "The '$toolName' call was cancelled by the HYBA-MCP PreToolUse hook because no '$hybaServer' tool has been called in this task yet. Call the '$hybaServer' tool 'hyba_context' with a short query describing the task, then continue. If '$hybaServer' is unavailable, tell the user and stop."
}
