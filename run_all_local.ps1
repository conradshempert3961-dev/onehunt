param(
    [string]$BotMiniAppUrl = "https://huntexam.online/",
    [switch]$NoBot,
    [switch]$NoMiniApp,
    [switch]$NoSite
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$LogsDir = Join-Path $Root "logs"
$DataDir = Join-Path $Root "data"

function Test-PythonExecutable {
    param([string]$Path)

    if (-not $Path -or -not (Test-Path $Path)) {
        return $false
    }

    try {
        & $Path --version *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Resolve-SystemPython {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd -and (Test-PythonExecutable -Path $pythonCmd.Source)) {
        return $pythonCmd.Source
    }

    $candidates = @(
        (Join-Path $env:LocalAppData "Programs\Python\Python312\python.exe"),
        (Join-Path $env:LocalAppData "Programs\Python\Python311\python.exe"),
        (Join-Path $env:LocalAppData "Programs\Python\Python310\python.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-PythonExecutable -Path $candidate) {
            return $candidate
        }
    }

    return $null
}

function Ensure-OnehuntVenv {
    $venvPath = Join-Path $Root ".venv"
    $venvPython = Join-Path $venvPath "Scripts\python.exe"

    if (Test-PythonExecutable -Path $venvPython) {
        return $venvPython
    }

    $systemPython = Resolve-SystemPython
    if (-not $systemPython) {
        $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
        if ($pyLauncher) {
            & py -3.11 -m venv --clear $venvPath
        } else {
            throw "Python 3.11 was not found. Install Python or add it to PATH."
        }
    } else {
        & $systemPython -m venv --clear $venvPath
    }

    if (-not (Test-PythonExecutable -Path $venvPython)) {
        throw "Failed to prepare .venv for ONEHUNT."
    }

    return $venvPython
}

function Set-OnehuntEnv {
    param([hashtable]$Extra = @{})

    $dbPath = (Join-Path $DataDir "onehunt_local.db").Replace("\", "/")
    $env:DATABASE_URL = "sqlite+aiosqlite:///$dbPath"
    $env:USE_REDIS_FSM = "false"
    $env:QUESTIONS_FILE = Join-Path $Root "questions.json"
    $env:EXPORT_DIR = $DataDir
    $env:ANIMAL_CARDS_FILE = Join-Path $DataDir "animal_cards.json"
    $env:QUOTES_FILE = Join-Path $DataDir "quotes.json"
    $env:FREE_MODE = "true"
    $env:BOT_SHELL_MODE = "true"
    $env:ANSWER_BUTTONS_LAYOUT = "single_row"
    $env:TELEGRAM_PROXY = ""
    $env:MINIAPP_BROWSER_DEMO = "true"
    $env:MINIAPP_BROWSER_DEMO_HOSTS = "localhost,127.0.0.1,::1"
    $env:MINIAPP_DEV_USER_ID = "6467055041"

    foreach ($key in $Extra.Keys) {
        Set-Item -Path "env:$key" -Value $Extra[$key]
    }
}

function Stop-FromPidFile {
    param([string]$Name)

    $pidFile = Join-Path $LogsDir "$Name.pid"
    if (-not (Test-Path $pidFile)) {
        return
    }

    $oldPid = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($oldPid -match "^\d+$") {
        $process = Get-Process -Id ([int]$oldPid) -ErrorAction SilentlyContinue
        if ($process) {
            Stop-Process -Id $process.Id -Force
        }
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

function Quote-PS {
    param([string]$Value)
    return "'" + $Value.Replace("'", "''") + "'"
}

function Start-OnehuntProcess {
    param(
        [string]$Name,
        [string[]]$Arguments,
        [hashtable]$ExtraEnv = @{}
    )

    Stop-FromPidFile -Name $Name

    Set-OnehuntEnv -Extra $ExtraEnv

    $stdoutPath = Join-Path $LogsDir "$Name.stdout.log"
    $stderrPath = Join-Path $LogsDir "$Name.stderr.log"
    Remove-Item $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue

    $process = Start-Process `
        -FilePath $Python `
        -ArgumentList $Arguments `
        -WorkingDirectory $Root `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -WindowStyle Minimized `
        -PassThru

    Set-Content -Path (Join-Path $LogsDir "$Name.pid") -Value $process.Id
    Write-Host "$Name started: PID $($process.Id), logs $stdoutPath / $stderrPath"
}

Set-Location $Root
New-Item -ItemType Directory -Force -Path $LogsDir, $DataDir | Out-Null

$Python = Ensure-OnehuntVenv

if (-not (Test-Path (Join-Path $Root ".env"))) {
    Copy-Item (Join-Path $Root ".env.local.example") (Join-Path $Root ".env")
    Write-Host ".env was created from .env.local.example. Fill BOT_TOKEN and run this script again."
    exit 1
}

Set-OnehuntEnv

& $Python -m pip install --disable-pip-version-check -r (Join-Path $Root "requirements.txt")
& $Python scripts\load_questions.py

if (-not $NoSite) {
    Start-OnehuntProcess -Name "site" -Arguments @("-m", "http.server", "8088", "--bind", "127.0.0.1", "--directory", "landing")
}

if (-not $NoMiniApp) {
    Start-OnehuntProcess -Name "miniapp" -Arguments @("miniapp_server.py") -ExtraEnv @{
        MINIAPP_PORT = "8080"
        MINIAPP_URL = "http://127.0.0.1:8080/"
    }
}

if (-not $NoBot) {
    Start-OnehuntProcess -Name "bot" -Arguments @("bot.py") -ExtraEnv @{
        MINIAPP_URL = $BotMiniAppUrl
    }
}

Write-Host ""
Write-Host "Local ONEHUNT is running."
Write-Host "Site:    http://127.0.0.1:8088/"
Write-Host "MiniApp: http://127.0.0.1:8080/"
Write-Host "Bot:     local long polling process"
Write-Host ""
Write-Host "Stop everything: powershell -ExecutionPolicy Bypass -File .\stop_all_local.ps1"
