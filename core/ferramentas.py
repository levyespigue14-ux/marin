"""Habilidades da Marin. Cada função com @habilidade vira uma ferramenta que a IA pode usar.

Para criar uma habilidade nova: escreva a função, decore com @habilidade(descrição, parâmetros)
e pronto — a Marin já passa a saber usar.
"""
import difflib
import glob
import os
import re
import subprocess
import sys
import urllib.parse
import webbrowser
from datetime import datetime, timedelta

import requests

import config

WINDOWS = os.name == "nt"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_DADOS = os.path.join(RAIZ, "data")
os.makedirs(PASTA_DADOS, exist_ok=True)

HABILIDADES = {}   # nome -> função
ESQUEMAS = []      # formato de "tools" do Ollama
LEMBRETES = None   # preenchido pelo main.py


def maximizar_depois(segundos=8):
    """Espera a janela que acabou de ser aberta aparecer na frente e maximiza ela.
    Roda em segundo plano, pra Marin não ficar esperando. Nunca mexe na janela da própria Marin."""
    if not WINDOWS or not getattr(config, "MAXIMIZAR_JANELAS", True):
        return
    import threading
    import time
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32

    def _pid(hwnd):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def _janelas():
        lista = set()

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _cada(hwnd, _):
            if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) and not user32.GetWindow(hwnd, 4):
                lista.add(hwnd)        # GetWindow(...,4) = tem "dono": é caixinha/popup, não janela principal
            return True

        user32.EnumWindows(_cada, 0)
        return lista

    antes = _janelas()
    frente_antes = user32.GetForegroundWindow()
    eu = os.getpid()

    def _vigiar():
        fim = time.time() + segundos
        while time.time() < fim:
            time.sleep(0.25)
            novas = [h for h in _janelas() - antes if _pid(h) != eu]
            frente = user32.GetForegroundWindow()
            alvo = None
            if frente and frente != frente_antes and _pid(frente) != eu and user32.IsWindowVisible(frente):
                alvo = frente
            elif novas:
                alvo = novas[0]
            if alvo:
                time.sleep(0.3)                     # deixa a janela terminar de abrir
                user32.ShowWindow(alvo, 3)           # 3 = maximizar
                user32.SetForegroundWindow(alvo)
                return

    threading.Thread(target=_vigiar, daemon=True).start()


def abrir_url(url):
    """Abre um link no navegador padrão. Tenta 3 jeitos, porque o webbrowser do Python
    às vezes falha calado no Windows (principalmente fora da thread principal)."""
    maximizar_depois()
    if WINDOWS:
        try:
            os.startfile(url)
            return True
        except OSError as e:
            print(f"[abrir_url] os.startfile falhou: {e}")
        try:
            subprocess.Popen(["rundll32", "url.dll,FileProtocolHandler", url])
            return True
        except Exception as e:
            print(f"[abrir_url] rundll32 falhou: {e}")
    try:
        return bool(webbrowser.open(url))
    except Exception as e:
        print(f"[abrir_url] webbrowser falhou: {e}")
        return False


def habilidade(descricao, parametros=None, obrigatorios=None):
    def deco(fn):
        HABILIDADES[fn.__name__] = fn
        ESQUEMAS.append({
            "type": "function",
            "function": {
                "name": fn.__name__,
                "description": descricao,
                "parameters": {
                    "type": "object",
                    "properties": parametros or {},
                    "required": obrigatorios or [],
                },
            },
        })
        return fn
    return deco


def executar(nome, argumentos):
    fn = HABILIDADES.get(nome)
    if not fn:
        return f"Habilidade '{nome}' não existe."
    try:
        argumentos = {k: v for k, v in (argumentos or {}).items() if v not in (None, "")}
        return str(fn(**argumentos))
    except TypeError as e:
        return f"Parâmetros inválidos para {nome}: {e}"
    except Exception as e:
        return f"Erro ao executar {nome}: {e}"


