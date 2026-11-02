# Windows 一键打包脚本
# 需要: pip install pyinstaller customtkinter rapidfuzz
# 用法: 双击运行或执行 build.bat
@echo off
chcp 65001 >nul
cd /d %~dp0
pip install pyinstaller customtkinter rapidfuzz
pyinstaller --noconfirm --onefile --windowed --name Toolbox ^
  --collect-all customtkinter ^
  main.py
echo.
echo 完成! 可执行文件在 dist\Toolbox.exe
pause
