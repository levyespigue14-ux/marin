"""Baixa o modelo XTTS (uma vez, ~1,8 GB) e testa a voz própria da Marin."""
import os
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
os.environ["COQUI_TOS_AGREED"] = "1"

import torch
import config

print("Placa de vídeo (CUDA):", "SIM" if torch.cuda.is_available() else "NÃO (vai usar o processador, fica mais lento)")
from TTS.api import TTS
print("Baixando/carregando o modelo de voz (na primeira vez demora)...")
TTS("tts_models/multilingual/multi-dataset/xtts_v2")
print("Modelo pronto!")

pasta = config.PASTA_VOZ_MARIN
os.makedirs(pasta, exist_ok=True)
audios = [f for f in os.listdir(pasta) if f.lower().endswith((".wav", ".mp3", ".flac", ".ogg", ".m4a"))]
if not audios:
    print(f"\nAinda não tem nenhum áudio da voz na pasta {pasta}.")
    print("Coloque lá o áudio gerado no ElevenLabs (veja o LEIA-ME.txt) e rode este instalador de novo.")
    sys.exit(0)

from core.tts import Voz
v = Voz()
print("\nMotor de voz:", v.motor)
v.falar(f"Oi, {config.COMO_ME_CHAMAR}! Agora essa é a minha voz pra sempre. Gostou?")
