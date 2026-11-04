@echo off
REM Windows build script for Toolbox.exe (PyInstaller one-file).
REM Pure ASCII + CRLF on purpose: cmd parses bat as GBK, Chinese text
REM and broken line-continuation (^) will silently wreck the whole script.
chcp 65001 >nul
cd /d %~dp0
if exist Toolbox.spec del Toolbox.spec
.venv\Scripts\python.exe -m pip install pyinstaller PySide6-Essentials rapidfuzz numpy sounddevice
.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed --name Toolbox --icon toolbox.ico --add-data "toolbox.ico;." --collect-submodules apps --collect-submodules core --hidden-import sounddevice --hidden-import numpy --hidden-import rapidfuzz main.py
if errorlevel 1 (
  echo BUILD FAILED
  pause
  exit /b 1
)
echo Done. Executable is at dist\Toolbox.exe
pause
