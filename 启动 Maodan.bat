@echo off
rem One-click start for Maodan. Double-click again while it runs to bring it back on screen.
setlocal
cd /d "%~dp0"
set "PET=%~dp0maodan.py"
set "PYW=%~dp0.pixi\envs\default\pythonw.exe"

if exist "%PYW%" goto start_pet

rem First start on this computer: let pixi create Maodan's own Python (needs internet once).
set "PIXI="
where pixi >nul 2>nul && set "PIXI=pixi"
if not defined PIXI if exist "%USERPROFILE%\.pixi\bin\pixi.exe" set "PIXI=%USERPROFILE%\.pixi\bin\pixi.exe"
if not defined PIXI goto system_python
echo Setting up Maodan for the first time. This happens only once...
"%PIXI%" install
if exist "%PYW%" goto start_pet

:system_python
rem No pixi, or it could not finish: any installed Python 3 with Tkinter works too.
py -3 -c "import tkinter" >nul 2>nul || goto no_python
start "" pyw -3 "%PET%"
exit /b 0

:start_pet
start "" "%PYW%" "%PET%"
exit /b 0

:no_python
echo.
echo Maodan needs Python 3 with Tkinter.
echo Install pixi from https://pixi.sh or Python from https://www.python.org, then run this file again.
echo.
pause
exit /b 1
