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
call :printHeader
call :printMenu
echo ║  Select an option (1-4) and press ENTER.
:choiceLoop
choice /C 1234 /N /M "  ║  Enter choice (1-4): "
set "choice=%errorlevel%"
if "%choice%"=="1" goto web
if "%choice%"=="2" goto cli
if "%choice%"=="3" goto setup
if "%choice%"=="4" goto exit
call :printError "Invalid choice! Please enter a number from 1 to 4."
goto choiceLoop

:web
cls
call :printHeader
call :printSection "Launching Web Interface..."
start "" http://localhost:5000
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
call :printHeader
call :printSection "Installing dependencies..."

REM === Download embedded Python if not present ===
if not exist "%PYEXE%" (
    call :printInfo "Downloading embedded Python..."
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.13.5/python-3.13.5-embed-amd64.zip' -OutFile 'python_embedded.zip'"
    if exist "python_embedded.zip" (
        call :printInfo "Extracting embedded Python..."
        powershell -Command "Expand-Archive -Path 'python_embedded.zip' -DestinationPath '%PYDIR%' -Force"
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
            powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'get-pip.py'"
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
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip' -OutFile 'ffmpeg.zip'"
    if exist "ffmpeg.zip" (
        call :printInfo "Extracting ffmpeg..."
        powershell -Command "Expand-Archive -Path 'ffmpeg.zip' -DestinationPath 'ffmpeg_temp' -Force"
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
call :runPython -m pip install -r requirements.txt
goto mainmenu

:exit
cls
call :printHeader
REM Delete the downloads folder if it exists
if exist "downloads" (
    rmdir /s /q "downloads"
)
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

:printMenu
echo ║  1. Start Web Interface                                    ║
echo ║  2. Command Line Help                                      ║
echo ║  3. Setup Dependencies                                     ║
echo ║  4. Exit                                                   ║
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