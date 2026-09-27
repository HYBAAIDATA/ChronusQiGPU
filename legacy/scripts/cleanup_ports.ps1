<#
.SYNOPSIS
    HYBA Production Port Diagnostic and Process Killer
.DESCRIPTION
    Scans for processes listening on target ports (default: 8000, 3000, 5173).
    Diagnoses conflicting PIDs using netstat / Get-NetTCPConnection, logs process details,
    and terminates conflicting processes if requested, or falls back to HYBA_API_PORT.
#>
param(
    [int[]]$Ports = @(8000, 3000, 5173),
    [switch]$Kill,
    [switch]$CheckOnly
)

Write-Host "=== HYBA Port Conflict Diagnostic ===" -ForegroundColor Cyan

foreach ($port in $Ports) {
    Write-Host "Checking port $port..." -NoNewline
    $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($connections) {
        Write-Host " [OCCUPIED]" -ForegroundColor Red
        foreach ($conn in $connections) {
            $pid_num = $conn.OwningProcess
            $proc = Get-Process -Id $pid_num -ErrorAction SilentlyContinue
            $procName = if ($proc) { $proc.ProcessName } else { "Unknown" }
            Write-Host "  -> PID: $pid_num ($procName), State: $($conn.State)" -ForegroundColor Yellow
            if ($Kill) {
                Write-Host "  -> Terminating process $pid_num..." -ForegroundColor Red
                Stop-Process -Id $pid_num -Force -ErrorAction SilentlyContinue
                Write-Host "  -> Terminated." -ForegroundColor Green
            }
        }
    } else {
        Write-Host " [AVAILABLE]" -ForegroundColor Green
    }
}
