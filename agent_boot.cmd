@echo off
REM Jedno kliknięcie / jedna linia dla Grok i operatora
cd /d "%~dp0"
python agent_boot.py %*
