@echo off
chcp 65001 >nul
title Marin
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Rode primeiro o instalar.bat
  pause & exit /b 1
)
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Ollama"
tasklist /FI "IMAGENAME eq ollama.exe" | find /I "ollama.exe" >nul || start "" /min ollama serve
.venv\Scripts\python.exe main.py %*
if errorlevel 1 pause
