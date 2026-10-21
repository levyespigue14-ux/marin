"""Atalhos rápidos: pedidos comuns resolvidos na hora, sem passar pela IA (resposta instantânea).

Se nada aqui reconhecer o pedido, a Marin usa o cérebro (Ollama) normalmente.
"""
import random
import re
import unicodedata

from core import ferramentas as f

import config

OK = ["Prontinho!", "Feito!", "Deixa comigo!", "Pronto!", "Prontinho, {t}!", "Feito, {t}!", "Às suas ordens, {t}!"]


def _norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", t)).strip()


def _ok():
    return random.choice(OK).format(t=config.tratamento())


def tentar(texto: str):
    """Devolve a resposta falada se reconheceu o pedido, ou None."""
    n = _norm(texto)
    n = re.sub(r"^(ei |oi |ok )?(marin|marim|marina)\s+", "", n)   # "Marin, abre..." digitado
    n = re.sub(r"^(por favor|pfv|ei|ok|oi)\s+", "", n)
    n = re.sub(r"\s+(por favor|pfv|pra mim|para mim)$", "", n)

    # --- começar prospecção (direto, sem a IA, para não "fingir" que abriu) ---
    canal = "whatsapp"
    m_insta = re.search(r" (pelo|no|via|por) (instagram|insta|direct)$", n)
    if m_insta and re.match(r"(aborda|abordar|aborde|prospecta|prospectar|comeca|manda mensagem)", n):
        canal = "instagram"
        n = n[:m_insta.start()]
    m = re.fullmatch(r"(aborda|abordar|aborde|prospecta|prospectar|comeca a abordar|comeca a prospeccao|manda mensagem para|manda mensagem pros?)"
                     r"(?: (?:os|as|mais))?(?: (\d+))?(?: (?:clientes?|leads?|restaurantes?))?(?: (?:de|do|da|dos))? ?(.*?)"
                     r"(?: (?:em|no|na) (.+))?", n)
    if m:
        from core import prospeccao as p0
        qtd = int(m.group(2)) if m.group(2) else 10
        nicho = (m.group(3) or "").strip() or None
        if nicho in ("os", "clientes", "leads"):
            nicho = None
        return p0.iniciar_prospeccao(nicho=nicho, cidade=(m.group(4) or "").strip() or None, quantidade=qtd,
                                     canal=canal)

    # --- follow-up / reabordagem (direto, sem a IA, para não "fingir" que fez) ---
    # aceita a frase em qualquer posição (o ouvido às vezes erra o começo: "oz os follow-ups de sushi")
    m = (re.search(r"(?:follow ?ups?|folow ?ups?|reabordagens?)(?: (?:de|do|da|dos|das|pros|pras|para os|para as))?(?: (.+))?$", n)
         or re.search(r"(?:reaborda|reabordar|reaborde|reabordo)(?: (?:os|as))?(?: (?:clientes?|leads?))?"
                      r"(?: (?:de|do|da|dos|das))?(?: (.+))?$", n))
    if m:
        from core import prospeccao as pf
        nicho = (m.group(1) or "").strip()
        if nicho in ("", "hoje", "de hoje", "pra hoje", "todos", "todo mundo", "clientes", "leads"):
            nicho = None
        elif len(nicho) > 3 and nicho.endswith("s"):
            nicho = nicho[:-1]          # "sushis" -> "sushi", "acais" -> "acai"
        return pf.fazer_followups(nicho=nicho)

    # --- prospecção em andamento (vem antes da mídia: aqui "próximo" é o próximo cliente) ---
    from core import prospeccao as p
    if p.SESSAO["ativa"]:
        if re.fullmatch(r"(proximo|proxima|proximo cliente|proximo lead|manda o proximo|enviei|mandei|enviado|foi|ja foi|ja mandei|ja enviei)", n):
            return p.proximo_cliente()
        if re.fullmatch(r"(pula|pular|pula esse|pula essa|pula esse cliente|pula cliente|esse nao|essa nao)", n):
            return p.pular_cliente()
        if re.fullmatch(r"(para|parar|para a prospeccao|chega|encerra|encerrar|termina|terminar)", n):
            return p.parar_prospeccao()
        if re.fullmatch(r"(abre |abrir |abra |manda |mandar |vai |manda pelo |vai pelo |pelo )?(o |no |pelo )?(instagram|insta|direct)( dele| dela| do cliente)?", n):
            return p.abrir_instagram_cliente()

    m = re.fullmatch(r"(abre|abrir|abra|manda mensagem no|manda no) (o )?(instagram|insta|direct) (do|da|de) (.+)", n)
    if m:
        return p.abrir_instagram_cliente(nome=m.group(5))

    # --- hora e data ---
    if re.fullmatch(r"(que horas? (sao|e)( agora)?|me (diz|fala) (a|as) horas?|horas?|que hora e essa)", n):
        return f"Agora {f.agora_e()}."
    if re.fullmatch(r"(que dia (e|eh) hoje|qual (e )?a data( de hoje)?|hoje e que dia|que data e hoje)", n):
        return f"Hoje é {f.data_extenso()}."
    if re.fullmatch(r"(data|dia|hoje|que dia)", n):
        return f"Hoje é {f.data_extenso()}."

    # --- clima (atalhos curtos: "temp", "clima", "tempo", "temp recife", "vai chover") ---
    m = re.fullmatch(r"(temp|temperatura|clima|tempo|previsao|calor|frio|chuva|vai chover)"
                     r"(?: (?:hoje|agora|de hoje))?(?: (?:em|no|na|de|do|da) (.+)| (.+))?", n)
    if not m:
        m = re.fullmatch(r"(como (esta|ta) (o clima|o tempo|a temperatura)|qual (e )?a temperatura|ta (calor|frio)|vai chover hoje)"
                         r"(?: (?:agora|hoje))?(?: (?:em|no|na) (.+))?()", n)
    if m:
        cidade = (m.groups()[-2] or m.groups()[-1] or "").strip() or None
        if cidade in ("hoje", "agora", "aqui"):
            cidade = None
        r = f.clima(_trecho_original(texto, cidade) if cidade else None)
        return r.split(" Amanhã:")[0]     # versão curta pra falar (agora + hoje)

    # --- print e lembretes ---
    if re.fullmatch(r"(print|printa|tira (um )?print|captura( de tela)?|screenshot)", n):
        return f"{_ok()} " + f.print_tela()
    if re.fullmatch(r"(lembretes|meus lembretes|lista (os )?lembretes|quais (sao )?(os )?(meus )?lembretes)", n):
        return f.listar_lembretes()
    if re.fullmatch(r"(notas|anotacoes|minhas notas|le (as )?(minhas )?(notas|anotacoes))", n):
        return f.ler_anotacoes()
    m = re.fullmatch(r"(anota|anotar|nota) (.+)", n)
    if m:
        f.anotar(_trecho_original(texto, m.group(2)))
        return f"{_ok()} Anotado."

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
    m = re.fullmatch(r"(?:(?:eu )?quero (?:ouvir|escutar)|(?:me )?deixa (?:eu )?(?:ouvir|escutar)|vamos ouvir|bora ouvir|"
                     r"toca|tocar|toque|toca ai|tocar ai|coloca|colocar|coloque|coloca ai|poe|por|ponha|poe ai|"
                     r"bota|botar|bote|bota ai|solta|ouvir|escutar|play)"
                     r" (?:pra mim |para mim |ai )?(a musica |o video |o clipe |a |o |uma musica d[aeo] |musica d[aeo] |um som d[aeo] )?(.+?)"
                     r"(?: no youtube| pra tocar| pra mim| ai)?", n)
    if m and re.fullmatch(r"(?:a |uma )?(?:sua|tua|a sua)? ?(?:musica|cancao|som)? ?(?:favorita|preferida|predileta)"
                          r"|(?:a )?(?:musica )?(?:da )?abertura(?: do| de)?(?: seu| teu| o seu| sua)?(?: anime)?(?: seu| dela)?"
                          r"|(?:a musica )?(?:do|de) (?:seu|teu) anime", m.group(2)):
        escolha = getattr(config, "MUSICA_FAVORITA", "") or "Sansan Days spira spica"
        r = f.tocar_youtube(escolha)
        if r.startswith("Não"):
            return r
        return f"A minha favorita, {config.tratamento()}! A abertura do meu anime! Tocando {escolha.split(' spira')[0]}!"
    if m and re.fullmatch(r"(?:uma |alguma |qualquer )?(?:musica|cancao|coisa|som)(?: qualquer| aleatoria| boa| legal| ai)?"
                          r"|algo|alguma coisa|qualquer coisa|qualquer uma|o que voce quiser|o que quiser|"
                          r"(?:(?:alguma |uma |a )?(?:musica |cancao )?que voce (?:mais )?gosta)|musica|som|um som", m.group(2)):
        escolha = random.choice(getattr(config, "MUSICAS_FAVORITAS", None) or ["Sansan Days spira spica"])
        r = f.tocar_youtube(escolha)
        if r.startswith("Não"):
            return r
        return f"Essa eu amo, {config.tratamento()}! Tocando {escolha.split(' spira')[0]}!"
    if m and m.group(2) not in ("musica", "uma musica", "algo", "alguma coisa", "som", "um som"):
        busca = _trecho_original(texto, m.group(2))
        r = f.tocar_youtube(busca)
        return r if r.startswith("Não") else f"Tocando {busca}!"

    # --- e-mail ---
    if re.fullmatch(r"(confere|conferir|ve|verifica|checa|olha)( o| os| meu| meus)? (e ?mails?|gmail|caixa de entrada)( novos?)?|chegou (algum )?(e ?mail|resposta)( novo| nova)?", n):
        from core import gmail
        return gmail.verificar_email()

    # --- leads (atalhos curtos) ---
    if re.fullmatch(r"(leads|meus leads|resumo|resumo (dos )?leads|resumo da prospeccao|como (estao|ta) os leads)", n):
        return p.resumo_prospeccao()
    if re.fullmatch(r"(planilha|planilha leads|excel)", n):
        try:
            return f"{_ok()} " + p.abrir_planilha_leads()
        except Exception as e:
            return f"Não consegui abrir a planilha ({e})."
    m = re.fullmatch(r"(respondeu|fechou|fechado|sem interesse|nao quis) (o |a )?(.+)", n)
    if m:
        status = {"respondeu": "respondeu", "fechou": "fechado", "fechado": "fechado"}.get(m.group(1), "sem_interesse")
        return p.atualizar_lead(_trecho_original(texto, m.group(3)), status)

    # --- planilha de leads e anotações ---
    if re.fullmatch(r"(abre|abrir|abra|mostra|me mostra|ver) (a |as )?(minha |minhas )?planilhas?( de| dos| das)?( leads?| clientes?| prospeccao)?", n):
        try:
            return f"{_ok()} " + p.abrir_planilha_leads()
        except Exception as e:
            return f"Não consegui abrir a planilha ({e})."
    if re.fullmatch(r"(abre|abrir|abra|mostra) (as |minhas )?(minhas )?anotac(ao|oes)", n):
        return f"{_ok()} " + f.abrir_anotacoes()

    # --- abrir site ou qualquer programa instalado ---
    m = re.fullmatch(r"(abre|abrir|abra|entra no|entra na|entrar no|inicia|iniciar|executa) (o |a |no |na )?(.+)", n)
    if m:
        alvo = re.sub(r"^(app|aplicativo|programa|site)( do| da| de)? ", "", m.group(3).strip())
        if alvo in f.SITES:
            r = f.abrir_site(alvo)
            return r if r.startswith("Não") else f"{_ok()} Abrindo o {alvo}."
        r = f.abrir_programa(alvo)
        if r.startswith("Abrindo"):
            return f"{_ok()} {r}"
        if r.startswith("Achei"):
            return r
        # não achou programa com esse nome: deixa a IA decidir (pode ser um site, por exemplo)
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
