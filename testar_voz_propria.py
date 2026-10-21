"""Mostra qual voz a Marin está usando, toca um teste e salva um relatório em voz_marin/diagnostico.txt."""
import os
import shutil
import sys
import traceback
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

LOG = []


def log(msg):
    print(msg)
    LOG.append(str(msg))


import config
pasta = config.PASTA_VOZ_MARIN
try:
    log(f"Arquivos em voz_marin: {os.listdir(pasta)}")
    try:
        import torch
        log(f"torch {torch.__version__} | CUDA: {torch.cuda.is_available()}")
    except Exception as e:
        log(f"torch não importa: {e}")
    try:
        import TTS
        log(f"coqui-tts OK ({getattr(TTS, '__version__', '?')})")
    except Exception as e:
        log(f"coqui-tts não importa: {e}")
    from core.tts import Voz
    v = Voz(log=log)
    log(f">>> Motor de voz em uso: {v.motor}")
    caminho = v.gerar(f"Oi, {config.COMO_ME_CHAMAR}! Essa é a minha voz. Ficou parecida?")
    log(f"Áudio gerado: {caminho}")
    if isinstance(caminho, str) and os.path.exists(caminho):
        shutil.copy(caminho, os.path.join(pasta, "teste_saida" + os.path.splitext(caminho)[1]))
        v.tocar(caminho)
except Exception:
    log(traceback.format_exc())
finally:
    with open(os.path.join(pasta, "diagnostico.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(LOG))
    print("\nRelatório salvo em voz_marin/diagnostico.txt")
input("\nAperte Enter para fechar...")
