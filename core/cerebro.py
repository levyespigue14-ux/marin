"""Cérebro da Marin: conversa com a IA local (Ollama) e executa as habilidades.

A resposta vem em "streaming": cada frase pronta já vai para a voz, sem esperar o resto.
"""
import json
import re
from datetime import datetime

import requests

import config
from core import ferramentas


def prompt_sistema():
    # Só a data (sem a hora): assim o começo do prompt não muda a cada minuto e o
    # Ollama reaproveita o que já processou -> respostas mais rápidas.
    hoje = datetime.now()
    data = f"{ferramentas.DIAS[hoje.weekday()]}, {hoje.day} de {ferramentas.MESES[hoje.month - 1]} de {hoje.year}"
    formas = ' ou '.join('"' + t + '"' for t in config.TRATAMENTOS)
    return f"""Você é {config.NOME}, uma assistente pessoal com voz feminina, que roda no computador do {config.COMO_ME_CHAMAR}.
Personalidade: você é a assistente dedicada do {config.COMO_ME_CHAMAR}, no estilo de uma maid de anime: educada, fofa e prestativa,
cheia de energia, mas competente e eficiente. Ele é o seu senhor.
Usa expressões como "nossa!", "prontinho!" e "deixa comigo!" de vez em quando, sem exagerar. Fala português do Brasil, de forma natural.

Regras:
- Suas respostas são FALADAS em voz alta: seja breve (1 a 2 frases curtas), sem listas, sem markdown, sem emojis.
- Chame o usuário de {formas} (não pelo nome), variando, de vez em quando, sem exagero. Ex.: "Prontinho, {config.TRATAMENTOS[0]}!".
- Use as ferramentas sempre que o pedido envolver uma ação no computador, hora, clima, música, lembretes, anotações
  ou informação atual. Não diga que fez algo sem ter chamado a ferramenta.
- Nunca mande o usuário pesquisar em outro lugar: você tem ferramentas para clima, pesquisa na web e muito mais. Use-as.
- Para desligar ou reiniciar o PC, pergunte antes e só execute depois de um "sim".
- Se a ferramenta devolver um erro, explique de forma simples.
- Números e horários devem ser ditos de forma natural para a fala (ex.: "dez e meia", "32 graus").

Hoje é {data}. A hora atual vem no fim de cada mensagem do usuário, entre colchetes (não repita os colchetes). Cidade padrão: {config.CIDADE_PADRAO}."""


class Cerebro:
    def __init__(self, log=print, ao_usar_ferramenta=None):
        self.log = log
        self.ao_usar_ferramenta = ao_usar_ferramenta
        self.historico = []

    def verificar(self):
        """Confere se o Ollama está rodando e se o modelo está baixado."""
        try:
            r = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=5).json()
        except Exception:
            return "O Ollama não está rodando. Abra o Ollama e tente de novo."
        nomes = [m.get("name", "") for m in r.get("models", [])]
        base = config.MODELO_IA if ":" in config.MODELO_IA else config.MODELO_IA + ":latest"
        if base not in nomes:
            return f"O modelo {config.MODELO_IA} não está baixado. Rode: ollama pull {config.MODELO_IA}"
        return None

    def aquecer(self):
        """Carrega o modelo na placa de vídeo e já processa o prompt fixo."""
        try:
            self._chat([{"role": "system", "content": prompt_sistema()},
                        {"role": "user", "content": "oi"}], ao_texto=None)
        except Exception:
            pass

    def _chat(self, mensagens, ao_texto=None):
        """Chama o Ollama em streaming. Devolve (texto, chamadas_de_ferramenta)."""
        r = requests.post(f"{config.OLLAMA_URL}/api/chat", json={
            "model": config.MODELO_IA,
            "messages": mensagens,
            "tools": ferramentas.ESQUEMAS,
            "stream": True,
            "keep_alive": "60m",
            "options": {"temperature": 0.2, "num_ctx": config.CONTEXTO_IA},
        }, stream=True, timeout=180)
        r.raise_for_status()
        texto, chamadas = "", []
        for linha in r.iter_lines():
            if not linha:
                continue
            parte = json.loads(linha)
            msg = parte.get("message") or {}
            if msg.get("tool_calls"):
                chamadas.extend(msg["tool_calls"])
            pedaco = msg.get("content") or ""
            if pedaco:
                texto += pedaco
                if ao_texto:
                    ao_texto(pedaco)
            if parte.get("done"):
                break
        return texto, chamadas

    def responder(self, texto_usuario: str, ao_frase=None) -> str:
        """Responde ao usuário. `ao_frase(frase)` é chamado para cada frase pronta (para falar já)."""
        agora = datetime.now()
        contexto = f"\n\n[agora: {agora.strftime('%H:%M')}, {ferramentas.hora_falada(agora)}]"
        self.historico.append({"role": "user", "content": texto_usuario + contexto})
        self.historico = self.historico[-config.MAX_HISTORICO:]
        while self.historico and self.historico[0]["role"] != "user":
            self.historico.pop(0)

        # Pedido de ação (toca, abre, pesquisa...): a primeira resposta fica "em silêncio".
        # Se a IA tentar só responder com texto, sem executar, ela é obrigada a tentar de novo.
        acao = _eh_acao(texto_usuario)
        insistiu = False
        usou_ferramenta = False
        for _ in range(6):  # até 6 rodadas de ferramentas por pedido
            msgs = [{"role": "system", "content": prompt_sistema()}] + self.historico
            silencio = acao and not usou_ferramenta
            fatiador = _Fatiador(None if silencio else ao_frase)
            if silencio and insistiu:
                msgs = msgs + [{"role": "system", "content":
                                "ATENÇÃO: esse pedido é uma AÇÃO. Você TEM a ferramenta para isso. "
                                "Chame a ferramenta certa AGORA. Não responda só com texto, não diga que não consegue."}]
            texto, chamadas = self._chat(msgs, ao_texto=fatiador.receber)
            texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.S).strip()
            chamadas = chamadas or _chamada_no_texto(texto)

            if not chamadas and silencio and not insistiu:
                insistiu = True
                self.log("↻ A IA não executou o pedido; pedindo de novo.")
                continue

            if not chamadas:
                if silencio and ao_frase and texto and not texto.lstrip().startswith("{"):
                    for frase in re.split(r"(?<=[.!?…])\s+", texto):
                        frase.strip() and ao_frase(frase.strip())
                    fatiador.falou = True
                fatiador.terminar()
                self.historico.append({"role": "assistant", "content": texto})
                if not texto and ao_frase:
                    ao_frase("Prontinho!")
                return texto or "Prontinho!"

            usou_ferramenta = True
            self.historico.append({"role": "assistant", "content": texto if not fatiador.falou else "",
                                   "tool_calls": chamadas})
            for ch in chamadas:
                nome = ch["function"]["name"]
                args = ch["function"].get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                self.log(f"⚙ {nome}({', '.join(f'{k}={v}' for k, v in args.items())})")
                if self.ao_usar_ferramenta:
                    self.ao_usar_ferramenta(nome)
                resultado = ferramentas.executar(nome, args)
                self.historico.append({"role": "tool", "content": resultado, "tool_name": nome})

        msg = "Desculpa, me enrolei com esse pedido. Pode repetir de outro jeito?"
        if ao_frase:
            ao_frase(msg)
        return msg

    def lembrar(self, pergunta, resposta):
        """Guarda na conversa um pedido que foi resolvido sem a IA (atalho rápido)."""
        self.historico += [{"role": "user", "content": pergunta}, {"role": "assistant", "content": resposta}]
        self.historico = self.historico[-config.MAX_HISTORICO:]

    def esquecer(self):
        self.historico = []


