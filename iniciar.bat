@echo off
chcp 65001 >nul
title Marin
cd /d "%~dp0"
rem Reabre esta janela preta (terminal) minimizada, pra ficar só a tela da Marin na frente
if not "%MARIN_MIN%"=="1" (set "MARIN_MIN=1" & start "Marin" /min cmd /c "%~f0" %* & exit /b)
if not exist .venv\Scripts\python.exe (
  echo Rode primeiro o instalar.bat
  pause & exit /b 1
)
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Ollama"
tasklist /FI "IMAGENAME eq ollama.exe" | find /I "ollama.exe" >nul || start "" /min ollama serve
rem Espera o Ollama responder (ate 40s). Importante quando a Marin abre junto com o Windows.
for /l %%i in (1,1,40) do (
  curl -s -o nul http://localhost:11434 && goto :ollama_ok
  timeout /t 1 >nul
)
:ollama_ok
.venv\Scripts\python.exe main.py %*
if errorlevel 1 pause
