@echo off
setlocal

echo ========================================
echo FPGA BASIC Build
echo ========================================

REM ----------------------------------------
REM Check project directory argument
REM ----------------------------------------

if "%~1"=="" (
    echo ERROR: Project directory argument is missing.
    exit /b 1
)

set "PROJECT_DIR=%~1"

echo.
echo Project Directory:
echo %PROJECT_DIR%

REM ----------------------------------------
REM Check project.json
REM ----------------------------------------

set "PROJECT_JSON=%PROJECT_DIR%\project.json"

if not exist "%PROJECT_JSON%" (
    echo ERROR: project.json not found.
    exit /b 1
)

REM ----------------------------------------
REM Change to project directory
REM ----------------------------------------

cd /d "%PROJECT_DIR%"

echo.
echo Current Directory:
cd

REM ----------------------------------------
REM Read project.json and create apio.ini
REM ----------------------------------------

echo.
echo ========================================
echo Creating apio.ini
echo ========================================

for /f "delims=" %%i in ('
python -c "import json; d=json.load(open('project.json', encoding='utf-8')); print(d['top_module'])"
') do set "TOP_MODULE=%%i"

for /f "delims=" %%i in ('
python -c "import json; d=json.load(open('project.json', encoding='utf-8')); print(d['sources'][0])"
') do set "SOURCE_FILE=%%i"

for /f "delims=" %%i in ('
python -c "import json; d=json.load(open('project.json', encoding='utf-8')); print(d['board'])"
') do set "BOARD_NAME=%%i"

REM ----------------------------------------
REM Convert board name to APIO board ID
REM ----------------------------------------

if "%BOARD_NAME%"=="iCESugar_1.5" (
    set "APIO_BOARD=icesugar-1-5"
)

if "%BOARD_NAME%"=="iCEBreaker 1.0e" (
    set "APIO_BOARD=icebreaker"
)

if "%APIO_BOARD%"=="" (
    echo ERROR: Unknown board.
    echo Board: %BOARD_NAME%
    exit /b 1
)

echo.
echo Board:
echo %APIO_BOARD%

echo Top Module:
echo %TOP_MODULE%

echo Source:
echo %SOURCE_FILE%

REM ----------------------------------------
REM Create apio.ini
REM ----------------------------------------

(
echo [env:default]
echo board = %APIO_BOARD%
echo top-module = %TOP_MODULE%
) > apio.ini

echo.
echo ========================================
echo Generated apio.ini
echo ========================================

type apio.ini

REM ----------------------------------------
REM Run APIO Build
REM ----------------------------------------

echo.
echo ========================================
echo Running APIO Build
echo ========================================

python -m apio build

set "BUILD_RESULT=%ERRORLEVEL%"

echo.
echo ========================================
echo BUILD RESULT
echo ========================================

if "%BUILD_RESULT%"=="0" (
    echo BUILD SUCCESS
	echo if you want to upload this bitstream, type python -m apio upload
) else (
    echo BUILD FAILED
    echo ERROR CODE: %BUILD_RESULT%
)

echo.
echo Build directory:

if exist "_build" (
    dir _build
) else (
    echo _build directory was not created.
)

echo.

exit /b %BUILD_RESULT%