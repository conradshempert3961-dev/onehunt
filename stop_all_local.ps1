$ErrorActionPreference = "SilentlyContinue"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogsDir = Join-Path $Root "logs"

foreach ($name in @("bot", "miniapp", "site")) {
    $pidFile = Join-Path $LogsDir "$name.pid"
    if (-not (Test-Path $pidFile)) {
        continue
    }

    $pidValue = Get-Content $pidFile | Select-Object -First 1
    if ($pidValue -match "^\d+$") {
        $process = Get-Process -Id ([int]$pidValue)
        if ($process) {
            Stop-Process -Id $process.Id -Force
            Write-Host "$name stopped: PID $pidValue"
        }
    }
    Remove-Item $pidFile -Force
}

Write-Host "Local ONEHUNT processes stopped."
