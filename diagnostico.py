"""Testa cada peça da Marin e mostra o que o Windows está bloqueando."""
import importlib
import sys
import traceback

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PECAS = [
    ("numpy", "numpy", "base de tudo"),
    ("sounddevice", "sounddevice", "microfone"),
    ("requests", "requests", "internet"),
    ("onnxruntime", "onnxruntime", "detector de voz do Whisper"),
    ("ctranslate2", "ctranslate2", "motor do Whisper (ouvido)"),
    ("faster_whisper", "faster_whisper", "Whisper (ouvido)"),
    ("edge_tts", "edge_tts", "voz online"),
    ("pygame", "pygame", "tocar a voz"),
    ("pyttsx3", "pyttsx3", "voz reserva do Windows"),
    ("webview", "webview", "janela HUD"),
    ("clr", "clr", "ponte .NET da janela HUD"),
    ("ddgs", "ddgs", "pesquisa na web"),
    ("PIL.ImageGrab", "PIL", "print da tela"),
    ("keyboard", "keyboard", "atalho Ctrl+Alt+M"),
]

print("\n=== DIAGNOSTICO DA MARIN ===")
print("Python", sys.version.split()[0], "\n")

from core.stt import _desviar_av, _registrar_dlls_cuda
_registrar_dlls_cuda()
_desviar_av()

bloqueados = []
for modulo, pacote, papel in PECAS:
    try:
        importlib.import_module(modulo)
        print(f"  OK         {pacote:16} {papel}")
    except Exception as e:
        msg = str(e)
        tipo = "BLOQUEADO" if ("Controle de Aplicativo" in msg or "Application Control" in msg
                               or "Device Guard" in msg or "4551" in msg) else "ERRO"
        bloqueados.append((pacote, tipo, msg))
        print(f"  {tipo:10} {pacote:16} {papel}")
        print(f"             -> {msg[:150]}")

print()
if "faster_whisper" not in [b[0] for b in bloqueados] and "ctranslate2" not in [b[0] for b in bloqueados]:
    print("Testando o Whisper de verdade (baixa o modelo na primeira vez)...")
    try:
        import numpy as np
        from core.stt import Transcritor
        t = Transcritor()
        t.transcrever(np.zeros(16000, dtype=np.float32))
        print(f"  OK         Whisper rodando na {t.dispositivo}")
    except Exception as e:
        print("  ERRO       Whisper:", str(e)[:200])
        traceback.print_exc()

print()
if bloqueados:
    print(f"{len(bloqueados)} peca(s) com problema. Tire um print desta tela e mande pro Claude.")
else:
    print("Tudo certo! Pode rodar o iniciar.bat")
