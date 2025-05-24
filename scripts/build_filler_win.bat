@echo off
ECHO Building SpeedyF Filler Program...

REM Define project root relative to this script's location
SET "SCRIPT_DIR=%~dp0"
SET "PROJECT_ROOT=%SCRIPT_DIR%..\"

REM Activate virtual environment
ECHO Activating filler virtual environment...
call "%PROJECT_ROOT%exported_program_template\venv_filler\Scripts\activate.bat"
IF ERRORLEVEL 1 (
    ECHO Failed to activate virtual environment. Exiting.
    PAUSE
    EXIT /B 1
)

REM Navigate to source directory
ECHO Changing to source directory...
cd "%PROJECT_ROOT%exported_program_template\src"
IF NOT EXIST main_filler.py (
    ECHO main_filler.py not found in %PROJECT_ROOT%exported_program_template\src. Exiting.
    cd "%SCRIPT_DIR%"
    call "%PROJECT_ROOT%exported_program_template\venv_filler\Scripts\deactivate.bat"
    PAUSE
    EXIT /B 1
)

REM Run PyInstaller - Outputting to PROJECT_ROOT\dist\filler
ECHO Running PyInstaller for SpeedyF Filler...
REM From .../src/, ..\.. gets to PROJECT_ROOT
pyinstaller --name SpeedyF_Filler --onefile --windowed --distpath "%PROJECT_ROOT%dist\filler" --workpath "%PROJECT_ROOT%build\filler" main_filler.py
IF ERRORLEVEL 1 (
    ECHO PyInstaller failed.
    cd "%SCRIPT_DIR%"
    call "%PROJECT_ROOT%exported_program_template\venv_filler\Scripts\deactivate.bat"
    PAUSE
    EXIT /B 1
)

ECHO SpeedyF Filler build complete. Output in %PROJECT_ROOT%dist\filler

REM Change back to the original scripts directory
cd "%SCRIPT_DIR%"

REM Deactivate virtual environment
ECHO Deactivating virtual environment...
call "%PROJECT_ROOT%exported_program_template\venv_filler\Scripts\deactivate.bat"

PAUSE