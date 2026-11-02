@echo off
REM Windows 一键打包脚本
REM 需要: pip install -r requirements.txt pyinstaller
REM 用法: 双击运行或在命令行执行 build.bat
chcp 65001 >nul
cd /d %~dp0
pip install pyinstaller customtkinter rapidfuzz numpy sounddevice
pyinstaller --noconfirm --onefile --windowed --name Toolbox ^
  --collect-all customtkinter ^
  --collect-submodules apps ^
  --collect-submodules core ^
  --hidden-import sounddevice ^
  --hidden-import numpy ^
  --hidden-import rapidfuzz ^
  main.py
echo.
echo 完成! 可执行文件在 dist\Toolbox.exe
pause
