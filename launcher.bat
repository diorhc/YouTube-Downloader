@echo off
chcp 65001 >nul
setlocal ENABLEDELAYEDEXPANSION

REM === CONFIGURABLE VARIABLES ===
set "PYDIR=python_embedded"
set "PYEXE=%PYDIR%\python.exe"
set "PYPTH=%PYDIR%\python313._pth"
set "PIP=%PYDIR%\Scripts\pip.exe"
set "FFMPEG=%PYDIR%\bin\ffmpeg.exe"
set "BORDER=╔════════════════════════════════════════════════════════════╗"
set "END=╚════════════════════════════════════════════════════════════╝"
title YouTube Downloader

REM === CHECK POWERSHELL ===
where powershell >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PowerShell is required but not found. Please install PowerShell.
    pause
    exit /b 1
)

:mainmenu
cls
call :printAnimatedHeader
call :printMenu
echo ║  Select an option (1-5) and press ENTER.
:choiceLoop
choice /C 12345 /N /M "  ║  Enter choice (1-5): "
set "choice=%errorlevel%"
if "%choice%"=="1" goto web
if "%choice%"=="2" goto cli
if "%choice%"=="3" goto setup
if "%choice%"=="4" goto update
if "%choice%"=="5" goto exit
call :printError "Invalid choice! Please enter a number from 1 to 5."
goto choiceLoop

:web
cls
call :printHeader
call :printSection "Launching Web Interface..."
start "" http://localhost:5005
call :runPython web_app.py
pause
goto mainmenu

:cli
cls
call :printHeader
call :printSection "Command Line Usage"
echo ║
echo ║  python youtube_downloader.py "VIDEO_URL" [options]
echo ║
echo ║  Options:
echo ║    -q, --quality     Video quality (best, 4k, 1080p, 720p, 480p, 360p)
echo ║    -m, --mode        Download mode (auto, ultra, standard)
echo ║    -o, --output      Output filename
echo ║    --audio-only      Download audio only
echo ║
echo ║  Examples:
echo ║    python youtube_downloader.py "https://youtube.com/watch?v=dQw4w9WgXcQ"
echo ║    python youtube_downloader.py "URL" -q 1080p -m ultra
echo ║    python youtube_downloader.py "URL" --audio-only
echo ║
pause
goto mainmenu

:setup
cls
call :printAnimatedHeader
call :printSection "Installing dependencies..."

REM === Download embedded Python if not present ===
if not exist "%PYEXE%" (
    call :printInfo "Downloading embedded Python..."
    call :startSpinner 200
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.13.5/python-3.13.5-embed-amd64.zip' -OutFile 'python_embedded.zip'" 2>&1
    powershell -NoProfile -Command "New-Item -Path 'tmp_ps_stop' -ItemType File -Force > $null; Start-Sleep -Milliseconds 120; Stop-Job -Name spinnerJob -Force; Remove-Item -Force 'tmp_ps_stop' > $null" >nul
    if exist "python_embedded.zip" (
        call :printInfo "Extracting embedded Python..."
    call :startSpinner 160
        powershell -Command "Expand-Archive -Path 'python_embedded.zip' -DestinationPath '%PYDIR%' -Force" 2>&1
        powershell -NoProfile -Command "New-Item -Path 'tmp_ps_stop' -ItemType File -Force > $null; Start-Sleep -Milliseconds 120; Stop-Job -Name spinnerJob -Force; Remove-Item -Force 'tmp_ps_stop' > $null" >nul
        del /f /q python_embedded.zip
        call :printSuccess "Embedded Python installed."
    ) else (
        call :printError "Failed to download embedded Python."
    )
)

REM === Configure embedded Python for pip usage ===
if exist "%PYEXE%" (
    if exist "%PYPTH%" (
        call :printInfo "Configuring Python path..."
        (
            echo python313.zip
            echo .
            echo Scripts
            echo Lib\site-packages
            echo.
            echo import site
        ) > "%PYPTH%"
    )
    REM === Install pip if not present ===
    if not exist "%PIP%" (
        call :printInfo "Bootstrapping pip for embedded Python..."
        if not exist "get-pip.py" (
            call :printInfo "Downloading get-pip.py..."
            call :startSpinner 180
            powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'get-pip.py'" 2>&1
            call :stopSpinner
        )
        if exist "get-pip.py" (
            "%PYEXE%" get-pip.py --no-warn-script-location
            del /f /q get-pip.py
        ) else (
            call :printError "Failed to download get-pip.py."
        )
    ) else (
        call :printSuccess "pip already present."
    )
)

REM === Download ffmpeg if not present ===
    if not exist "%FFMPEG%" (
    call :printInfo "Downloading ffmpeg..."
    call :startSpinner 160
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip' -OutFile 'ffmpeg.zip'" 2>&1
    call :stopSpinner
    if exist "ffmpeg.zip" (
        call :printInfo "Extracting ffmpeg..."
    call :startSpinner 160
    powershell -Command "Expand-Archive -Path 'ffmpeg.zip' -DestinationPath 'ffmpeg_temp' -Force" 2>&1
    call :stopSpinner
        for /d %%D in ("ffmpeg_temp\ffmpeg-*") do (
            xcopy /y /e /i "%%D\bin" "%PYDIR%\bin"
        )
        rmdir /s /q ffmpeg_temp
        del /f /q ffmpeg.zip
        if exist "%FFMPEG%" (
            call :printSuccess "ffmpeg installed."
        ) else (
            call :printError "Failed to extract ffmpeg."
        )
    ) else (
        call :printError "Failed to download ffmpeg."
    )
) else (
    call :printSuccess "ffmpeg already present."
)

