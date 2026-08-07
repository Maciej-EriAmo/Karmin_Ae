@echo off
REM Prosty rytual pamieci — bez panelu
REM   SESSION.cmd start
REM   SESSION.cmd status
REM   SESSION.cmd fact "..."
REM   SESSION.cmd work "..."
REM   SESSION.cmd done
cd /d "%~dp0"
python karmin_session.py %*
if errorlevel 1 pause