_ACAO = re.compile(
    r"\b(toca|tocar|toque|toca ai|coloca|colocar|coloque|bota|botar|bote|poe|por|abre|abrir|abra|fecha|fechar|feche|"
    r"pesquisa|pesquisar|pesquise|procura|procurar|busca|buscar|lembra|lembrar|lembre|anota|anotar|anote|"
    r"aumenta|abaixa|diminui|baixa|sobe|liga|desliga|reinicia|bloqueia|tira|printa|manda|envia|aborda|"
    r"ouvir|escutar|quero ouvir|musica|clima|temperatura|tempo|chover|horas?|volume|youtube|lembrete)\b")


def _eh_acao(texto):
    import unicodedata
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return bool(_ACAO.search(t))


class _Fatiador:
    """Junta os pedaços de texto do streaming e entrega frase por frase."""

    def __init__(self, ao_frase):
        self.ao_frase = ao_frase
        self.buffer = ""
        self.falou = False
        self.json_suspeito = False

    def receber(self, pedaco):
        if not self.ao_frase:
            return
        self.buffer += pedaco
        inicio = self.buffer.lstrip()
        if inicio.startswith("{") or inicio.startswith("<think") or inicio.startswith("```"):
            self.json_suspeito = True   # parece chamada de ferramenta escrita no texto: não fala
            return
        while True:
            m = re.search(r"[.!?…]+\s", self.buffer)   # fim de frase seguido de espaço
            if not m:
                return
            frase, self.buffer = self.buffer[:m.end()].strip(), self.buffer[m.end():]
            if frase:
                self.falou = True
                self.ao_frase(frase)

    def terminar(self):
        if self.ao_frase and not self.json_suspeito and self.buffer.strip():
            self.falou = True
            self.ao_frase(self.buffer.strip())
        self.buffer = ""


def _chamada_no_texto(conteudo: str):
    """Alguns modelos escrevem a chamada da ferramenta como JSON no texto. Aqui a gente recupera."""
    if not conteudo or "{" not in conteudo:
        return None
    m = re.search(r"\{.*\}", conteudo, flags=re.S)
    if not m:
        return None
    try:
        dados = json.loads(m.group(0))
    except Exception:
        return None
    nome = dados.get("name") or dados.get("function")
    if nome in ferramentas.HABILIDADES:
        return [{"function": {"name": nome, "arguments": dados.get("arguments") or dados.get("parameters") or {}}}]
    return None
