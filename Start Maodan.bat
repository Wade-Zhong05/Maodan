@echo off
rem One-click start for Maodan. Double-click again while it runs to bring it back on screen.
rem
rem Nothing needs to be installed first. On the first start this downloads a private copy of pixi
rem into this folder (.pixi\bootstrap) and lets it build Maodan's own Python + Tk
rem (.pixi\envs\default). That needs the internet once; deleting the folder removes everything.
rem
rem Keep this file's line endings CRLF (.gitattributes does): with LF-only lines cmd.exe can fail
rem to find the :labels below. There are no ( ) blocks on purpose, so a folder name with brackets,
rem such as "Maodan (1)", cannot break the script.
setlocal EnableExtensions
cd /d "%~dp0"
rem The subroutines below cannot rely on the batch file's own path, so the folder is kept here.
set "MAODAN_DIR=%~dp0"
set "MAODAN_PET=%MAODAN_DIR%maodan.py"
set "MAODAN_PY=%MAODAN_DIR%.pixi\envs\default\python.exe"
set "MAODAN_PYW=%MAODAN_DIR%.pixi\envs\default\pythonw.exe"
set "MAODAN_BOOT=%MAODAN_DIR%.pixi\bootstrap"
set "MAODAN_OWN_PIXI=%MAODAN_BOOT%\pixi.exe"
rem The pixi release this launcher was tested with. The x64 build also runs on ARM Windows, where it
rem still sets up pixi.toml's win-64 environment.
set "MAODAN_PIXI_VERSION=0.80.0"
set "MAODAN_PIXI_SHA256=7700e558c4abef7d9b12f6caffabef39aec50b86fb76ac86cafa24f7c6c49bf5"

if not exist "%MAODAN_PET%" goto not_extracted
call :runtime_ready && goto start_pet

echo Setting up Maodan for the first time. This needs the internet once and takes a minute or two.
echo.

rem 1. A pixi this computer already has.
set "MAODAN_PIXI="
call :find_installed_pixi
if defined MAODAN_PIXI call :install_with "%MAODAN_PIXI%" && goto start_pet
if defined MAODAN_PIXI echo The pixi on this computer could not set Maodan up. Trying Maodan's own copy instead...

rem 2. Maodan's own copy of pixi, kept in this folder.
if not exist "%MAODAN_OWN_PIXI%" call :download_pixi
if exist "%MAODAN_OWN_PIXI%" call :install_with "%MAODAN_OWN_PIXI%" && goto start_pet

rem 3. Offline, or the setup failed: a Python 3 already on this computer with a working Tk will do.
call :system_python_ready && goto start_system_python
goto failed


:start_pet
start "" "%MAODAN_PYW%" "%MAODAN_PET%"
exit /b 0

:start_system_python
echo Using the Python that is already installed on this computer.
start "" pyw -3 "%MAODAN_PET%"
exit /b 0

:runtime_ready
rem pythonw.exe alone proves little: a quick hidden Tk window shows the whole runtime works.
if not exist "%MAODAN_PY%" exit /b 1
if not exist "%MAODAN_PYW%" exit /b 1
"%MAODAN_PY%" -c "import tkinter as tk; root = tk.Tk(); root.withdraw(); root.destroy()" >nul 2>nul
exit /b %errorlevel%

:system_python_ready
where py >nul 2>nul || exit /b 1
py -3 -c "import tkinter as tk; root = tk.Tk(); root.withdraw(); root.destroy()" >nul 2>nul
exit /b %errorlevel%

:find_installed_pixi
where pixi >nul 2>nul && set "MAODAN_PIXI=pixi"
if not defined MAODAN_PIXI if defined PIXI_HOME if exist "%PIXI_HOME%\bin\pixi.exe" set "MAODAN_PIXI=%PIXI_HOME%\bin\pixi.exe"
if not defined MAODAN_PIXI if exist "%USERPROFILE%\.pixi\bin\pixi.exe" set "MAODAN_PIXI=%USERPROFILE%\.pixi\bin\pixi.exe"
exit /b 0

:install_with
echo.
rem "call" also comes back when the pixi found is a .cmd wrapper rather than pixi.exe.
call "%~1" install --manifest-path "%MAODAN_DIR%pixi.toml"
if errorlevel 1 exit /b 1
call :runtime_ready
exit /b %errorlevel%

:download_pixi
set "MAODAN_PIXI_URL=https://github.com/prefix-dev/pixi/releases/download/v%MAODAN_PIXI_VERSION%/pixi-x86_64-pc-windows-msvc.zip"
set "MAODAN_PIXI_ZIP=%MAODAN_BOOT%\pixi.zip"
if not exist "%MAODAN_BOOT%" mkdir "%MAODAN_BOOT%"
del "%MAODAN_PIXI_ZIP%" >nul 2>nul
echo Downloading pixi %MAODAN_PIXI_VERSION%, which sets up Maodan's Python...
rem curl.exe and tar.exe come with Windows 10 (1803) and 11; PowerShell covers older systems.
curl.exe --fail --location --retry 3 --progress-bar --output "%MAODAN_PIXI_ZIP%" "%MAODAN_PIXI_URL%"
if errorlevel 1 del "%MAODAN_PIXI_ZIP%" >nul 2>nul
if not exist "%MAODAN_PIXI_ZIP%" powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -UseBasicParsing -Uri $env:MAODAN_PIXI_URL -OutFile $env:MAODAN_PIXI_ZIP"
if not exist "%MAODAN_PIXI_ZIP%" echo Could not download pixi from github.com.
if not exist "%MAODAN_PIXI_ZIP%" exit /b 1
call :zip_is_genuine || goto download_damaged
tar.exe -xf "%MAODAN_PIXI_ZIP%" -C "%MAODAN_BOOT%" pixi.exe >nul 2>nul
if not exist "%MAODAN_OWN_PIXI%" powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath $env:MAODAN_PIXI_ZIP -DestinationPath $env:MAODAN_BOOT -Force"
del "%MAODAN_PIXI_ZIP%" >nul 2>nul
if exist "%MAODAN_OWN_PIXI%" exit /b 0
echo Could not unpack pixi.
exit /b 1

:download_damaged
del "%MAODAN_PIXI_ZIP%" >nul 2>nul
echo The pixi download was incomplete or altered, so it was not used. Please try again.
exit /b 1

:zip_is_genuine
rem certutil prints a header line, then the hash (with spaces between bytes on older Windows).
set "MAODAN_HASH="
for /f "skip=1 delims=" %%h in ('certutil -hashfile "%MAODAN_PIXI_ZIP%" SHA256') do if not defined MAODAN_HASH set "MAODAN_HASH=%%h"
if not defined MAODAN_HASH exit /b 1
set "MAODAN_HASH=%MAODAN_HASH: =%"
if /i "%MAODAN_HASH%"=="%MAODAN_PIXI_SHA256%" exit /b 0
exit /b 1

:not_extracted
echo Maodan's files are not next to this launcher.
echo If you opened it from inside a .zip file, extract the whole folder first, then run it again.
echo.
pause
exit /b 1

:failed
echo.
echo Maodan could not be set up on this computer.
echo  - Check the internet connection: github.com and conda.anaconda.org must be reachable.
echo    Then run this file again; it continues where it stopped.
echo  - Or install Python 3 from https://www.python.org, keeping "tcl/tk and IDLE" selected,
echo    then run this file again.
echo.
pause
exit /b 1
