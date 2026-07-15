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

function Stop-OwnedDescendants {
  param(
    [int]$ParentProcessId,
    [string]$RepositoryMarker,
    [System.Collections.Generic.List[string]]$StoppedEntries,
    [System.Collections.Generic.List[string]]$SkippedEntries
  )
  $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $ParentProcessId" -ErrorAction SilentlyContinue)
  foreach ($child in $children) {
    Stop-OwnedDescendants -ParentProcessId ([int]$child.ProcessId) -RepositoryMarker $RepositoryMarker -StoppedEntries $StoppedEntries -SkippedEntries $SkippedEntries
    $normalizedCommand = Normalize-TextPath -Value ([string]$child.CommandLine)
    if ($normalizedCommand.Contains($RepositoryMarker)) {
      Stop-Process -Id ([int]$child.ProcessId) -Force -ErrorAction SilentlyContinue
      $StoppedEntries.Add("owned child pid $($child.ProcessId)")
    } else {
      $SkippedEntries.Add("child pid $($child.ProcessId) outside this repo")
    }
  }
}

$stopped = New-Object System.Collections.Generic.List[string]
$skipped = New-Object System.Collections.Generic.List[string]
$repoMarker = Normalize-TextPath -Value $repoRoot

if (Test-Path -LiteralPath $pidFile) {
  $launcherRecordText = (Get-Content -LiteralPath $pidFile -Raw).Trim()
  $launcherPid = 0
  $launcherOwned = $false
  if ([int]::TryParse($launcherRecordText, [ref]$launcherPid)) {
    $legacyLauncherCommand = Normalize-TextPath -Value (Get-ProcessCommandLine -ProcessId $launcherPid)
    $launcherOwned = $legacyLauncherCommand.Contains($repoMarker)
  } else {
    try {
      $launcherRecord = $launcherRecordText | ConvertFrom-Json
      if (
        $launcherRecord.schema -eq "aibi-local-launcher/v1" -and
        [int]::TryParse(([string]$launcherRecord.processId), [ref]$launcherPid) -and
        (Normalize-TextPath -Value ([string]$launcherRecord.repositoryRoot)) -eq $repoMarker -and
        [string]$launcherRecord.ownerToken
      ) {
        $launcherCommand = Normalize-TextPath -Value (Get-ProcessCommandLine -ProcessId $launcherPid)
        $ownerMarker = ("--aibi-local-owner={0}" -f ([string]$launcherRecord.ownerToken)).ToLowerInvariant()
        $launcherOwned = $launcherCommand.Contains($ownerMarker)
      }
    } catch {
      $launcherPid = 0
    }
  }
  if ($launcherPid -gt 0) {
    $launcher = Get-Process -Id $launcherPid -ErrorAction SilentlyContinue
    if ($launcher -and $launcherOwned) {
      Stop-Process -Id $launcherPid -Force
      $stopped.Add("launcher pid $launcherPid")
    } elseif ($launcher) {
      $skipped.Add("launcher pid $launcherPid failed ownership verification")
    }
  }
  Remove-Item -LiteralPath $pidFile -Force
}

foreach ($port in @($ApiPort, $UiPort)) {
  foreach ($listenerProcessId in Get-ListenerPids -Port $port) {
    $commandLine = Get-ProcessCommandLine -ProcessId $listenerProcessId
    $normalizedCommand = Normalize-TextPath -Value $commandLine
    if ($normalizedCommand.Contains($repoMarker)) {
      Stop-OwnedDescendants -ParentProcessId $listenerProcessId -RepositoryMarker $repoMarker -StoppedEntries $stopped -SkippedEntries $skipped
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
  Write-Host "Skipped processes that did not belong to this repo:"
  foreach ($entry in $skipped) {
    Write-Host ("  {0}" -f $entry)
  }
}
