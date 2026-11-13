param([switch]$Foreground)
$ErrorActionPreference = 'Stop'
$sourcePath = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $sourcePath 'examples\watch-cloud.json'
$runtimePath = Join-Path $sourcePath '.watch\cloud'
New-Item -ItemType Directory -Force -Path $runtimePath | Out-Null
if (Test-Path -LiteralPath (Join-Path $runtimePath 'STOP')) {
    throw 'Remove .watch/cloud/STOP before starting.'
}
$pythonPath = (Get-Command python -ErrorAction Stop).Source
if ($Foreground) {
    Push-Location $sourcePath
    try { & $pythonPath -m codelaboon.service $configPath }
    finally { Pop-Location }
} else {
    $serviceProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m', 'codelaboon.service', ('"' + $configPath + '"')) -WorkingDirectory $sourcePath -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimePath 'service.stdout.log') -RedirectStandardError (Join-Path $runtimePath 'service.stderr.log')
    Write-Output "Started cloud-watch service PID $($serviceProcess.Id). Logs: $runtimePath"
}
