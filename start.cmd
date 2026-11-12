@echo off
setlocal
pushd "%~dp0"
set "INVOICE_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%INVOICE_PYTHON%" (
  echo Python environment not found. Please run setup.ps1 first. See README.md.
  pause
  popd
  exit /b 1
)
"%INVOICE_PYTHON%" -X utf8 run.py %*
set "INVOICE_EXIT=%ERRORLEVEL%"
if not "%INVOICE_EXIT%"=="0" pause
popd
exit /b %INVOICE_EXIT%