def _txt(tipo="string", desc="", enum=None):
    d = {"type": tipo, "description": desc}
    if enum:
        d["enum"] = enum
    return d


# =====================================================================
# Controle do PC
# =====================================================================
PROGRAMAS = {
    "chrome": "chrome", "google chrome": "chrome", "navegador": "chrome",
    "edge": "msedge", "microsoft edge": "msedge",
    "vscode": "code", "vs code": "code", "visual studio code": "code",
    "calculadora": "calc", "bloco de notas": "notepad", "notepad": "notepad",
    "explorador": "explorer", "explorador de arquivos": "explorer", "arquivos": "explorer",
    "terminal": "wt", "prompt de comando": "cmd", "cmd": "cmd", "powershell": "powershell",
    "gerenciador de tarefas": "taskmgr", "paint": "mspaint",
    "configurações": "ms-settings:", "configuracoes": "ms-settings:",
    "spotify": "spotify:", "whatsapp": "whatsapp:", "steam": "steam:",
}

PROCESSOS = {
    "chrome": "chrome.exe", "google chrome": "chrome.exe", "navegador": "chrome.exe",
    "edge": "msedge.exe", "vscode": "Code.exe", "vs code": "Code.exe",
    "calculadora": "CalculatorApp.exe", "bloco de notas": "notepad.exe",
    "spotify": "Spotify.exe", "discord": "Discord.exe", "pycharm": "pycharm64.exe",
    "whatsapp": "WhatsApp.exe", "steam": "steam.exe", "paint": "mspaint.exe",
}


def _atalhos_menu_iniciar():
    pastas = [
        os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.path.expanduser("~"), "Desktop"),
    ]
    atalhos = {}
    for p in pastas:
        for arq in glob.glob(os.path.join(p, "**", "*.lnk"), recursive=True) + glob.glob(os.path.join(p, "*.url")):
            nome = os.path.splitext(os.path.basename(arq))[0].lower()
            if "uninstall" in nome or "desinstalar" in nome:
                continue
            atalhos.setdefault(nome, arq)
    return atalhos


