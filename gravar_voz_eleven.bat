@echo off
chcp 65001 >nul
title Gravar a voz da Marin
cd /d "%~dp0"
.venv\Scripts\python.exe gravar_voz_eleven.py %*
pause
