param(
  [int]$ApiPort = 0,
  [int]$UiPort = 8686,
  [switch]$Json
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path

function Read-DotEnvValue {
  param(
    [string]$Path,
    [string]$Name
  )

  if (-not (Test-Path -LiteralPath $Path)) {
    return $null
  }

  foreach ($line in Get-Content -LiteralPath $Path) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) {
      continue
    }

    $separator = $trimmed.IndexOf("=")
    if ($separator -le 0) {
      continue
    }

    $key = $trimmed.Substring(0, $separator).Trim()
    if ($key -ne $Name) {
      continue
    }

    $value = $trimmed.Substring($separator + 1).Trim()
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
      $value = $value.Substring(1, $value.Length - 2)
    }
    return $value
  }

  return $null
}

if ($ApiPort -le 0) {
  if ($env:AIBI_API_PORT) {
    $ApiPort = [int]$env:AIBI_API_PORT
  } else {
    $envPort = Read-DotEnvValue -Path (Join-Path $repoRoot ".env") -Name "AIBI_API_PORT"
    if ($envPort) {
      $ApiPort = [int]$envPort
    } else {
      $ApiPort = 8787
    }
  }
}

$apiUrl = "http://127.0.0.1:$ApiPort/api/health"
$uiUrl = "http://127.0.0.1:$UiPort/"

$api = [pscustomobject]@{
  ok = $false
  url = $apiUrl
  statusCode = $null
  service = $null
  error = $null
}

$ui = [pscustomobject]@{
  ok = $false
  url = $uiUrl
  statusCode = $null
  title = $null
  error = $null
}

try {
  $apiResponse = Invoke-WebRequest -Uri $apiUrl -TimeoutSec 3 -UseBasicParsing
  $api.statusCode = [int]$apiResponse.StatusCode
  $payload = $apiResponse.Content | ConvertFrom-Json
  $api.service = $payload.service
  $api.ok = ($payload.ok -eq $true -and $payload.service -eq "aibi-hybrid-api")
} catch {
  $api.error = $_.Exception.Message
}

try {
  $uiResponse = Invoke-WebRequest -Uri $uiUrl -TimeoutSec 3 -UseBasicParsing
  $ui.statusCode = [int]$uiResponse.StatusCode
  $titleMatch = [regex]::Match($uiResponse.Content, "<title>(.*?)</title>", "IgnoreCase")
  if ($titleMatch.Success) {
    $ui.title = $titleMatch.Groups[1].Value
  }
  $ui.ok = ($uiResponse.StatusCode -ge 200 -and $uiResponse.StatusCode -lt 400 -and $uiResponse.Content.Contains("<title>AIBI-C</title>"))
} catch {
  $ui.error = $_.Exception.Message
}

$result = [pscustomobject]@{
  ok = ($api.ok -and $ui.ok)
  repoRoot = $repoRoot
  api = $api
  ui = $ui
}

if ($Json) {
  $result | ConvertTo-Json -Depth 6
} else {
  if ($result.ok) {
    Write-Host "AIBI-C local services are healthy."
  } else {
    Write-Host "AIBI-C local services are not ready."
  }
  Write-Host ("API {0} {1}" -f $api.url, $(if ($api.ok) { "ok" } else { "failed" }))
  if ($api.error) {
    Write-Host ("  {0}" -f $api.error)
  }
  Write-Host ("UI  {0} {1}" -f $ui.url, $(if ($ui.ok) { "ok" } else { "failed" }))
  if ($ui.error) {
    Write-Host ("  {0}" -f $ui.error)
  }
}

if ($result.ok) {
  exit 0
}

exit 1