def _sem_acento(t):
    import unicodedata
    t = unicodedata.normalize("NFD", str(t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


_APPS_CACHE = None


def _apps_instalados(atualizar=False):
    """Todos os apps do Menu Iniciar, INCLUSIVE os da Microsoft Store (que não têm atalho .lnk).
    Devolve {nome_normalizado: (nome_bonito, como_abrir)}."""
    global _APPS_CACHE
    if _APPS_CACHE is not None and not atualizar:
        return _APPS_CACHE
    apps = {}
    # 1) Get-StartApps: lista tudo que aparece no Menu Iniciar (programas comuns + apps da Store)
    if WINDOWS:
        try:
            cmd = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
                   "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress")
            r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True,
                               timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            import json
            dados = json.loads(r.stdout.decode("utf-8", "ignore") or "[]")
            if isinstance(dados, dict):
                dados = [dados]
            for a in dados:
                nome, appid = a.get("Name") or "", a.get("AppID") or ""
                n = _sem_acento(nome)
                if not n or not appid or "uninstall" in n or "desinstalar" in n:
                    continue
                apps.setdefault(n, (nome, "shell:AppsFolder\\" + appid))
        except Exception as e:
            print(f"[abrir_programa] Get-StartApps falhou: {e}")
    # 2) atalhos .lnk/.url (Menu Iniciar e Área de Trabalho), caso o de cima falhe
    for nome, arq in _atalhos_menu_iniciar().items():
        apps.setdefault(_sem_acento(nome), (os.path.splitext(os.path.basename(arq))[0], arq))
    _APPS_CACHE = apps
    return apps


def _achar_app(chave, apps):
    if chave in apps:
        return chave
    if len(chave) < 3:
        return None
    # nome do app contém o que foi falado (ex.: "esound" -> "esound music")
    contem = [n for n in apps if chave in n]
    if contem:
        return sorted(contem, key=len)[0]
    # o que foi falado contém o nome do app (ex.: "o spotify music" -> "spotify")
    dentro = [n for n in apps if len(n) >= 4 and n in chave]
    if dentro:
        return sorted(dentro, key=len)[-1]
    # junta as palavras (o reconhecimento de voz às vezes separa: "e sound" -> "esound")
    junto = chave.replace(" ", "")
    for n in apps:
        if junto and junto in n.replace(" ", ""):
            return n
    perto = difflib.get_close_matches(chave, list(apps), n=1, cutoff=0.6)
    return perto[0] if perto else None


@habilidade("Abre qualquer programa/aplicativo instalado no computador, inclusive apps da Microsoft Store "
            "(ex.: chrome, spotify, eSound, vscode, pycharm, discord, calculadora, whatsapp).",
            {"nome": _txt(desc="Nome do programa")}, ["nome"])
def abrir_programa(nome):
    maximizar_depois(12)
    chave = _sem_acento(re.sub(r"^(o |a )?(app|aplicativo|programa)( do| da| de)? ", "", nome.lower().strip()))
    if chave in PROGRAMAS:
        alvo = PROGRAMAS[chave]
        try:
            if alvo.endswith(":"):
                os.startfile(alvo)
            else:
                subprocess.Popen(f'start "" {alvo}', shell=True)
            return f"Abrindo {nome}."
        except Exception:
            pass
    for atualizar in (False, True):   # se não achar, recarrega a lista (app instalado agora há pouco)
        apps = _apps_instalados(atualizar)
        achado = _achar_app(chave, apps)
        if achado:
            bonito, alvo = apps[achado]
            try:
                if alvo.startswith("shell:AppsFolder"):
                    subprocess.Popen(["explorer.exe", alvo])
                else:
                    os.startfile(alvo)
                return f"Abrindo {bonito}."
            except Exception as e:
                return f"Achei o {bonito}, mas não consegui abrir ({e})."
    return f"Não encontrei o programa '{nome}' no computador."


@habilidade("Fecha um programa que está aberto.", {"nome": _txt(desc="Nome do programa")}, ["nome"])
def fechar_programa(nome):
    chave = nome.lower().strip()
    exe = PROCESSOS.get(chave, chave.replace(" ", "") + ".exe")
    r = subprocess.run(["taskkill", "/IM", exe, "/F"], capture_output=True, text=True)
    if r.returncode == 0:
        return f"{nome} fechado."
    return f"Não consegui fechar {nome} (processo {exe} não encontrado)."


SITES = {
    "youtube": "https://www.youtube.com", "gmail": "https://mail.google.com", "email": "https://mail.google.com",
    "whatsapp": "https://web.whatsapp.com", "whatsapp web": "https://web.whatsapp.com",
    "instagram": "https://www.instagram.com", "github": "https://github.com", "linkedin": "https://www.linkedin.com",
    "google": "https://www.google.com", "netflix": "https://www.netflix.com", "drive": "https://drive.google.com",
    "workana": "https://www.workana.com", "99freelas": "https://www.99freelas.com.br", "claude": "https://claude.ai",
    "ava": "https://ava2.uniasselvi.com.br", "uniasselvi": "https://ava2.uniasselvi.com.br",
}


@habilidade("Abre um site no navegador (ex.: youtube, gmail, github, instagram, ou um endereço como exemplo.com).",
            {"site": _txt(desc="Nome ou endereço do site")}, ["site"])
def abrir_site(site):
    s = site.lower().strip()
    url = SITES.get(s)
    if not url:
        if s.startswith("http"):
            url = s
        elif "." in s:
            url = "https://" + s
        else:
            url = f"https://www.{s.replace(' ', '')}.com"
    if not abrir_url(url):
        return f"Não consegui abrir {url}."
    return f"Abrindo {url}."


VK = {"mudo": 0xAD, "diminuir": 0xAE, "aumentar": 0xAF,
      "proxima": 0xB0, "anterior": 0xB1, "parar": 0xB2, "pausar": 0xB3}


def _tecla(vk, vezes=1):
    import ctypes
    for _ in range(vezes):
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)


