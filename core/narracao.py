"""Narração de vídeos na voz da Marin (ElevenLabs).

"Marin, grava a narração do vídeo" -> grava um mp3 por fala da lista CENAS em
"Claude outputs/narracao_linkedin/". Para mudar as falas, edite CENAS e peça de novo.
"""
import os

import requests

import config
from core.ferramentas import RAIZ, habilidade, maximizar_depois

CENAS = [
    "Oi! Eu sou a Marin, a assistente de voz que o Levy criou. Hoje eu vou te mostrar o robô de vídeos que ele fez!",
    "Primeiro, o robô busca produtos em alta. Ele filtra por nota, desconto e quantidade de vendas, "
    "e a cada vídeo ele troca de nicho: casa, tecnologia, moda e beleza.",
    "Depois, a inteligência artificial escreve o roteiro: o gancho, as falas e a legenda, tudo pensado pra cada produto.",
    "Aí ele monta o vídeo sozinho: foto em movimento, voz de IA, música e legendas animadas. "
    "Olha esse aqui, feito cem por cento pelo robô!",
    "Quando fica pronto, o vídeo chega no Telegram do Levy, com a legenda e o link. Ele só revisa e posta.",
    "E o melhor: ele roda sozinho, duas vezes por dia, às onze da manhã e às sete da noite.",
    "Tudo feito com Python, inteligência artificial e muita automação. Gostou? Fala com o Levy aqui no LinkedIn!",
]

PASTA = os.path.join(RAIZ, "Claude outputs", "narracao_linkedin")


def _voz_id(h):
    voz = config.ELEVENLABS_VOZ_ID
    nome = (getattr(config, "ELEVENLABS_VOZ_NOME", "") or "").strip().lower()
    try:
        r = requests.get("https://api.elevenlabs.io/v1/voices", headers=h, timeout=20)
        for v in r.json().get("voices", []) if r.status_code == 200 else []:
            if v.get("name", "").strip().lower() == nome:
                return v["voice_id"]
    except Exception:
        pass
    return voz


@habilidade("Grava, na voz da Marin, a narração do vídeo do robô para o LinkedIn (um áudio por cena).")
def gravar_narracao_video():
    if not config.ELEVENLABS_CHAVE:
        return "Falta a chave do ElevenLabs no arquivo .env."
    os.makedirs(PASTA, exist_ok=True)
    h = {"xi-api-key": config.ELEVENLABS_CHAVE, "Content-Type": "application/json"}
    voz = _voz_id(h)
    anterior = ""
    for i, texto in enumerate(CENAS, 1):
        # exatamente a mesma voz e os mesmos ajustes que a Marin usa para falar no dia a dia (config.py)
        corpo = {"text": texto, "model_id": config.ELEVENLABS_MODELO, "language_code": "pt",
                 "previous_text": anterior,
                 "voice_settings": {"stability": config.ELEVENLABS_ESTABILIDADE, "similarity_boost": 0.8,
                                    "style": config.ELEVENLABS_EXPRESSIVIDADE, "use_speaker_boost": True,
                                    "speed": config.ELEVENLABS_VELOCIDADE}}
        r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voz}",
                          params={"output_format": "mp3_44100_128"}, headers=h, timeout=120, json=corpo)
        if r.status_code in (400, 422) and ("language" in r.text.lower() or "previous" in r.text.lower()):
            corpo.pop("language_code", None)
            corpo.pop("previous_text", None)
            r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voz}",
                              params={"output_format": "mp3_44100_128"}, headers=h, timeout=120, json=corpo)
        if r.status_code != 200:
            if r.status_code == 401 or "quota" in r.text.lower():
                return f"Parei na fala {i}: acabou o crédito do ElevenLabs ou a chave está inválida."
            return f"Parei na fala {i}: o ElevenLabs deu erro {r.status_code}."
        with open(os.path.join(PASTA, f"cena_{i}.mp3"), "wb") as f:
            f.write(r.content)
        anterior = texto
    try:
        maximizar_depois()
        os.startfile(PASTA)
    except Exception:
        pass
    return f"Prontinho! Gravei as {len(CENAS)} falas da narração e abri a pasta. Pode avisar o Claude."
