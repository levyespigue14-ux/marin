"""Toca a mesma frase em cada voz disponível para você escolher."""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import config
from core.tts import Voz

FRASE = f"Oi, {config.COMO_ME_CHAMAR}! Nossa, que bom te ver. Deixa comigo, já abri o YouTube pra você. Prontinho!"

if config.ELEVENLABS_CHAVE:
    print(f"\n▶ ElevenLabs (voz {config.ELEVENLABS_VOZ_ID})")
    Voz().falar(FRASE)
else:
    print("\n(ElevenLabs não configurado: veja a seção 'Voz fofa' do README)")

chave = config.ELEVENLABS_CHAVE
config.ELEVENLABS_CHAVE = ""   # agora testa só as vozes do Edge
for voz, tom in [("pt-BR-ThalitaMultilingualNeural", "+0Hz"), ("pt-BR-ThalitaMultilingualNeural", "+12Hz"),
                 ("pt-BR-FranciscaNeural", "+0Hz"), ("pt-BR-FranciscaNeural", "+12Hz")]:
    print(f"\n▶ Edge: {voz}  tom {tom}")
    config.VOZ, config.TOM_VOZ = voz, tom
    Voz().falar(FRASE)

print("\nPara usar uma delas, ajuste VOZ e TOM_VOZ no config.py.")