@habilidade("Controla o volume do computador.",
            {"acao": _txt(desc="O que fazer", enum=["aumentar", "diminuir", "mudo", "definir"]),
             "quantidade": _txt("integer", "Para aumentar/diminuir: pontos percentuais (padrão 10). Para definir: o volume final de 0 a 100.")},
            ["acao"])
def volume(acao, quantidade=None):
    if acao == "mudo":
        _tecla(VK["mudo"])
        return "Som mutado/desmutado."
    if acao == "definir":
        alvo = max(0, min(100, int(quantidade if quantidade is not None else 50)))
        _tecla(VK["diminuir"], 50)          # zera (cada toque = 2%)
        _tecla(VK["aumentar"], round(alvo / 2))
        return f"Volume em {alvo}%."
    passos = max(1, round(int(quantidade or 10) / 2))
    _tecla(VK[acao], passos)
    return f"Volume {'aumentado' if acao == 'aumentar' else 'diminuído'}."


@habilidade("Desliga, reinicia, bloqueia ou suspende o computador, ou cancela um desligamento agendado. "
            "SEMPRE pergunte antes de desligar ou reiniciar e só chame com confirmado=true depois que o usuário disser sim.",
            {"acao": _txt(desc="Ação", enum=["desligar", "reiniciar", "bloquear", "suspender", "cancelar"]),
             "confirmado": _txt("boolean", "O usuário confirmou? Obrigatório para desligar/reiniciar.")},
            ["acao"])
def energia(acao, confirmado=False):
    if acao in ("desligar", "reiniciar") and not confirmado:
        return "Precisa confirmar com o usuário antes."
    if acao == "desligar":
        subprocess.run(["shutdown", "/s", "/t", "30"])
        return "O computador vai desligar em 30 segundos. Diga 'cancela o desligamento' para impedir."
    if acao == "reiniciar":
        subprocess.run(["shutdown", "/r", "/t", "30"])
        return "O computador vai reiniciar em 30 segundos."
    if acao == "cancelar":
        subprocess.run(["shutdown", "/a"])
        return "Desligamento cancelado."
    if acao == "bloquear":
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return "Computador bloqueado."
    if acao == "suspender":
        subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
        return "Suspendendo."
    return "Ação desconhecida."


@habilidade("Tira um print (captura) da tela e salva na pasta Imagens\\Marin.")
def print_tela():
    from PIL import ImageGrab
    pasta = os.path.join(os.path.expanduser("~"), "Pictures", "Marin")
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, datetime.now().strftime("print_%Y-%m-%d_%H-%M-%S.png"))
    ImageGrab.grab(all_screens=True).save(caminho)
    return f"Print salvo em {caminho}."


# =====================================================================
# Hora, clima e pesquisa
# =====================================================================
DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def periodo_do_dia(h):
    if h < 5:
        return "madrugada"
    if h < 12:
        return "manhã"
    if h < 18:
        return "tarde"
    return "noite"


def hora_falada(agora=None):
    """Ex.: 'meia-noite e 12, de madrugada' / 'duas e meia da tarde' / '7 em ponto da manhã'."""
    agora = agora or datetime.now()
    h, m = agora.hour, agora.minute
    if h == 0:
        base = "meia-noite"
    elif h == 12:
        base = "meio-dia"
    else:
        h12 = h % 12
        base = {1: "uma", 2: "duas"}.get(h12, str(h12))
    if m == 0:
        minutos = " em ponto"
    elif m == 30:
        minutos = " e meia"
    else:
        minutos = f" e {m}"
    per = periodo_do_dia(h)
    ligacao = ", de" if h in (0, 12) else " da"
    return f"{base}{minutos}{ligacao} {per}"


