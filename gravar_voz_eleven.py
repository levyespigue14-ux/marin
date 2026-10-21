"""Grava vozes do ElevenLabs para a Marin usar para sempre (voz própria, no PC).

Grava TUDO DE UMA VEZ: um único pedido por voz, com todo o texto do arquivo textos_para_gravar.txt.
Dá para gravar várias vozes no mesmo comando:  gravar_voz_eleven.bat marin, outra_voz
Cada voz fica na sua pasta: vozes/<nome>/.  A voz que a Marin usa é a VOZ_ATIVA do config.py.
"""
import os
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import requests

import config

BASE = os.path.dirname(os.path.abspath(__file__))
ARQ_TEXTOS = os.path.join(BASE, "textos_para_gravar.txt")
PADRAO = """Oi, Levy! Que bom te ver de novo, eu tava com saudade! Deixa comigo, já abri o WhatsApp pra você.
Hmm, deixa eu pensar um pouquinho... Ah, achei! São três clientes novos esperando resposta.
Nossa, que notícia boa! Parabéns, você mandou muito bem hoje. Agora vai descansar, tá bom?"""

chave = config.ELEVENLABS_CHAVE
if not chave:
    sys.exit("Falta a ELEVENLABS_CHAVE no arquivo .env.")
H = {"xi-api-key": chave, "Content-Type": "application/json"}

texto = open(ARQ_TEXTOS, encoding="utf-8").read().strip() if os.path.exists(ARQ_TEXTOS) else PADRAO
texto = "\n".join(l for l in texto.splitlines() if l.strip() and not l.lstrip().startswith("#"))
print(f"Texto para gravar: {len(texto)} caracteres (é o que vai gastar de crédito por voz).")

entrada = " ".join(sys.argv[1:]).strip() or input("Nome(s) ou ID(s) da voz, separados por vírgula (ex.: marin): ").strip()
pedidos = [p.strip() for p in entrada.split(",") if p.strip()] or ["marin"]

try:
    r = requests.get("https://api.elevenlabs.io/v1/voices", headers=H, timeout=20)
    vozes = r.json().get("voices", []) if r.status_code == 200 else []
    if r.status_code != 200:
        print(f"(Não consegui listar suas vozes: {r.status_code}. Se der 'voice not found', a chave é de outra conta.)")
except Exception:
    vozes = []


def achar(p):
    for v in vozes:
        if v.get("voice_id") == p or v.get("name", "").strip().lower() == p.lower():
            return v["voice_id"], v.get("name", p)
    return p, p   # tenta como ID mesmo


def gerar(voz_id, corpo):
    return requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voz_id}",
                         params={"output_format": "mp3_44100_128"}, headers=H, json=corpo, timeout=180)


ok = []
for p in pedidos:
    voz_id, nome = achar(p)
    pasta_nome = "".join(c for c in nome.lower() if c.isalnum() or c in "-_") or "voz"
    print(f"\nGravando a voz '{nome}' (tudo de uma vez)...")
    corpo = {"text": texto, "model_id": "eleven_multilingual_v2", "language_code": "pt",
             "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.4, "use_speaker_boost": True}}
    r = gerar(voz_id, corpo)
    if r.status_code in (400, 422) and "language" in r.text.lower():
        corpo.pop("language_code")
        r = gerar(voz_id, corpo)
    if r.status_code != 200:
        if r.status_code == 404:
            print(">>> Voz não encontrada nessa conta. Troque a chave do .env pela da conta onde a voz está.")
        elif r.status_code == 401 or "quota" in r.text.lower():
            print(">>> Sem crédito ou chave inválida no ElevenLabs.")
        else:
            print(f">>> Erro do ElevenLabs: {r.status_code} {r.text[:200]}")
        continue
    pasta = os.path.join(BASE, "vozes", pasta_nome)
    os.makedirs(pasta, exist_ok=True)
    destino = os.path.join(pasta, f"{pasta_nome}.mp3")
    with open(destino, "wb") as f:
        f.write(r.content)
    print(f"  salvo em {destino}")
    ok.append(pasta_nome)

if ok:
    print(f"\nPronto! Vozes gravadas: {', '.join(ok)}.")
    print(f"A Marin usa a voz definida em VOZ_ATIVA no config.py (agora: '{getattr(config, 'VOZ_ATIVA', 'marin')}').")
    print("Teste com o testar_voz_propria.bat.")
