"""Configurações da Marin. Altere à vontade."""
import os
from pathlib import Path

# Carrega as chaves secretas do arquivo .env (ele fica só no seu PC e não vai pro GitHub)
_env = Path(__file__).with_name(".env")
if _env.exists():
    for _linha in _env.read_text(encoding="utf-8").splitlines():
        _linha = _linha.strip()
        if _linha and not _linha.startswith("#") and "=" in _linha:
            _k, _v = _linha.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# --- Identidade ---
NOME = "Marin"
COMO_ME_CHAMAR = "Levy"          # como a Marin chama você
CIDADE_PADRAO = "Teresina"       # usada no clima quando você não fala a cidade

# Palavras que ativam a Marin (o Whisper às vezes escreve o nome de outro jeito)
PALAVRAS_ATIVACAO = ["marin", "marim", "marina", "marine", "mari", "marrin", "ma rin"]

# --- Cérebro (Ollama rodando no seu PC) ---
OLLAMA_URL = "http://localhost:11434"
MODELO_IA = "qwen2.5:7b"         # bom em português e em usar ferramentas; cabe em 8 GB de VRAM
MAX_HISTORICO = 12               # quantas mensagens da conversa ela lembra
CONTEXTO_IA = 4096               # memória de trabalho da IA (menor = mais rápido)

# --- Ouvido (Whisper) ---
WHISPER_MODELO = "small"         # tiny | base | small | medium  (medium é mais preciso, mais pesado)
WHISPER_DISPOSITIVO = "auto"     # auto | cuda | cpu
MICROFONE = None                 # None = padrão do Windows. Ou o número do dispositivo (veja: python main.py --microfones)

# Detecção de fala
SILENCIO_FIM = 0.7               # segundos de silêncio para considerar que você terminou de falar
FALA_MAXIMA = 15                 # segundos máximos de uma fala
SENSIBILIDADE = 2.8              # maior = precisa falar mais alto (ajuda em ambiente barulhento)
TEMPO_CONVERSA = 6               # depois de responder, ela escuta X segundos sem precisar dizer "Marin"

# --- Voz ---
# 1) ElevenLabs: voz mais natural e fofa. Crie a chave e a voz seguindo o README (seção "Voz fofa").
#    A chave fica no arquivo .env (ELEVENLABS_CHAVE=...). Sem ela, a Marin usa a voz grátis do Edge.
ELEVENLABS_CHAVE = os.getenv("ELEVENLABS_CHAVE", "")
ELEVENLABS_VOZ_ID = "VJgOa7n4NKmFPqqBWkEg"
ELEVENLABS_MODELO = "eleven_v4_turbo"     # rápido e com sotaque melhor; "eleven_v4" = mais caprichado, mais lento
ELEVENLABS_ESTABILIDADE = 0.3            # menor = mais expressiva/emotiva, maior = mais constante
ELEVENLABS_EXPRESSIVIDADE = 0.35          # 0 a 1
ELEVENLABS_VELOCIDADE = 1.05              # 0.7 a 1.2

# 2) Edge (grátis, reserva). Tom natural: mexer muito no TOM deixa a voz robótica.
VOZ = "pt-BR-ThalitaMultilingualNeural"   # ou "pt-BR-FranciscaNeural"
VELOCIDADE_VOZ = "+6%"
TOM_VOZ = "+0Hz"

# --- Interface ---
USAR_HUD = True
ATALHO_GLOBAL = "ctrl+alt+m"     # aperta para falar com ela sem dizer o nome ("" para desativar)