def agora_e(agora=None):
    """'é meia-noite e 10, de madrugada' ou 'são 3 e 45 da tarde' (concordância certinha)."""
    txt = hora_falada(agora)
    verbo = "é" if txt.split()[0] in ("meia-noite", "meio-dia", "uma") else "são"
    return f"{verbo} {txt}"


def data_extenso(agora=None):
    agora = agora or datetime.now()
    return f"{DIAS[agora.weekday()]}, {agora.day} de {MESES[agora.month - 1]} de {agora.year}"


def data_hora_extenso(agora=None):
    agora = agora or datetime.now()
    return f"{data_extenso(agora)}, {agora.strftime('%H:%M')} ({hora_falada(agora)})"


@habilidade("Diz a data e a hora atuais.")
def data_hora():
    return f"Hoje é {data_extenso()} e agora {agora_e()} ({datetime.now().strftime('%H:%M')})."


CLIMA_COD = {
    0: "céu limpo", 1: "predominantemente limpo", 2: "parcialmente nublado", 3: "nublado",
    45: "neblina", 48: "neblina", 51: "garoa fraca", 53: "garoa", 55: "garoa forte",
    61: "chuva fraca", 63: "chuva", 65: "chuva forte", 80: "pancadas de chuva fracas",
    81: "pancadas de chuva", 82: "pancadas de chuva fortes", 95: "trovoadas",
    96: "trovoadas com granizo", 99: "trovoadas com granizo",
}


@habilidade("Mostra o clima, a temperatura, se vai chover, se está calor ou frio, e a previsão de hoje e amanhã de uma cidade. "
            "SEMPRE use esta ferramenta para qualquer pergunta sobre tempo, temperatura, calor, frio ou chuva.",
            {"cidade": _txt(desc=f"Cidade (padrão: {config.CIDADE_PADRAO})")})
def clima(cidade=None):
    cidade = cidade or config.CIDADE_PADRAO
    g = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                     params={"name": cidade, "count": 1, "language": "pt"}, timeout=10).json()
    if not g.get("results"):
        return f"Não encontrei a cidade {cidade}."
    loc = g["results"][0]
    p = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": loc["latitude"], "longitude": loc["longitude"], "timezone": "auto", "forecast_days": 2,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
    }, timeout=10).json()
    c, d = p["current"], p["daily"]
    desc = CLIMA_COD.get(c["weather_code"], "tempo variado")
    return (f"{loc['name']}: agora {round(c['temperature_2m'])}°C (sensação {round(c['apparent_temperature'])}°C), "
            f"{desc}, umidade {c['relative_humidity_2m']}%, vento {round(c['wind_speed_10m'])} km/h. "
            f"Hoje: máx {round(d['temperature_2m_max'][0])}°C, mín {round(d['temperature_2m_min'][0])}°C, "
            f"chance de chuva {d['precipitation_probability_max'][0]}%. "
            f"Amanhã: máx {round(d['temperature_2m_max'][1])}°C, mín {round(d['temperature_2m_min'][1])}°C, "
            f"{CLIMA_COD.get(d['weather_code'][1], 'tempo variado')}, chance de chuva {d['precipitation_probability_max'][1]}%.")


@habilidade("Pesquisa na internet e traz um resumo dos resultados. Use para notícias, fatos atuais, preços, "
            "resultados de jogos ou qualquer coisa que você não saiba com certeza.",
            {"consulta": _txt(desc="O que pesquisar"),
             "abrir_no_navegador": _txt("boolean", "Também abrir a pesquisa no navegador")},
            ["consulta"])