REM === Install Python requirements ===
call :printInfo "Installing Python requirements..."
call :startSpinner 140
call :runPython -m pip install -r requirements.txt
call :stopSpinner
goto mainmenu

:update
cls
call :printHeader
call :printSection "Checking for dependency updates..."
set "OUTFILE=outdated.txt"
if exist "%OUTFILE%" del /f /q "%OUTFILE%" 2>nul

REM Determine which python/pip to use (embedded first, then system)
if exist "%PYEXE%" (
    set "PYCMD=%PYEXE% -m pip"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        call :printError "Python not found! Please run Setup first."
        pause
        goto mainmenu
    ) else (
        set "PYCMD=python -m pip"
    )
)

call :printInfo "Checking for outdated packages..."
%PYCMD% list --outdated --format=columns > "%OUTFILE%" 2>&1

if not exist "%OUTFILE%" (
    call :printError "Failed to check for outdated packages."
    pause
    goto mainmenu
)

set "HAS_OUTDATED=0"
for /f "usebackq delims=" %%L in ("%OUTFILE%") do (
    set "HAS_OUTDATED=1"
    goto _after_check
)
:_after_check

if "%HAS_OUTDATED%"=="0" (
    call :printSuccess "All dependencies are up to date."
    del /f /q "%OUTFILE%" 2>nul
    pause
    goto mainmenu
)

call :printInfo "Updating outdated dependencies..."
set "FAIL=0"
REM Parse the columns output, skip header line(s), and extract first token as package name
set "FAIL=0"
for /f "usebackq skip=2 tokens=1" %%A in ("%OUTFILE%") do (
    if not "%%A"=="" (
        call :printInfo "Upgrading %%A..."
        %PYCMD% install --upgrade "%%A"
        if errorlevel 1 (
            set "FAIL=1"
        )
    )
)

if "%FAIL%"=="1" (
    call :printError "One or more packages failed to update. Check the output above."
 ) else (
    call :printSuccess "All outdated dependencies were updated successfully."
 )

del /f /q "%OUTFILE%" 2>nul
pause
goto mainmenu

:exit
cls
call :printHeader
echo ║  👋 Goodbye! Thank you for using YouTube Downloader.        ║
echo %END%
exit /b 0

REM ──────────────────────────────────────────────────────────────
REM  BEAUTIFUL PRINT FUNCTIONS
REM ──────────────────────────────────────────────────────────────
:printHeader
echo.
echo %BORDER%
echo ║              YOUTUBE DOWNLOADER LAUNCHER                   ║
echo ║        Cross-Platform Edition   (Platform: Windows)        ║
echo ║  For other platforms: ./launcher.sh or python launcher.py  ║
echo %END%
echo.
goto :eof

:printAnimatedHeader
echo.
for /f "delims=" %%L in ('powershell -NoProfile -Command "[Console]::ForegroundColor='Cyan'; Write-Host '╔' + '═' * 60 + '╗' -NoNewline; Start-Sleep -Milliseconds 60; Write-Host ''; [Console]::ForegroundColor='White'"') do (
    rem no-op to consume output
)
echo %BORDER%
echo ║              YOUTUBE DOWNLOADER LAUNCHER                   ║
echo ║        Cross-Platform Edition   (Platform: Windows)        ║
echo ║  For other platforms: ./launcher.sh or python launcher.py  ║
echo %END%
echo.
goto :eof

:printMenu
echo ║  1. Start Web Interface                                    ║
echo ║  2. Command Line Help                                      ║
echo ║  3. Setup Dependencies                                     ║
echo ║  4. Update yt-dlp                                          ║
echo ║  5. Exit                                                   ║
echo %END%
echo.
goto :eof

:printSection
setlocal
set "msg=%~1"
echo ║  %msg%
echo ╠════════════════════════════════════════════════════════════╣
endlocal
goto :eof

:printSuccess
setlocal
set "msg=%~1"
echo   [SUCCESS] %msg%
endlocal
goto :eof

:printError
setlocal
set "msg=%~1"
echo   [ERROR] %msg%
endlocal
goto :eof

:printInfo
setlocal
set "msg=%~1"
echo   [INFO] %msg%
endlocal
goto :eof

:startSpinner
rem Start a background PowerShell job that prints dots at given interval (ms)
set "_ms=%~1"
powershell -NoProfile -Command "Start-Job -Name spinnerJob -ScriptBlock {param($ms) while(-not (Test-Path 'tmp_ps_stop')){ Write-Host -NoNewline '.'; Start-Sleep -Milliseconds $ms }} -ArgumentList %_ms%" >nul
goto :eof

:stopSpinner
rem Stop the spinner job and remove the sentinel file
powershell -NoProfile -Command "New-Item -Path 'tmp_ps_stop' -ItemType File -Force > $null; Start-Sleep -Milliseconds 120; Stop-Job -Name spinnerJob -Force -ErrorAction SilentlyContinue; Remove-Item -Force 'tmp_ps_stop' -ErrorAction SilentlyContinue" >nul
goto :eof

REM ──────────────────────────────────────────────────────────────
REM  PYTHON RUNNER FUNCTION
REM ──────────────────────────────────────────────────────────────
:runPython
setlocal
if exist "%PYEXE%" (
    call :printSuccess "Using embedded Python"
    "%PYEXE%" %*
) else (
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        call :printSuccess "Using system Python"
        python %*
    ) else (
        call :printError "Python not found! Please install Python or run setup."
        call :printInfo "Download from: https://python.org"
        pause
        endlocal
        exit /b 1
    )
)
endlocal
goto :eof