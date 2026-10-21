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
TRATAMENTO = ["mestre", "senhor", "meu senhor"]   # como ela te chama nas frases (sorteia um). O nome fica só na saudação
TRATAMENTOS = [TRATAMENTO] if isinstance(TRATAMENTO, str) else list(TRATAMENTO)


def tratamento():
    """Sorteia como a Marin te chama agora."""
    import random
    return random.choice(TRATAMENTOS)


PRONUNCIA_NOME = "Lévi"          # como a voz deve FALAR o seu nome (só muda o som, o texto continua "Levy")

# A música favorita dela ("toca sua música favorita"): abertura de My Dress-Up Darling, o anime da Marin
MUSICA_FAVORITA = "Sansan Days spira spica"

# Outras músicas que ela gosta: sorteadas quando você pede algo vago ("toca uma música", "toca qualquer coisa", "toca algo").
MUSICAS_FAVORITAS = [
    "Sansan Days spira spica",          # abertura de My Dress-Up Darling (o anime da Marin)
    "Idol YOASOBI",
    "Racing Into The Night YOASOBI",
    "Gurenge LiSA",
    "Kick Back Kenshi Yonezu",
]
CIDADE_PADRAO = "Teresina"       # usada no clima quando você não fala a cidade

# Palavras que ativam a Marin (o Whisper às vezes escreve o nome de outro jeito)
PALAVRAS_ATIVACAO = ["marin", "marim", "marina", "marine", "mari", "marrin", "ma rin"]

# --- Cérebro (Ollama rodando no seu PC) ---
OLLAMA_URL = "http://localhost:11434"
MODELO_IA = "qwen2.5:7b"         # bom em português e em usar ferramentas; cabe em 8 GB de VRAM
MAX_HISTORICO = 12               # quantas mensagens da conversa ela lembra
CONTEXTO_IA = 8192               # memória de trabalho da IA. 4096 ficou pequeno com todas as habilidades (ela "esquecia" as regras)

# --- Ouvido (Whisper) ---
WHISPER_MODELO = "small"         # tiny | base | small | medium  (medium é mais preciso, mais pesado)
WHISPER_DISPOSITIVO = "auto"     # auto | cuda | cpu
MICROFONE = None                 # None = padrão do Windows. Ou o número do dispositivo (veja: python main.py --microfones)

# Detecção de fala
SILENCIO_FIM = 0.7               # segundos de silêncio para considerar que você terminou de falar
FALA_MAXIMA = 15                 # segundos máximos de uma fala
SENSIBILIDADE = 1.4              # maior = precisa falar mais alto (ajuda em ambiente barulhento)
LIMIAR_MINIMO = 120              # volume mínimo para contar como fala. Microfone baixo? diminua (rode testar_microfone.bat)
TEMPO_CONVERSA = 6               # depois de responder, ela escuta X segundos sem precisar dizer "Marin"

# --- Voz ---
# Qual voz vem primeiro:
#   "elevenlabs" = voz exata do ElevenLabs enquanto tiver crédito; quando acabar, cai sozinha na voz própria (grátis)
#   "propria"    = sempre a voz própria no PC (grátis, mas a cópia não é perfeita)
VOZ_PRINCIPAL = "elevenlabs"
ELEVENLABS_VOZ_NOME = "marin"    # nome da voz em "My Voices" (se vazio, usa o ELEVENLABS_VOZ_ID)
CACHE_VOZ_MAX_CARACTERES = 200   # frases até esse tamanho ficam salvas: repetiu, não gasta crédito de novo

# A) VOZ PRÓPRIA DA MARIN (gravada uma vez, usada para sempre, grátis, roda no PC)
#    Coloque 1 a 3 áudios da voz dela (10 a 30 segundos cada, .wav ou .mp3) na pasta voz_marin/
#    e rode o instalar_voz_propria.bat. Sem os áudios, a Marin usa as opções abaixo.
USAR_VOZ_PROPRIA = True
VOZ_ATIVA = "marin"              # qual voz gravada a Marin usa (pasta vozes/<nome>/)
_BASE = os.path.dirname(os.path.abspath(__file__))
PASTA_VOZ_MARIN = os.path.join(_BASE, "vozes", VOZ_ATIVA)
if not os.path.isdir(PASTA_VOZ_MARIN):                     # compatibilidade com a pasta antiga
    PASTA_VOZ_MARIN = os.path.join(_BASE, "voz_marin")
VOZ_PROPRIA_VELOCIDADE = 1.0     # 0.8 a 1.3
VOZ_PROPRIA_EMOCAO = 0.6         # 0.4 = mais fiel à voz original, 0.9 = mais expressiva (mas o timbre "escapa")

