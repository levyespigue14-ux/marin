"""Testa a voz local da Marin."""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import config
from core.tts import Voz

v = Voz()
print("Motor de voz:", v.motor)
print("Mistura:", config.VOZ_LOCAL_MISTURA)
v.falar(f"Oi, {config.COMO_ME_CHAMAR}! Agora eu tenho uma voz nova, só minha. Gostou?")
