@echo off
chcp 65001 >nul
title Instalar voz local da Marin
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Rode primeiro o instalar.bat
  pause & exit /b 1
)
echo Instalando a voz local Kokoro...
.venv\Scripts\python.exe -m pip install "kokoro-onnx>=0.4"
.venv\Scripts\python.exe baixar_voz_local.py
echo.
echo Testando a voz...
.venv\Scripts\python.exe testar_voz_local.py
pause
