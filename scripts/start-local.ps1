param(
  [int]$ApiPort = 0,
  [int]$UiPort = 8686,
  [int]$TimeoutSeconds = 45
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$healthScript = Join-Path $scriptDir "local-health.ps1"
$logDir = Join-Path $repoRoot "logs"
$pidFile = Join-Path $logDir "aibi-local.pid"
$outLog = Join-Path $logDir "aibi-local.out.log"
$errLog = Join-Path $logDir "aibi-local.err.log"

if (-not (Test-Path -LiteralPath $logDir)) {
  New-Item -ItemType Directory -Path $logDir | Out-Null
}

function Get-LocalHealth {
  try {
    $output = & $healthScript -ApiPort $ApiPort -UiPort $UiPort -Json 2>$null
    if (-not $output) {
      return $null
    }
    return (($output -join "`n") | ConvertFrom-Json)
  } catch {
    return $null
  }
}

$currentHealth = Get-LocalHealth
if ($currentHealth -and $currentHealth.ok) {
  Write-Host "AIBI-C local services are already running."
  Write-Host ("UI:  {0}" -f $currentHealth.ui.url)
  Write-Host ("API: {0}" -f $currentHealth.api.url)
  exit 0
}

$npmCommand = "npm"
if ($IsWindows -or $env:OS -eq "Windows_NT") {
  $npmCommand = "npm.cmd"
}

$process = Start-Process -FilePath $npmCommand `
  -ArgumentList @("run", "dev") `
  -WorkingDirectory $repoRoot `
  -WindowStyle Hidden `
  -RedirectStandardOutput $outLog `
  -RedirectStandardError $errLog `
  -PassThru

Set-Content -LiteralPath $pidFile -Value $process.Id
Write-Host ("Started AIBI-C local launcher pid {0}." -f $process.Id)

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Milliseconds 1000
  $health = Get-LocalHealth
  if ($health -and $health.ok) {
    Write-Host "AIBI-C local services are ready."
    Write-Host ("UI:  {0}" -f $health.ui.url)
    Write-Host ("API: {0}" -f $health.api.url)
    exit 0
  }
}

Write-Host "AIBI-C local services did not become healthy before timeout."
if (Test-Path -LiteralPath $outLog) {
  Write-Host ""
  Write-Host "stdout tail:"
  Get-Content -LiteralPath $outLog -Tail 60
}
if (Test-Path -LiteralPath $errLog) {
  Write-Host ""
  Write-Host "stderr tail:"
  Get-Content -LiteralPath $errLog -Tail 60
}

exit 1