def pesquisar_web(consulta, abrir_no_navegador=False):
    if abrir_no_navegador:
        abrir_url("https://www.google.com/search?q=" + urllib.parse.quote(consulta))
    try:
        from ddgs import DDGS
        resultados = list(DDGS().text(consulta, region="br-pt", max_results=5))
    except Exception as e:
        return f"Não consegui pesquisar agora ({e.__class__.__name__})."
    if not resultados:
        return "Nenhum resultado encontrado."
    linhas = [f"- {r.get('title', '')}: {r.get('body', '')}" for r in resultados]
    return "Resultados da pesquisa:\n" + "\n".join(linhas)


# =====================================================================
# Música e YouTube
# =====================================================================
def buscar_video_youtube(busca):
    html = requests.get("https://www.youtube.com/results", params={"search_query": busca, "hl": "pt-BR"},
                        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "pt-BR"}, timeout=10).text
    ids = re.findall(r'"videoId":"([\w-]{11})"', html)
    return ids[0] if ids else None


def _janela_youtube():
    """Procura uma janela do navegador que esteja mostrando o YouTube. Devolve o identificador ou None."""
    if not WINDOWS:
        return None
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    achadas = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _cada(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                titulo = buf.value
                if "YouTube" in titulo and ("Chrome" in titulo or "Edge" in titulo or "Brave" in titulo
                                            or "Firefox" in titulo):   # só navegador (o app do YouTube não tem barra de endereço)
                    achadas.append(hwnd)
        return True

    user32.EnumWindows(_cada, 0)
    return achadas[0] if achadas else None


def _abrir_na_aba_do_youtube(url):
    """Reaproveita a aba do YouTube que já está aberta (em vez de abrir uma aba nova).
    Só digita o endereço se tiver certeza de que a janela certa está na frente."""
    hwnd = _janela_youtube()
    if not hwnd:
        return False
    try:
        import ctypes
        import time
        import keyboard
        user32 = ctypes.windll.user32
        user32.ShowWindow(hwnd, 3)                     # maximiza (também tira do minimizado)
        user32.keybd_event(0x12, 0, 0, 0)              # truque do Alt: o Windows deixa trazer a janela pra frente
        user32.keybd_event(0x12, 0, 2, 0)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.35)
        if user32.GetForegroundWindow() != hwnd:
            return False                               # não conseguiu focar: melhor abrir aba nova do que digitar no lugar errado
        keyboard.send("ctrl+l")
        time.sleep(0.15)
        keyboard.write(url, delay=0)
        time.sleep(0.05)
        keyboard.send("enter")
        return True
    except Exception as e:
        print(f"[youtube] não consegui reaproveitar a aba: {e}")
        return False


def _abrir_youtube(url):
    return _abrir_na_aba_do_youtube(url) or abrir_url(url)


@habilidade("Toca uma música, clipe ou vídeo no YouTube.",
            {"busca": _txt(desc="Nome da música/artista/vídeo")}, ["busca"])
def tocar_youtube(busca):
    try:
        vid = buscar_video_youtube(busca)
    except Exception as e:
        print(f"[youtube] busca falhou: {e}")
        vid = None
    if not vid:
        if not _abrir_youtube("https://www.youtube.com/results?search_query=" + urllib.parse.quote(busca)):
            return "Não consegui abrir o navegador."
        return f"Abri a pesquisa de '{busca}' no YouTube."
    if not _abrir_youtube(f"https://www.youtube.com/watch?v={vid}"):
        return "Não consegui abrir o navegador."
    return f"Tocando '{busca}' no YouTube."


@habilidade("Controla a música/vídeo que está tocando (Spotify, YouTube etc.): pausar/continuar, próxima, anterior.",
            {"acao": _txt(desc="Ação", enum=["pausar", "proxima", "anterior", "parar"])}, ["acao"])
def controlar_midia(acao):
    _tecla(VK[acao])
    return {"pausar": "Pausado/retomado.", "proxima": "Próxima faixa.",
            "anterior": "Faixa anterior.", "parar": "Mídia parada."}[acao]


