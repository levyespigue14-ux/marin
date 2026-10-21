@echo off
chcp 65001 >nul
title Instalar a voz propria da Marin
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Rode primeiro o instalar.bat
  pause & exit /b 1
)
echo ============================================================
echo  Voz propria da Marin (modelo XTTS-v2 da Coqui)
echo  Licenca do modelo: Coqui Public Model License - uso NAO comercial.
echo  Para uso pessoal na Marin esta tudo certo.
echo  Vai baixar uns 4 GB na primeira vez (PyTorch + modelo).
echo ============================================================
set /p OK=Digite S e aperte Enter para aceitar a licenca e instalar: 
if /I not "%OK%"=="S" exit /b 0
echo.
echo [1/3] Instalando o PyTorch com suporte a placa de video...
.venv\Scripts\python.exe -m pip install "torch<2.9" "torchaudio<2.9" --index-url https://download.pytorch.org/whl/cu128
echo.
echo [2/3] Instalando o gerador de voz...
.venv\Scripts\python.exe -m pip install coqui-tts "transformers<5"
echo.
echo [3/3] Baixando o modelo e testando...
.venv\Scripts\python.exe preparar_voz_propria.py
pause
