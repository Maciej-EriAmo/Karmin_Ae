@echo off
REM EriAmo brainstorm chat (main_aware) — wspolna holon_memory.json
REM Panel: START.cmd  |  Agent SE: python agent_boot.py
cd /d "%~dp0"
title Karmin_Ae — chat / brainstorm
python main_aware.py
if errorlevel 1 pause
