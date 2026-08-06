@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Publish Uriel to GitHub

echo ============================================================
echo  Uriel - safe GitHub publisher
echo ============================================================
echo This will use GitHub's official browser sign-in.
echo It will never ask for your password, token, cookie, or recovery code.
echo.

set "MISSING=0"
where git >nul 2>nul || set "MISSING=1"
where gh >nul 2>nul || set "MISSING=1"
where py >nul 2>nul || where python >nul 2>nul || set "MISSING=1"

if "%MISSING%"=="1" (
  where winget >nul 2>nul
  if errorlevel 1 (
    echo One or more prerequisites are missing, and Windows Package Manager was not found.
    echo Install GitHub Desktop instead, then follow docs\PUBLISH_TO_GITHUB.md.
    pause
    exit /b 1
  )
  echo Missing prerequisites can be installed from official winget packages:
  echo   Git for Windows, GitHub CLI, and Python 3.12.
  choice /C YN /M "Install any missing prerequisites now"
  if errorlevel 2 exit /b 1

  where git >nul 2>nul || winget install --id Git.Git --exact --accept-package-agreements --accept-source-agreements
  if errorlevel 1 goto :install_failed
  where gh >nul 2>nul || winget install --id GitHub.cli --exact --accept-package-agreements --accept-source-agreements
  if errorlevel 1 goto :install_failed
  where py >nul 2>nul || where python >nul 2>nul || winget install --id Python.Python.3.12 --exact --scope user --accept-package-agreements --accept-source-agreements
  if errorlevel 1 goto :install_failed
)

rem Newly installed tools may not be visible until a new terminal; add common paths now.
set "PATH=%ProgramFiles%\Git\cmd;%ProgramFiles%\GitHub CLI;%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;%PATH%"

where git >nul 2>nul || goto :restart_needed
where gh >nul 2>nul || goto :restart_needed
where py >nul 2>nul || where python >nul 2>nul || goto :restart_needed

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\publish_github.ps1" -OpenInBrowser
set "EXITCODE=%ERRORLEVEL%"
echo.
if not "%EXITCODE%"=="0" echo Publishing stopped with exit code %EXITCODE%. Your local files were not deleted.
pause
exit /b %EXITCODE%

:install_failed
echo.
echo A prerequisite installation failed. Nothing in the Uriel folder was deleted.
echo You can use the GitHub Desktop route in docs\PUBLISH_TO_GITHUB.md instead.
pause
exit /b 1

:restart_needed
echo.
echo Installation completed, but Windows has not refreshed PATH yet.
echo Close this window, then double-click PUBLISH_TO_GITHUB.cmd again.
pause
exit /b 1