# 0) Voz LOCAL (Kokoro): roda no seu PC, grátis e sem limite. Instale com o instalar_voz_local.bat.
#    Se os arquivos do modelo não existirem, a Marin pula para as opções abaixo.
USAR_VOZ_LOCAL = False          # desligada: a voz principal é o ElevenLabs (True para voltar a usar)
# Mistura de vozes: pf_dora = brasileira; jf_alpha / jf_gongitsune / jf_nezumi / jf_tebukuro = japonesas.
# Quanto maior o peso da japonesa, mais "anime" (e menos clara em português). Os pesos somam 1.
VOZ_LOCAL_MISTURA = {"pf_dora": 0.4, "jf_alpha": 0.6}
VOZ_LOCAL_VELOCIDADE = 1.05      # 0.8 a 1.3
VOZ_LOCAL_AGUDO = 1.12           # deixa a voz mais fina/fofa sem mudar a velocidade (1.0 = normal, até ~1.25)
PASTA_MODELOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modelos")

# 1) ElevenLabs: voz mais natural e fofa. Crie a chave e a voz seguindo o README (seção "Voz fofa").
#    A chave fica no arquivo .env (ELEVENLABS_CHAVE=...). Sem ela, a Marin usa a voz grátis do Edge.
ELEVENLABS_CHAVE = os.getenv("ELEVENLABS_CHAVE", "")
ELEVENLABS_VOZ_ID = "VJgOa7n4NKmFPqqBWkEg"
ELEVENLABS_MODELO = "eleven_v4_turbo"     # rápido e com sotaque melhor; "eleven_v4" = mais caprichado, mais lento
ELEVENLABS_ESTABILIDADE = 0.5            # menor = mais emotiva (mas abaixo de 0.4 o sotaque pode "escorregar"), maior = mais constante
ELEVENLABS_EXPRESSIVIDADE = 0.35          # 0 a 1
ELEVENLABS_VELOCIDADE = 1.05              # 0.7 a 1.2

# 2) Edge (grátis, reserva). Tom natural: mexer muito no TOM deixa a voz robótica.
VOZ = "pt-BR-FranciscaNeural"   # brasileira nativa (a Thalita "Multilingual" às vezes puxa sotaque gringo)
VELOCIDADE_VOZ = "+0%"
TOM_VOZ = "+0Hz"

# --- Interface ---
USAR_HUD = True
MAXIMIZAR_JANELAS = True         # tudo que a Marin abrir (sites, programas, YouTube) aparece maximizado
INICIAR_ESCONDIDA = False        # False = abre já mostrando a tela da Marin | True = abre escondida e só aparece quando você chama
ESCONDER_DEPOIS = 20             # segundos depois da conversa para ela sumir de novo (0 = fica na tela)
ATALHO_GLOBAL = "ctrl+alt+m"     # aperta para falar com ela sem dizer o nome ("" para desativar)

# --- Prospecção no WhatsApp ---
# Link do site-modelo que vai na primeira mensagem, por nicho ("padrao" = quando o nicho não está aqui).
LINKS_MODELO = {
    "fretes": "https://demerval-fretes.netlify.app",
    "energia solar": "https://solar-aurora.netlify.app",
    "sushi": "https://sumi-demo.netlify.app",
    "açaí": "https://igarape-acai.netlify.app",
    # "academia": "https://...netlify.app",
    # "hamburgueria": "https://...netlify.app",
    "padrao": "",
}
WHATSAPP_MODO = "app"           # "app" = WhatsApp do Windows | "web" = WhatsApp Web no navegador
DIAS_FOLLOWUP = 3                # depois de quantos dias sem resposta ela sugere o follow-up
LIMITE_DIARIO = 25               # máximo de mensagens de prospecção por dia (abordagem + follow-up)

# --- Gmail (avisos de e-mail importante) ---
# A senha NÃO fica aqui: coloque no arquivo .env
#   GMAIL_USUARIO=seuemail@gmail.com
#   GMAIL_SENHA_APP=senha de app de 16 letras (myaccount.google.com/apppasswords)
GMAIL_INTERVALO = 120            # de quantos em quantos segundos ela confere o Gmail
# Quem é importante: trecho do remetente -> como a Marin fala
GMAIL_REMETENTES = {
    "workana": "Workana", "99freelas": "99Freelas", "upwork": "Upwork",
    "gupy": "Gupy", "programathor": "ProgramaThor", "indeed": "Indeed",
    "linkedin": "LinkedIn", "remotive": "Remotive", "euremotejobs": "EU Remote Jobs",
}
# Assuntos que também merecem aviso, venha de quem vier
GMAIL_PALAVRAS = ["entrevista", "processo seletivo", "candidatura", "proposta", "orçamento", "orcamento", "site"]
