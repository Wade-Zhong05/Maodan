@echo off
rem One-click start for Maodan. Double-click again while it runs to bring it back on screen.
setlocal
cd /d "%~dp0"
set "PET=%~dp0maodan.py"
set "PY=%~dp0.pixi\envs\default\python.exe"
set "PYW=%~dp0.pixi\envs\default\pythonw.exe"

rem Do not trust a half-created or outdated environment just because pythonw.exe exists.
rem A quick hidden Tk window proves that the complete runtime is ready.
if exist "%PY%" if exist "%PYW%" (
    "%PY%" -c "import tkinter as tk; root=tk.Tk(); root.withdraw(); root.destroy()" >nul 2>nul && goto start_pet
)

rem First start on this computer: install Pixi when needed, then let it create
rem Maodan's isolated Python + Tk environment. Both steps only need internet once.
set "PIXI="
call :find_pixi
if defined PIXI goto setup_maodan

echo Pixi is not installed. Installing it for the current Windows user...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Invoke-RestMethod -UseBasicParsing 'https://pixi.sh/install.ps1' | Invoke-Expression"
if errorlevel 1 goto pixi_install_failed

rem The installer updates future shells' PATH, but this cmd.exe is already open.
rem Resolve the installed executable directly so setup can continue immediately.
call :find_pixi
if not defined PIXI goto pixi_install_failed

:setup_maodan
echo Setting up Maodan for the first time. This happens only once...
"%PIXI%" install
if errorlevel 1 goto environment_failed
if exist "%PY%" if exist "%PYW%" (
    "%PY%" -c "import tkinter as tk; root=tk.Tk(); root.withdraw(); root.destroy()" >nul 2>nul && goto start_pet
)
goto environment_failed

:system_python
rem If online setup failed, an existing Python 3 with a working Tk still works offline.
py -3 -c "import tkinter as tk; root=tk.Tk(); root.withdraw(); root.destroy()" >nul 2>nul || goto no_python
start "" pyw -3 "%PET%"
exit /b 0

:start_pet
start "" "%PYW%" "%PET%"
exit /b 0

:no_python
echo.
echo Maodan could not prepare its runtime automatically.
echo Connect to the internet and run this file again, or install Python 3 with Tkinter.
echo.
pause
exit /b 1

:pixi_install_failed
echo.
echo Pixi could not be installed. Check your internet connection and try again.
echo Trying an existing Python installation instead...
echo.
goto system_python

:environment_failed
echo.
echo Pixi was installed, but Maodan's Python environment could not be prepared.
echo Check your internet connection and try again.
echo Trying an existing Python installation instead...
echo.
goto system_python

:find_pixi
where pixi >nul 2>nul && set "PIXI=pixi"
if defined PIXI exit /b 0
if defined PIXI_HOME if exist "%PIXI_HOME%\bin\pixi.exe" set "PIXI=%PIXI_HOME%\bin\pixi.exe"
if defined PIXI exit /b 0
if exist "%USERPROFILE%\.pixi\bin\pixi.exe" set "PIXI=%USERPROFILE%\.pixi\bin\pixi.exe"
if defined PIXI exit /b 0
if exist "%LOCALAPPDATA%\pixi\bin\pixi.exe" set "PIXI=%LOCALAPPDATA%\pixi\bin\pixi.exe"
exit /b 0
