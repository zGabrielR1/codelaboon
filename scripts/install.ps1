# Install codelaboon for the current user and add it to PATH.
#
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
#   powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/zGabrielR1/codelaboon/main/scripts/install.ps1 | iex"
#
# The Python installer runs `pip install --user`, then adds
# %APPDATA%\Python\PythonX.Y\Scripts to the user Path registry value.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

Push-Location $Root
try {
    & $Python -m codelaboon install @args
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
