# Install codelaboon for the current user and add it to PATH.
#
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
#   powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/zGabrielR1/codelaboon/main/scripts/install.ps1 | iex"
#
# The Python installer runs `pip install --user`, then adds
# %APPDATA%\Python\PythonX.Y\Scripts to the user Path registry value.
$ErrorActionPreference = "Stop"

$Root = if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { "" }
$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }
if (-not $Root -or -not (Test-Path (Join-Path $Root "pyproject.toml"))) {
    $Root = if ($env:CODELABOON_SOURCE_DIR) { $env:CODELABOON_SOURCE_DIR } else { Join-Path $env:LOCALAPPDATA "codelaboon\source" }
    if (-not (Test-Path (Join-Path $Root ".git"))) {
        & git clone https://github.com/zGabrielR1/codelaboon.git $Root
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}

Push-Location $Root
try {
    & $Python -m codelaboon install @args
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
