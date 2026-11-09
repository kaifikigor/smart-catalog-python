@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "catalog_cleaner.py"
) else (
    python "catalog_cleaner.py"
)
echo.
pause
