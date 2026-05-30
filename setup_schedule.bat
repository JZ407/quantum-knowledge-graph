@echo off
REM Setup scheduled task for knowledge graph auto-rebuild
REM Run this as Administrator

set TASK_NAME=QuantumKG_AutoBuild
set SCRIPT_PATH=D:\Claude_code\knowledge_graph\build_graph.py
set PYTHON_PATH=C:\Python314\python.exe

schtasks /Create /SC HOURLY /MO 4 /TN %TASK_NAME% /TR "%PYTHON_PATH% -X utf8 %SCRIPT_PATH%" /ST 08:00 /F

echo Task "%TASK_NAME%" created - runs every 4 hours from 08:00
schtasks /Query /TN %TASK_NAME%
pause
