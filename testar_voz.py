"""Diagnóstico da voz: mostra se o ElevenLabs está funcionando (e quanto crédito sobrou)
e toca a mesma frase em cada voz para você escolher."""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import requests

import config
from core.tts import Voz

FRASE = f"Oi, {config.COMO_ME_CHAMAR}! Nossa, que bom te ver. Deixa comigo, já abri o WhatsApp pra você. Prontinho!"

print("=" * 60)
print("1) ElevenLabs")
print("=" * 60)
chave = config.ELEVENLABS_CHAVE
if not chave:
    print("Sem chave no .env (ELEVENLABS_CHAVE). A Marin está usando a voz reserva do Edge.")
else:
    try:
        r = requests.get("https://api.elevenlabs.io/v1/user/subscription",
                         headers={"xi-api-key": chave}, timeout=15)
        if r.status_code == 200:
            d = r.json()
            usado, limite = d.get("character_count", 0), d.get("character_limit", 0)
            print(f"Chave OK. Plano: {d.get('tier')}. Créditos usados: {usado} de {limite} "
                  f"(sobram {max(0, limite - usado)}).")
            reset = d.get("next_character_count_reset_unix")
            if reset:
                import datetime
                print("Os créditos renovam em:", datetime.datetime.fromtimestamp(reset).strftime("%d/%m/%Y às %H:%M"))
            if limite and usado >= limite:
                print(">>> OS CRÉDITOS ACABARAM: por isso a voz mudou para a reserva.")
        elif r.status_code == 401:
            print(">>> CHAVE INVÁLIDA (401). Gere uma chave nova no site do ElevenLabs e coloque no .env.")
        else:
            print(f"Resposta inesperada: {r.status_code} {r.text[:150]}")
    except Exception as e:
        print(f"Não consegui falar com o ElevenLabs: {e}")

    for modelo in [config.ELEVENLABS_MODELO, "eleven_multilingual_v2", "eleven_flash_v2_5"]:
        print(f"\n▶ ElevenLabs, modelo {modelo}")
        config.ELEVENLABS_MODELO = modelo
        v = Voz(log=print)
        v._combos = [(modelo, "pt"), (modelo, None)]
        v.falar(FRASE)
        print(f"   (motor usado: {v.motor})")

print("\n" + "=" * 60)
print("2) Vozes grátis do Edge (reserva)")
print("=" * 60)
config.ELEVENLABS_CHAVE = ""
for voz, tom, vel, nome in [
        ("pt-BR-FranciscaNeural", "+0Hz", "+0%", "Francisca natural"),
        ("pt-BR-FranciscaNeural", "+15Hz", "+5%", "Francisca fofinha (mais aguda)"),
        ("pt-BR-ThalitaMultilingualNeural", "+0Hz", "+0%", "Thalita (a de antes)")]:
    print(f"\n▶ Edge: {nome}")
    config.VOZ, config.TOM_VOZ, config.VELOCIDADE_VOZ = voz, tom, vel
    Voz(log=print).falar(FRASE)

print("\nMe conta qual soou melhor (e o que apareceu no item 1) que eu deixo a Marin com ela.")
input("\nAperte Enter para fechar...")
