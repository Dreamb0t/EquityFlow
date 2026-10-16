@echo off
rem Builds a single-file Windows executable at dist\EquityFlow.exe.
rem Run from anywhere: it switches to the project folder first.

cd /d "%~dp0"

python -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1

rem APScheduler loads its triggers/executors through package entry points,
rem which PyInstaller can't see on its own — hence the explicit collect/copy.
python -m PyInstaller --noconfirm --clean --onefile --windowed --name EquityFlow ^
    --collect-submodules apscheduler ^
    --copy-metadata apscheduler ^
    main.py
if errorlevel 1 exit /b 1

echo.
echo Built dist\EquityFlow.exe
