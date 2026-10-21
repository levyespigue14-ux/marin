"""Mostra o volume do microfone em tempo real, para ajustar a Marin.
Fale normalmente por alguns segundos e veja os números."""
import sys
import time

import numpy as np
import sounddevice as sd

import config

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

disp = config.MICROFONE
if len(sys.argv) > 1:
    disp = int(sys.argv[1])
nome = sd.query_devices(disp if disp is not None else sd.default.device[0])["name"]
print(f"\nTestando o microfone: {nome}")
print("Fique 3 segundos em silencio e depois fale normalmente. (Ctrl+C para sair)\n")

niveis = []


def cb(indata, frames, t, status):
    rms = float(np.sqrt(np.mean(indata[:, 0].astype(np.float32) ** 2)))
    niveis.append(rms)


with sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=480, device=disp, callback=cb):
    inicio = time.time()
    try:
        while time.time() - inicio < 15:
            time.sleep(0.15)
            if niveis:
                v = max(niveis[-5:])
                barra = "#" * min(60, int(v / 25))
                print(f"\r  volume {v:6.0f} |{barra:<60}|", end="", flush=True)
    except KeyboardInterrupt:
        pass

arr = np.array(niveis)
silencio = float(np.median(arr[: int(len(arr) * 0.2)])) if len(arr) else 0
pico = float(np.percentile(arr, 95)) if len(arr) else 0
print(f"\n\nSilencio: ~{silencio:.0f}   Sua voz (pico): ~{pico:.0f}")
limiar = max(silencio * config.SENSIBILIDADE, config.LIMIAR_MINIMO)
print(f"A Marin hoje so escuta acima de: {limiar:.0f}")
if pico < 30:
    print("-> Quase nada chegou. Microfone errado, mudo ou bloqueado no Windows.")
elif pico < silencio * 2:
    print("-> Sua voz quase nao se destaca do barulho de fundo.")
    print("   1) Aumente o volume do microfone no Windows (Configuracoes > Sistema > Som > Entrada > Volume 100).")
    print("   2) Fale mais perto do microfone e rode este teste de novo.")
    sug = max(1.1, round(pico / max(silencio, 1) * 0.85, 1))
    print(f"   3) Se ainda assim ficar baixo, no config.py coloque SENSIBILIDADE = {sug}")
elif pico < limiar * 1.3:
    sug = max(1.1, round(pico / max(silencio, 1) * 0.6, 1))
    print(f"-> Sua voz esta baixa para a Marin. No config.py coloque SENSIBILIDADE = {sug}")
else:
    print("-> Volume ok! A Marin deve te ouvir bem.")
