$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    & py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 or newer from python.org first.' }
    & py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtual environment.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check network access and retry.' }
& '.\.venv\Scripts\python.exe' -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed.' }
Write-Host 'Ready. Double-click start.cmd to launch.'

