@echo off
echo Checking Python...
python --version

echo.
echo Checking pyinstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing pyinstaller...
    pip install pyinstaller
)

echo.
echo Preparing files...
if exist "dist" rmdir /s /q dist
mkdir dist\data

copy main_app.py dist\ >nul
copy data\time_sync.py dist\data\ >nul
copy data\config.json dist\data\ >nul

echo Building exe...
python -m PyInstaller --onefile --windowed --name ZGIRC_TimeSync --distpath dist --workpath build --specpath . dist\main_app.py

echo.
echo Done! Check dist folder.
pause
