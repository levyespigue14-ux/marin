@echo off
chcp 65001 >nul
title Marin - iniciar junto com o Windows
cd /d "%~dp0"
set "ATALHO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Marin.lnk"

rem Rodar de novo desliga (liga/desliga)
if exist "%ATALHO%" (
  del "%ATALHO%"
  echo.
  echo  A Marin NAO vai mais abrir junto com o Windows.
  echo  Para ligar de novo, rode este arquivo outra vez.
  echo.
  pause
  exit /b 0
)

if not exist .venv\Scripts\python.exe (
  echo Rode primeiro o instalar.bat
  pause & exit /b 1
)

set "ALVO=%~dp0iniciar.bat"
set "PASTA=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:ATALHO); $s.TargetPath=$env:ALVO; $s.WorkingDirectory=$env:PASTA; $s.WindowStyle=7; $s.Description='Marin - assistente por voz'; $s.Save()"

if exist "%ATALHO%" (
  echo.
  echo  Pronto! A Marin vai abrir sozinha quando voce ligar o PC.
  echo  A janela preta abre minimizada; a interface aparece normal.
  echo  Para desligar, rode este arquivo de novo.
  echo.
) else (
  echo.
  echo  [ERRO] Nao consegui criar o atalho. Tire um print e mande pro Claude.
  echo.
)
pause
