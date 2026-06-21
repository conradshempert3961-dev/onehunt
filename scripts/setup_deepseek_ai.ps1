param(
    [string]$RepoUrl = "",
    [string]$TargetDir = "",
    [int]$Port = 18632
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $Root
if (-not $TargetDir) {
    $TargetDir = Join-Path $ProjectRoot "tools\deepseek-free-api"
}

$EnvFile = Join-Path $ProjectRoot ".env"
$EnvExample = Join-Path $ProjectRoot ".env.local.example"

function Ensure-DeepseekEnv {
    $lines = @()
    if (Test-Path $EnvFile) {
        $lines = Get-Content $EnvFile
    } elseif (Test-Path $EnvExample) {
        $lines = Get-Content $EnvExample
    }

    $map = @{
        "OPENAI_API_KEY" = "sk-dummy"
        "OPENAI_API_BASE" = "http://127.0.0.1:$Port/v1"
        "OPENAI_MODEL" = "deepseek-chat"
        "AI_REQUEST_TIMEOUT" = "90"
    }

    $seen = @{}
    $updated = @()
    foreach ($line in $lines) {
        if ($line -match '^\s*([A-Za-z0-9_]+)\s*=') {
            $key = $Matches[1]
            if ($map.ContainsKey($key)) {
                $updated += "$key=$($map[$key])"
                $seen[$key] = $true
                continue
            }
        }
        $updated += $line
    }

    foreach ($key in $map.Keys) {
        if (-not $seen.ContainsKey($key)) {
            $updated += "$key=$($map[$key])"
        }
    }

    Set-Content -Path $EnvFile -Value $updated -Encoding UTF8
    Write-Host ".env updated for DeepSeek proxy on port $Port"
}

function Test-Node {
    $node = Get-Command node -ErrorAction SilentlyContinue
    if (-not $node) {
        throw "Node.js 18+ is required. Install from https://nodejs.org"
    }
    $version = & node --version
    Write-Host "Node.js: $version"
}

Ensure-DeepseekEnv
Test-Node

if ($RepoUrl) {
    if (-not (Test-Path $TargetDir)) {
        Write-Host "Cloning $RepoUrl -> $TargetDir"
        git clone $RepoUrl $TargetDir
    }
    Push-Location $TargetDir
    if (Test-Path "package.json") {
        npm install
    }
    Pop-Location
    Write-Host "Repo ready in $TargetDir"
}

Write-Host ""
Write-Host "DeepSeek Free API setup for ONEHUNT"
Write-Host "====================================="
Write-Host "1. In your deepseek-free-api folder:"
Write-Host "   node server.mjs --login"
Write-Host "   (log in at https://chat.deepseek.com in the opened browser window)"
Write-Host ""
Write-Host "2. Start the proxy:"
Write-Host "   node server.mjs"
Write-Host "   (default: http://127.0.0.1:$Port)"
Write-Host ""
Write-Host "3. Start ONEHUNT:"
Write-Host "   powershell -ExecutionPolicy Bypass -File .\run_all_local.ps1"
Write-Host ""
Write-Host "4. Open http://127.0.0.1:8080/app -> AI tab"
Write-Host ""
Write-Host "Test proxy:"
Write-Host "curl http://127.0.0.1:$Port/v1/chat/completions -H `"Content-Type: application/json`" -d '{`"model`":`"deepseek-chat`",`"messages`":[{`"role`":`"user`",`"content`":`"Привет`"}],`"stream`":false}'"
