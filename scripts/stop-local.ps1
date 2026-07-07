param(
  [int]$ApiPort = 8787,
  [int]$UiPort = 8686
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$logDir = Join-Path $repoRoot "logs"
$pidFile = Join-Path $logDir "aibi-local.pid"

function Normalize-TextPath {
  param([string]$Value)
  if (-not $Value) {
    return ""
  }
  return $Value.ToLowerInvariant().Replace("/", "\")
}

function Get-ListenerPids {
  param([int]$Port)
  try {
    return @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
  } catch {
    return @()
  }
}

function Get-ProcessCommandLine {
  param([int]$ProcessId)
  try {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId"
    if ($process) {
      return [string]$process.CommandLine
    }
  } catch {
    return ""
  }
  return ""
}

$stopped = New-Object System.Collections.Generic.List[string]
$skipped = New-Object System.Collections.Generic.List[string]
$repoMarker = Normalize-TextPath -Value $repoRoot

if (Test-Path -LiteralPath $pidFile) {
  $launcherPidText = (Get-Content -LiteralPath $pidFile -Raw).Trim()
  $launcherPid = 0
  if ([int]::TryParse($launcherPidText, [ref]$launcherPid)) {
    $launcher = Get-Process -Id $launcherPid -ErrorAction SilentlyContinue
    if ($launcher) {
      Stop-Process -Id $launcherPid -Force
      $stopped.Add("launcher pid $launcherPid")
    }
  }
  Remove-Item -LiteralPath $pidFile -Force
}

foreach ($port in @($ApiPort, $UiPort)) {
  foreach ($listenerProcessId in Get-ListenerPids -Port $port) {
    $commandLine = Get-ProcessCommandLine -ProcessId $listenerProcessId
    $normalizedCommand = Normalize-TextPath -Value $commandLine
    if ($normalizedCommand.Contains($repoMarker)) {
      Stop-Process -Id $listenerProcessId -Force
      $stopped.Add("port $port pid $listenerProcessId")
    } else {
      $skipped.Add("port $port pid $listenerProcessId outside this repo")
    }
  }
}

if ($stopped.Count -eq 0) {
  Write-Host "No AIBI-C local services from this repo were running."
} else {
  Write-Host "Stopped AIBI-C local services:"
  foreach ($entry in $stopped) {
    Write-Host ("  {0}" -f $entry)
  }
}

if ($skipped.Count -gt 0) {
  Write-Host "Skipped listeners that did not belong to this repo:"
  foreach ($entry in $skipped) {
    Write-Host ("  {0}" -f $entry)
  }
}
