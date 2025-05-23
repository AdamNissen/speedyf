@echo off
REM Activate virtual environment - adjust path as necessary
call ..\designer_app\venv_designer\Scripts\activate

REM Navigate to source directory
cd ..\designer_app\src

REM Run PyInstaller
pyinstaller --name SpeedyF_Designer --onefile --windowed --distpath ..\..\dist\designer --workpath ..\..\build\designer main_designer.py

REM Deactivate (optional, if script is run in a new cmd window)
REM deactivate
echo Designer build complete. Output in speedyf\dist\designer
pause