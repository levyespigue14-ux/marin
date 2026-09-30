@echo off
chcp 65001 >nul
title Instalando a Marin
cd /d "%~dp0"
echo.
echo  ===============================================
echo    MARIN - instalacao
echo  ===============================================
echo.

rem ---- 1. Python 3.12 (ou 3.11) ----
call :achar_python
if not defined PY (
  echo [1/5] Python 3.12 nao encontrado. Instalando pelo winget...
  winget install -e --id Python.Python.3.12 --scope user --accept-source-agreements --accept-package-agreements
  call :achar_python
)
if not defined PY (
  echo.
  echo [ERRO] Nao consegui instalar o Python 3.12 automaticamente.
  echo        Baixe em https://www.python.org/downloads/release/python-31210/
  echo        ^(role ate "Windows installer 64-bit"^), instale e rode este arquivo de novo.
  pause & exit /b 1
)
echo [1/5] Usando:
%PY% --version

rem ---- 2. Ambiente virtual ----
if exist .venv (
  .venv\Scripts\python.exe -c "import sys; sys.exit(0 if sys.version_info[:2] in [(3,11),(3,12)] else 1)" >nul 2>&1
  if errorlevel 1 (
    echo [2/5] Ambiente antigo com versao errada do Python. Recriando...
    rmdir /s /q .venv
  )
)
if not exist .venv (
  echo [2/5] Criando ambiente virtual...
  %PY% -m venv .venv
  if errorlevel 1 (echo [ERRO] Falha ao criar o ambiente. & pause & exit /b 1)
) else (
  echo [2/5] Ambiente virtual ok.
)
set "VPY=%~dp0.venv\Scripts\python.exe"
rem usamos "python -m pip" em vez de pip.exe (o Windows bloqueia o pip.exe)
"%VPY%" -m pip install --upgrade pip >nul

rem ---- 3. Bibliotecas ----
echo [3/5] Instalando bibliotecas (pode demorar alguns minutos)...
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 (echo [ERRO] Falha ao instalar bibliotecas. Tire um print e mande pro Claude. & pause & exit /b 1)
echo       Instalando suporte a placa de video NVIDIA para o Whisper (cerca de 1 GB)...
"%VPY%" -m pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
if errorlevel 1 echo       [aviso] Sem CUDA: o Whisper vai usar a CPU. Funciona, so fica um pouco mais lento.

rem ---- 4. Ollama (cerebro) ----
where ollama >nul 2>&1
if errorlevel 1 if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Ollama"
where ollama >nul 2>&1
if errorlevel 1 (
  echo [4/5] Instalando o Ollama...
  winget install -e --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
  set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Ollama"
) else (
  echo [4/5] Ollama ja instalado.
)
where ollama >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Nao consegui instalar o Ollama. Baixe em https://ollama.com/download e rode este arquivo de novo.
  pause & exit /b 1
)
tasklist /FI "IMAGENAME eq ollama.exe" | find /I "ollama.exe" >nul || start "" /min ollama serve
timeout /t 4 >nul
echo       Baixando o modelo de IA qwen2.5:7b (cerca de 4,7 GB, so na primeira vez)...
ollama pull qwen2.5:7b

rem ---- 5. Modelo de voz para texto ----
echo [5/5] Baixando o modelo do Whisper...
"%VPY%" -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8'); print('      Whisper ok')"

echo.
echo  ===============================================
echo    Pronto! Para abrir a Marin, rode iniciar.bat
echo  ===============================================
pause
exit /b 0

:achar_python
set PY=
py -3.12 --version >nul 2>&1 && set "PY=py -3.12" && goto :eof
py -3.11 --version >nul 2>&1 && set "PY=py -3.11" && goto :eof
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"" && goto :eof
if exist "%ProgramFiles%\Python312\python.exe" set "PY="%ProgramFiles%\Python312\python.exe"" && goto :eof
goto :eof
