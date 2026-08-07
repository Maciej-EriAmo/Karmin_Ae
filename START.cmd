@echo off
REM Karmin_Ae — normalna sciezka dla CZLOWIEKA (Control Center GUI)
REM Agent SE: python agent_boot.py  (nie ten plik)
cd /d "%~dp0"
python karmin_app.py %*
if errorlevel 1 (
  echo.
  echo Jesli brak tkinter:  python holon_configure.py wizard
  pause
)
