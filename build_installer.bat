@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ==============================
REM ArcaneAudio: build EXE + installer
REM ==============================

REM ---- config ----
set "SPEC_FILE=arcaneaudio.spec"
set "APP_NAME=ArcaneAudio"
set "EXE_NAME=ArcaneAudio.exe"
REM ---- version is derived from arcaneaudio\__init__.py after pushd ----

REM ---- ffmpeg staging ----
set "FFMPEG_DIR=third_party\ffmpeg"
set "FFMPEG_EXE=%FFMPEG_DIR%\ffmpeg.exe"
set "FFMPEG_URL=https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

set "DIST_DIR=dist\%APP_NAME%"
set "INSTALLER_DIR=installer"

REM Source .iss in repo root:
set "ISS_SRC=arcaneaudio.iss"
REM Copied .iss compiled from installer\ (this makes SourcePath == installer\)
set "ISS_FILE=%INSTALLER_DIR%\arcaneaudio.iss"
REM ----------------

REM Run from this script's folder (repo root)
pushd "%~dp0"

REM ---- Derive version from arcaneaudio\__init__.py (single source of truth) ----
set "VERSION="
for /f "tokens=2 delims== " %%v in ('findstr /b /c:"__version__" "arcaneaudio\__init__.py"') do set "VERSION=%%~v"
if not defined VERSION (
  echo [!] Could not read __version__ from arcaneaudio\__init__.py.
  goto :end
)
echo [*] Version from __init__.py: %VERSION%

REM Prefer venv python
set "PY_EXE=.venv\Scripts\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=python"

REM ===== Ensure ffmpeg is present (download once, not in git) =====
set "FFMPEG_FORCE=0"  REM set to 1 to redownload even if ffmpeg.exe exists

echo [*] Ensuring ffmpeg exists...
echo [i] Target: %FFMPEG_EXE%
echo [i] Source: %FFMPEG_URL%

if "%FFMPEG_FORCE%"=="1" (
  if exist "%FFMPEG_EXE%" (
    echo [i] Force enabled: deleting existing ffmpeg.exe
    del /q "%FFMPEG_EXE%" >NUL 2>&1
  )
)

if not exist "%FFMPEG_EXE%" (
  echo [i] ffmpeg not found. Downloading + extracting...
  if not exist "%FFMPEG_DIR%" mkdir "%FFMPEG_DIR%" 2>nul

  REM Clean any leftovers from a prior run
  if exist "ffmpeg.zip" del /q "ffmpeg.zip" >NUL 2>&1
  if exist "ffmpeg_tmp" rmdir /s /q "ffmpeg_tmp" >NUL 2>&1

  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ErrorActionPreference='Stop';" ^
    "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" ^
    "$zip='ffmpeg.zip';" ^
    "Write-Host '[ps] Downloading...';" ^
    "Invoke-WebRequest -Uri '%FFMPEG_URL%' -OutFile $zip;" ^
    "Write-Host '[ps] Extracting...';" ^
    "Expand-Archive -Force $zip -DestinationPath 'ffmpeg_tmp';" ^
    "$exe = Get-ChildItem -Recurse -Filter ffmpeg.exe 'ffmpeg_tmp' | Select-Object -First 1;" ^
    "if (-not $exe) { throw 'ffmpeg.exe not found inside zip'; }" ^
    "Write-Host ('[ps] Found: ' + $exe.FullName);" ^
    "Copy-Item $exe.FullName '%FFMPEG_EXE%' -Force;" ^
    "Write-Host '[ps] Cleaning...';" ^
    "Remove-Item $zip -Force;" ^
    "Remove-Item 'ffmpeg_tmp' -Recurse -Force;"

  if errorlevel 1 (
    echo [!] Failed to download/extract ffmpeg.
    goto :end
  )

  echo [✓] ffmpeg staged: %FFMPEG_EXE%
) else (
  echo [✓] ffmpeg already present: %FFMPEG_EXE%
)
REM ================================================================

echo [*] Stopping previous instances...
taskkill /IM "%EXE_NAME%" /F >NUL 2>&1
powershell -NoProfile -Command ^
 "Get-CimInstance Win32_Process | Where-Object { ($_.Name -in 'python.exe','pythonw.exe') -and ($_.CommandLine -match 'arcaneaudio') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >NUL 2>&1
ping 127.0.0.1 -n 2 >NUL

echo [*] Cleaning old build artifacts...
if exist "%DIST_DIR%" rmdir /S /Q "%DIST_DIR%"
if exist "build\arcaneaudio" rmdir /S /Q "build\arcaneaudio"

echo [*] Building EXE with PyInstaller...
"%PY_EXE%" -m PyInstaller --noconfirm --clean "%SPEC_FILE%"
if errorlevel 1 goto :py_fail

if not exist "%DIST_DIR%\%EXE_NAME%" (
  echo [!] Built executable not found: "%DIST_DIR%\%EXE_NAME%"
  goto :end
)

echo [*] Preparing installer directory...
if not exist "%INSTALLER_DIR%" mkdir "%INSTALLER_DIR%" 2>nul

echo [*] Copying ISS to installer folder...
if not exist "%ISS_SRC%" (
  echo [!] Cannot find %ISS_SRC%
  goto :end
)
copy /Y "%ISS_SRC%" "%ISS_FILE%" >nul
echo   [+] Copied %ISS_SRC% to %ISS_FILE%

echo [*] Locating Inno Setup compiler...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC for %%I in (ISCC.exe) do set "ISCC=%%~$PATH:I"
if not defined ISCC goto :no_iscc

echo [*] Compiling installer...
"%ISCC%" /DMyAppVersion=%VERSION% "%ISS_FILE%"
if errorlevel 1 goto :iscc_fail

echo.
echo [✓] Installer built.
if exist "%INSTALLER_DIR%\output" (
  echo [i] Output folder: %INSTALLER_DIR%\output
  dir /b "%INSTALLER_DIR%\output"
) else (
  echo [i] Your .iss OutputDir is not '%INSTALLER_DIR%\output'. Check OutputDir in the .iss file.
)

goto :end

:py_fail
echo [!] PyInstaller failed.
goto :end

:no_iscc
echo [!] Inno Setup compiler (ISCC.exe) not found.
echo     Install it (winget install JRSoftware.InnoSetup) or adjust ISCC path in this script.
goto :end

:iscc_fail
echo [!] Inno compilation failed. Check the .iss paths (Source:, OutputDir:, LicenseFile:, SetupIconFile:).
goto :end

:end
popd
endlocal