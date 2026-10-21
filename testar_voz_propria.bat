@echo off
chcp 65001 >nul
title Testar voz propria da Marin
cd /d "%~dp0"
.venv\Scripts\python.exe testar_voz_propria.py