# =====================================================================
# Lembretes e anotações
# =====================================================================
@habilidade("Cria um lembrete. Informe em_minutos (daqui a quanto tempo) OU horario (HH:MM). "
            "Se o horário já passou hoje, fica para amanhã.",
            {"mensagem": _txt(desc="Do que lembrar"),
             "em_minutos": _txt("number", "Daqui a quantos minutos"),
             "horario": _txt(desc="Horário no formato HH:MM"),
             "data": _txt(desc="Data AAAA-MM-DD (opcional, junto com horario)")},
            ["mensagem"])
def criar_lembrete(mensagem, em_minutos=None, horario=None, data=None):
    agora = datetime.now()
    if em_minutos is not None:
        quando = agora + timedelta(minutes=float(em_minutos))
    elif horario:
        nums = re.findall(r"\d+", horario)
        if not nums:
            return "Não entendi o horário."
        h, m = int(nums[0]), int(nums[1]) if len(nums) > 1 else 0
        base = datetime.strptime(data, "%Y-%m-%d") if data else agora
        quando = base.replace(hour=h, minute=m, second=0, microsecond=0)
        if quando <= agora and not data:
            quando += timedelta(days=1)
    else:
        return "Preciso saber quando: em quantos minutos ou em que horário."
    LEMBRETES.adicionar(mensagem, quando)
    return f"Lembrete criado para {data_hora_extenso(quando)}: {mensagem}"


@habilidade("Lista os lembretes pendentes.")
def listar_lembretes():
    itens = LEMBRETES.listar()
    if not itens:
        return "Nenhum lembrete pendente."
    return "\n".join(f"{i + 1}. {data_hora_extenso(datetime.fromisoformat(x['quando']))} — {x['mensagem']}"
                     for i, x in enumerate(itens))


@habilidade("Cancela um lembrete pelo número da lista (veja listar_lembretes).",
            {"numero": _txt("integer", "Número do lembrete (começa em 1)")}, ["numero"])
def cancelar_lembrete(numero):
    item = LEMBRETES.remover(int(numero) - 1)
    return f"Lembrete cancelado: {item['mensagem']}" if item else "Esse lembrete não existe."


ANOTACOES = os.path.join(PASTA_DADOS, "anotacoes.md")


@habilidade("Anota algo no bloco de anotações da Marin.", {"texto": _txt(desc="O que anotar")}, ["texto"])
def anotar(texto):
    with open(ANOTACOES, "a", encoding="utf-8") as f:
        f.write(f"- [{datetime.now().strftime('%d/%m/%Y %H:%M')}] {texto}\n")
    return "Anotado."


@habilidade("Lê as últimas anotações.", {"quantidade": _txt("integer", "Quantas (padrão 5)")})
def ler_anotacoes(quantidade=5):
    if not os.path.exists(ANOTACOES):
        return "Ainda não há anotações."
    with open(ANOTACOES, encoding="utf-8") as f:
        linhas = [l.strip() for l in f if l.strip()]
    return "\n".join(linhas[-int(quantidade):]) or "Ainda não há anotações."


@habilidade("Abre o arquivo de anotações no Bloco de Notas.")
def abrir_anotacoes():
    if not os.path.exists(ANOTACOES):
        open(ANOTACOES, "w", encoding="utf-8").close()
    maximizar_depois()
    os.startfile(ANOTACOES)
    return "Abrindo suas anotações."


# =====================================================================
# Prospecção de clientes no WhatsApp (fica em core/prospeccao.py)
# =====================================================================
from core import prospeccao  # noqa: E402,F401  (registra as habilidades de prospecção)
from core import gmail  # noqa: E402,F401  (registra a habilidade de conferir o e-mail)

# carrega a lista de apps instalados em segundo plano, para o "abre ..." ser instantâneo
if WINDOWS:
    import threading  # noqa: E402
    threading.Thread(target=_apps_instalados, daemon=True).start()
