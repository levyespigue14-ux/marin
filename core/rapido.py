"""Atalhos rápidos: pedidos comuns resolvidos na hora, sem passar pela IA (resposta instantânea).

Se nada aqui reconhecer o pedido, a Marin usa o cérebro (Ollama) normalmente.
"""
import random
import re
import unicodedata

from core import ferramentas as f

OK = ["Prontinho!", "Feito!", "Deixa comigo!", "Pronto!"]


def _norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", t)).strip()


def _ok():
    return random.choice(OK)


def tentar(texto: str):
    """Devolve a resposta falada se reconheceu o pedido, ou None."""
    n = _norm(texto)
    n = re.sub(r"^(por favor|pfv|ei|ok|oi)\s+", "", n)
    n = re.sub(r"\s+(por favor|pfv|pra mim|para mim)$", "", n)

    # --- hora e data ---
    if re.fullmatch(r"(que horas? (sao|e)( agora)?|me (diz|fala) (a|as) horas?|horas?|que hora e essa)", n):
        return f"Agora {f.agora_e()}."
    if re.fullmatch(r"(que dia (e|eh) hoje|qual (e )?a data( de hoje)?|hoje e que dia|que data e hoje)", n):
        return f"Hoje é {f.data_extenso()}."

    # --- mídia ---
    if re.fullmatch(r"(pausa|pausar|pause|para a musica|pausa a musica|continua|continuar|despausa|play|solta a musica)", n):
        f.controlar_midia("pausar")
        return _ok()
    if re.fullmatch(r"(proxima|proxima musica|proxima faixa|pula|pula essa|passa|passa a musica|pula a musica)", n):
        f.controlar_midia("proxima")
        return _ok()
    if re.fullmatch(r"(volta|volta a musica|musica anterior|anterior|volta uma)", n):
        f.controlar_midia("anterior")
        return _ok()

    # --- volume ---
    m = re.fullmatch(r"(coloca |deixa |poe )?(o )?volume (em|no|pra|para|a) (\d{1,3})( por cento)?", n)
    if m:
        f.volume("definir", int(m.group(4)))
        return f"Volume em {min(100, int(m.group(4)))}."
    if re.fullmatch(r"(aumenta|sobe|aumentar)( o)?( volume| o som)?|mais alto", n):
        f.volume("aumentar", 10)
        return _ok()
    if re.fullmatch(r"(abaixa|diminui|baixa|diminuir|abaixar)( o)?( volume| o som)?|mais baixo", n):
        f.volume("diminuir", 10)
        return _ok()
    if re.fullmatch(r"(muta|mutar|silencio|tira o som|desmuta)", n):
        f.volume("mudo")
        return _ok()

    # --- YouTube ---
    m = re.fullmatch(r"(toca|tocar|coloca|poe|bota) (a musica |o video |o clipe )?(.+?)( no youtube)?", n)
    if m and m.group(3) not in ("musica", "uma musica", "algo", "alguma coisa"):
        busca = _trecho_original(texto, m.group(3))
        r = f.tocar_youtube(busca)
        return r if r.startswith("Não") else f"Tocando {busca}!"

    # --- abrir site ou programa conhecido ---
    m = re.fullmatch(r"(abre|abrir|abra|entra no|entra na|entrar no) (o |a |no |na )?(.+)", n)
    if m:
        alvo = m.group(3).strip()
        if alvo in f.SITES:
            r = f.abrir_site(alvo)
            return r if r.startswith("Não") else f"{_ok()} Abrindo o {alvo}."
        if alvo in f.PROGRAMAS:
            f.abrir_programa(alvo)
            return f"{_ok()} Abrindo {alvo}."
    return None


def _trecho_original(texto, trecho_norm):
    """Recupera o trecho com acentos/maiúsculas originais (para buscar e falar certinho)."""
    palavras = texto.split()
    alvo = trecho_norm.split()
    for i in range(len(palavras)):
        janela = palavras[i:i + len(alvo)]
        if [_norm(p) for p in janela] == alvo:
            return " ".join(janela).strip(" ,.!?")
    return trecho_norm
