"""Grava 5 segundos, salva em data/teste_ouvido.wav e mostra o que o Whisper entendeu."""
import os
import sys
import time
import wave

import numpy as np
import sounddevice as sd

import config

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TAXA = 16000
disp = config.MICROFONE
print("\nMicrofone:", sd.query_devices(disp if disp is not None else sd.default.device[0])["name"])
print("Quando aparecer FALE AGORA, diga: 'Marin, que horas são?'\n")
time.sleep(1)
print(">>> FALE AGORA (5 segundos) <<<")
audio = sd.rec(int(5 * TAXA), samplerate=TAXA, channels=1, dtype="int16", device=disp)
sd.wait()
print("Gravado.\n")
a = audio[:, 0]
os.makedirs("data", exist_ok=True)
with wave.open(os.path.join("data", "teste_ouvido.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(TAXA); w.writeframes(a.tobytes())

blocos = a[: len(a) // 480 * 480].reshape(-1, 480).astype(np.float32)
rms = np.sqrt((blocos ** 2).mean(axis=1))
print(f"Volume: minimo {rms.min():.0f} | mediano {np.median(rms):.0f} | maximo {rms.max():.0f}")

from core.stt import Transcritor
t = Transcritor()
f = a.astype(np.float32) / 32768.0
print(f"Whisper na {t.dispositivo}")
seg, _ = t.modelo.transcribe(f, language="pt", beam_size=1, vad_filter=False)
print("Entendeu (sem filtro):", " ".join(s.text.strip() for s in seg) or "(nada)")
seg, _ = t.modelo.transcribe(f, language="pt", beam_size=1, vad_filter=True)
print("Entendeu (com filtro):", " ".join(s.text.strip() for s in seg) or "(nada)")
print("\nTire um print desta tela e mande pro Claude.")
