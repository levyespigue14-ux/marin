"""Prospecção de clientes pelo WhatsApp (semi-automática e segura).

A Marin escolhe o próximo cliente da planilha, escreve uma mensagem personalizada e abre o
WhatsApp com a conversa e o texto prontos. VOCÊ confere e aperta Enviar. Depois diz
"Marin, próximo" e ela marca o cliente como abordado e já abre o seguinte.

Ela NUNCA envia sozinha: mandar mensagens automáticas em massa faz o WhatsApp banir o número.

Planilha: data/leads.csv (abre no Excel). Colunas:
    nome; nicho; cidade; whatsapp; instagram; avaliacao; status; abordado_em; followup_em; observacao
Status possíveis: novo, abordado, followup, respondeu, fechado, sem_interesse, pulado
"""
import csv
import json
import os
import random
import re
import unicodedata
import urllib.parse
from datetime import date, timedelta

import config
from core.ferramentas import PASTA_DADOS, _txt, abrir_url, habilidade, maximizar_depois

PLANILHA = os.path.join(PASTA_DADOS, "leads.csv")
COLUNAS = ["nome", "nicho", "cidade", "whatsapp", "instagram", "avaliacao",
           "status", "abordado_em", "followup_em", "observacao"]
STATUS_VALIDOS = ["novo", "abordado", "followup", "respondeu", "fechado", "sem_interesse", "pulado"]

# Limite diário de mensagens (abordagens + follow-ups) para o WhatsApp não restringir a conta.
CONTADOR = os.path.join(PASTA_DADOS, "envios_hoje.json")


def _limite():
    return int(getattr(config, "LIMITE_DIARIO", 25))


def _enviados_hoje():
    hoje = date.today().isoformat()
    try:
        with open(CONTADOR, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("data") == hoje:
            return int(d.get("qtd", 0))
    except Exception:
        pass
    # primeira vez no dia: começa pelos abordados de hoje que já estão na planilha
    return sum(1 for l in ler_leads() if l["abordado_em"] == hoje)


def _somar_envio():
    qtd = _enviados_hoje() + 1
    try:
        with open(CONTADOR, "w", encoding="utf-8") as f:
            json.dump({"data": date.today().isoformat(), "qtd": qtd}, f)
    except Exception as e:
        print(f"[prospeccao] não consegui salvar o contador: {e}")
    return qtd


def _restante_hoje():
    return max(0, _limite() - _enviados_hoje())


def _aviso_limite():
    return (f"Hoje já foram {_enviados_hoje()} mensagens, o limite é {_limite()} por dia "
            "pra o WhatsApp não restringir a conta. Amanhã a gente continua!")


# Sessão em andamento (só na memória)
SESSAO = {"ativa": False, "tipo": None, "fila": [], "atual": None, "canal": "whatsapp"}


# =====================================================================
# Planilha
# =====================================================================
def _norm(t):
    t = unicodedata.normalize("NFD", str(t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


def _criar_planilha():
    with open(PLANILHA, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, delimiter=";").writerow(COLUNAS)


def ler_leads():
    if not os.path.exists(PLANILHA):
        _criar_planilha()
    with open(PLANILHA, encoding="utf-8-sig", newline="") as f:
        amostra = f.read(2048)
        f.seek(0)
        sep = ";" if amostra.count(";") >= amostra.count(",") else ","
        linhas = list(csv.DictReader(f, delimiter=sep))
    for l in linhas:
        for c in COLUNAS:
            l[c] = (l.get(c) or "").strip()
        if not l["status"]:
            l["status"] = "novo"
    return linhas


def salvar_leads(linhas):
    extras = []
    for l in linhas:
        extras += [k for k in l if k and k not in COLUNAS and k not in extras]
    try:
        with open(PLANILHA, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUNAS + extras, delimiter=";", extrasaction="ignore")
            w.writeheader()
            w.writerows(linhas)
    except PermissionError:
        raise RuntimeError("A planilha de leads está aberta no Excel. Fecha ela e tenta de novo.")


def _chave(lead):
    return (_norm(lead["nome"]), re.sub(r"\D", "", lead["whatsapp"]))


def _atualizar(lead, **campos):
    linhas = ler_leads()
    for l in linhas:
        if _chave(l) == _chave(lead):
            l.update(campos)
            break
    salvar_leads(linhas)


def _telefone(numero):
    d = re.sub(r"\D", "", numero or "")
    if len(d) in (10, 11):
        d = "55" + d
    return d if len(d) >= 12 else ""


# =====================================================================
# Mensagens (edite à vontade)
# =====================================================================
PLURAL = {
    "sushi": "restaurantes japoneses", "hamburgueria": "hamburguerias", "academia": "academias",
    "clinica": "clínicas", "advocacia": "escritórios de advocacia", "imobiliaria": "imobiliárias",
    "fretes": "empresas de frete", "energia solar": "empresas de energia solar", "pizzaria": "pizzarias", "acai": "açaiterias",
}

# O que o site-modelo de cada nicho tem (só coisas que o modelo realmente faz). Vai no meio da mensagem.
DESCRICAO_SITE = {
    "sushi": [
        "Cardápio completo com fotos, e o cliente monta o pedido (tira ingrediente, escolhe adicionais, deixa observação)",
        "O pedido chega pronto no WhatsApp de vocês, já com endereço e taxa de entrega por bairro",
        "Pagamento por Pix no próprio site, com QR Code já no valor do pedido",
        "Dá pra agendar pedido mesmo com a loja fechada",
        "Visual de cinema com animação 3D, igualzinho no celular e no PC",
        "Sem pagar comissão de aplicativo em cada pedido",
    ],
    "padrao": [
        "Site rápido e bonito, igualzinho no celular e no PC",
        "Botão que leva o cliente direto pro WhatsApp de vocês",
        "Todas as informações, fotos e serviços num lugar só",
        "Ajuda vocês a serem encontrados no Google",
    ],
}

ABORDAGENS = [
    "Oi, tudo bem? Gostaria de falar com o responsável/dono da {nome}, é sobre o site de vocês (não é pedido). {gancho}\n\n"
    "Eu crio sites para {nicho_plural} e montei esse modelo pra mostrar: {link}\n\n"
    "*O que o site faz:*\n{recursos}\n\n"
    "Monto tudo com a identidade da {nome}. Quer que eu te mostre como ficaria?",

    "Olá! Tudo certo por aí? Gostaria de falar com o responsável/dono, é sobre o site de vocês (não é pedido). {gancho}\n\n"
    "Dá uma olhada nesse site que fiz para {nicho_plural}: {link}\n\n"
    "*Nele:*\n{recursos}\n\n"
    "Posso montar um assim pra {nome}?",
]

# Mensagem aprovada pelo Levy para cada nicho (curta, sem falar de valores).
# Se o nicho estiver aqui, ela é usada no lugar das ABORDAGENS genéricas.
ABORDAGENS_NICHO = {
    "sushi": (
        "Olá! Tudo bem? 🍣 Gostaria de falar com o responsável/dono, é sobre o site do restaurante (não é pedido).\n\n"
        "{elogio} Fiquei pensando que um sushi desse nível merece um site à altura, "
        "então montei este modelo pra te mostrar:\n"
        "👉 {link}\n\n"
        "*O que ele faz:*\n"
        "✅ Mostra seu cardápio completo, com fotos e preços\n"
        "✅ O cliente monta o pedido no site e ele chega pronto no seu WhatsApp, *sem comissão de aplicativo*\n"
        "✅ Visual animado e profissional, perfeito no celular\n\n"
        "Imagina isso com o nome, o logo e as fotos de vocês. Dá uma olhada e me diz: o que achou? 😊"
    ),
    # Aprovada pelo Levy em 18/10/2026: mais explicativa e convincente, curta e sem preço.
    "acai": (
        "Oi, tudo bem? Falo com o responsável pela {nome}? É sobre o site da loja, não é pedido 😊\n\n"
        "Fiz este modelo de site pra açaiteria:\n"
        "👉 {link}\n\n"
        "Nele o cliente monta o açaí do jeito dele, vê o preço na hora e o pedido chega prontinho no WhatsApp de vocês.\n\n"
        "✅ Sem pagar comissão por pedido, como no iFood\n"
        "✅ Sem erro de pedido nem vai e volta de mensagem\n"
        "✅ Vocês mudam preços e produtos pelo próprio celular\n\n"
        "É o que faz o cliente pedir direto com vocês, e não pelo aplicativo. Teriam interesse em ter um assim?"
    ),
    # Aprovada pelo Levy em 19/10/2026: curta, sem preço e sem oferecer prévia.
    "energia solar": (
        "Oi, tudo bem? Falo com o responsável pela {nome}? É sobre o site da empresa, não é orçamento 😊\n\n"
        "Fiz este modelo de site pra empresa de energia solar:\n"
        "👉 {link}\n\n"
        "Nele o cliente coloca o valor da conta de luz e já vê quanto vai economizar e em quanto tempo o sistema se paga. "
        "Daí ele chama vocês no WhatsApp já querendo orçamento.\n\n"
        "✅ Simulador de economia\n"
        "✅ Obras feitas, avaliações e opções de financiamento\n"
        "✅ Perfeito no celular e no PC\n\n"
        "É o que faz o cliente fechar com vocês, e não com o concorrente. Teriam interesse em ter um assim?"
    ),
}


def _elogio(lead):
    """Elogio só com base na nota real do Google (nada inventado)."""
    try:
        nota = float(lead["avaliacao"].replace(",", "."))
    except ValueError:
        nota = None
    if nota and nota >= 4.5:
        return "Vi as avaliações de vocês e o pessoal elogia muito!"
    if not nota:
        return "Vi a loja de vocês aqui no Google!"
    return "Vi o trabalho de vocês e gostei muito!"

FOLLOWUPS = [
    "Oi, tudo bem? Passando só pra saber se chegou a ver o modelo de site que te mandei: {link}\n\n"
    "Se quiser, monto uma prévia com a cara da {nome}, sem compromisso.",

    "Olá! Conseguiu dar uma olhada no site que te enviei? {link}\n\nSe tiver alguma dúvida sobre valor ou prazo, me chama.",
]

# Follow-up próprio por nicho (aprovado pelo Levy em 08/10/2026). Sem falar de preço.
FOLLOWUPS_NICHO = {
    # Aprovado pelo Levy em 13/10/2026: sem oferecer prévia grátis e sem falar de preço.
    "acai": (
        "Oi, tudo bem? Passando só pra saber se chegou a ver o modelo de site que te mandei:\n"
        "{link}\n\n"
        "Ficou alguma dúvida sobre como ele funciona?"
    ),
    "energia solar": (
        "Oi, tudo bem? Passando só pra saber se chegou a ver o modelo de site que te mandei:\n"
        "{link}\n\n"
        "Ficou alguma dúvida sobre como ele funciona?"
    ),
    "sushi": (
        "Oi, tudo bem? 🍣 Passando só pra saber se chegou a ver o modelo de site que te mandei: {link}\n\n"
        "Se quiser, monto uma prévia com o nome e o cardápio da {nome}, sem compromisso. Posso?"
    ),
}


def _gancho(lead):
    """Frase de abertura usando só dados reais da planilha (nada inventado)."""
    try:
        nota = float(lead["avaliacao"].replace(",", "."))
    except ValueError:
        nota = None
    if nota and nota >= 4.5:
        return f"Vi que vocês têm ótimas avaliações no Google ({str(nota).replace('.', ',')} estrelas), mas ainda não têm um site próprio."
    if lead["instagram"]:
        return "Vi o Instagram de vocês e percebi que ainda não têm um site próprio."
    return "Vi que vocês ainda não têm um site próprio."


def _link(nicho):
    links = getattr(config, "LINKS_MODELO", {})
    n = _norm(nicho)
    for chave, url in links.items():
        if _norm(chave) in n or n in _norm(chave):
            return url
    return links.get("padrao", "")


def _recursos(nicho):
    n = _norm(nicho)
    itens = next((v for k, v in DESCRICAO_SITE.items() if k != "padrao" and k in n), DESCRICAO_SITE["padrao"])
    return "\n".join(f"✅ {i}" for i in itens)


def montar_mensagem(lead, tipo="abordagem"):
    link = _link(lead["nicho"])
    nicho_n = _norm(lead["nicho"])
    plural = next((v for k, v in PLURAL.items() if k in nicho_n), lead["nicho"] or "empresas")
    especifica = next((v for k, v in ABORDAGENS_NICHO.items() if k in nicho_n), None)
    fup = next((v for k, v in FOLLOWUPS_NICHO.items() if k in nicho_n), None)
    if tipo != "followup" and especifica:
        modelo = especifica
    elif tipo == "followup" and fup:
        modelo = fup
    else:
        modelo = random.choice(FOLLOWUPS if tipo == "followup" else ABORDAGENS)
    texto = modelo.format(nome=lead["nome"], gancho=_gancho(lead), elogio=_elogio(lead), nicho_plural=plural,
                          link=link or "[SEM LINK DE MODELO]", eu=config.COMO_ME_CHAMAR,
                          recursos=_recursos(lead["nicho"]))
    return texto, bool(link)


def copiar(texto):
    """Coloca o texto na área de transferência do Windows (para colar com Ctrl+V)."""
    try:
        import subprocess
        subprocess.run(["clip"], input=texto.encode("utf-16le"), check=True)
        return True
    except Exception as e:
        print(f"[prospeccao] não consegui copiar: {e}")
        return False


def abrir_whatsapp(telefone, texto):
    """Abre a conversa no WhatsApp do Windows e deixa a mensagem copiada.
    (O link com o texto junto ficava grande demais para o Windows e caía no navegador.)"""
    copiou = copiar(texto)
    if getattr(config, "WHATSAPP_MODO", "app") == "app":
        try:
            maximizar_depois()
            os.startfile(f"whatsapp://send?phone={telefone}")
            return "colar" if copiou else "app"
        except Exception as e:
            print(f"[prospeccao] whatsapp:// falhou: {e}")
    q = urllib.parse.quote(texto)
    return "web" if abrir_url(f"https://web.whatsapp.com/send?phone={telefone}&text={q}") else ""


# =====================================================================
# Fluxo da sessão
# =====================================================================
def _abrir_atual():
    lead = SESSAO["atual"]
    if SESSAO.get("canal") == "instagram":
        resto = len(SESSAO["fila"])
        falta = ("Esse é o último!" if resto == 0 else "Depois dele só falta mais um." if resto == 1
                 else f"Faltam {resto}.")
        return abrir_instagram_cliente() + " " + falta
    tel = _telefone(lead["whatsapp"])
    if not tel:
        _atualizar(lead, status="pulado", observacao=(lead["observacao"] + " | número inválido").strip(" |"))
        return f"O número de {lead['nome']} está inválido, pulei. " + _avancar()
    texto, tem_link = montar_mensagem(lead, SESSAO["tipo"])
    modo = abrir_whatsapp(tel, texto)
    if not modo:
        return (f"Não consegui abrir o WhatsApp de {lead['nome']}. Diz 'próximo' para tentar o seguinte.")
    resto = len(SESSAO["fila"])
    if modo == "colar":
        aviso_extra = " A mensagem já está copiada: clica na caixa de texto do WhatsApp, aperta Ctrl+V e envia."
    else:
        aviso_extra = ""
    aviso = "" if tem_link else (" Atenção: não tenho link de modelo para esse nicho, "
                                 "troca o [SEM LINK DE MODELO] antes de enviar e coloca o link no config.py.")
    if resto == 0:
        falta = "Esse é o último, depois dele a gente termina!"
    elif resto == 1:
        falta = "Depois dele só falta mais um."
    else:
        falta = f"Faltam {resto}."
    dica_insta = (" Se não tiver WhatsApp, diz 'instagram' que eu abro o Direct dele."
                  if _usuario_instagram(lead["instagram"]) else "")
    return (f"Abri o WhatsApp de {lead['nome']}.{aviso_extra} Depois diz 'próximo'.{dica_insta} {falta}{aviso}")


def _avancar():
    if not SESSAO["fila"]:
        SESSAO.update(ativa=False, atual=None)
        fim = random.choice([
            "Concluímos com sucesso! Todos os clientes da lista foram abordados.",
            "Prontinho, concluímos com sucesso! Mandamos mensagem pra todo mundo da lista.",
            "Missão cumprida! Concluímos com sucesso, agora é esperar as respostas.",
        ])
        return fim + " " + resumo_prospeccao()
    SESSAO["atual"] = SESSAO["fila"].pop(0)
    return _abrir_atual()


@habilidade("Prospectar/abordar clientes (leads) no WhatsApp ou no Instagram, um por vez.",
            {"nicho": _txt(desc="ex.: sushi"), "cidade": _txt(), "quantidade": _txt("integer", "padrão 10"),
             "canal": _txt(desc="whatsapp (padrão) ou instagram", enum=["whatsapp", "instagram"])})
def iniciar_prospeccao(nicho=None, cidade=None, quantidade=10, canal="whatsapp"):
    canal = "instagram" if _norm(canal or "").startswith("insta") else "whatsapp"
    leads = [l for l in ler_leads() if l["status"] == "novo"]
    if canal == "instagram":
        leads = [l for l in leads if _usuario_instagram(l["instagram"])]
    else:
        # telefone fixo não tem WhatsApp: esses ficam para a rodada do Instagram
        leads = [l for l in leads if not _eh_fixo(l["whatsapp"])]
    if nicho:
        leads = [l for l in leads if _norm(nicho) in _norm(l["nicho"])]
    if cidade:
        leads = [l for l in leads if _norm(cidade) in _norm(l["cidade"])]
    if not leads:
        return "Não achei nenhum cliente novo com esse filtro na planilha de leads."
    restante = _restante_hoje()
    if restante <= 0:
        return _aviso_limite()
    pedido = max(1, int(quantidade))
    fila = leads[:min(pedido, restante)]
    SESSAO.update(ativa=True, tipo="abordagem", fila=fila[1:], atual=fila[0], canal=canal)
    onde = " pelo Instagram" if canal == "instagram" else ""
    corte = (f" Você pediu {pedido}, mas só dá mais {restante} hoje por causa do limite diário."
             if pedido > restante and len(leads) > restante else "")
    return f"Bora! Vou abordar {len(fila)} clientes{onde}.{corte} " + _abrir_atual()


@habilidade("Follow-up (reabordagem) dos leads abordados que não responderam. Se disser o nicho "
            "(ex.: sushi), reaborda TODOS os abordados desse nicho, mesmo os que ainda não venceram.",
            {"nicho": _txt(desc="opcional, ex.: sushi ou açaí")})
def fazer_followups(nicho=None):
    hoje = date.today().isoformat()
    if nicho:
        leads = [l for l in ler_leads()
                 if l["status"] == "abordado" and _norm(nicho) in _norm(l["nicho"])]
    else:
        leads = [l for l in ler_leads()
                 if l["status"] == "abordado" and l["followup_em"] and l["followup_em"] <= hoje]
    leads = [l for l in leads if not _eh_fixo(l["whatsapp"])]
    if not leads:
        return "Nenhum follow-up pendente" + (f" de {nicho}." if nicho else " pra hoje.")
    restante = _restante_hoje()
    if restante <= 0:
        return _aviso_limite()
    total = len(leads)
    leads = leads[:restante]
    SESSAO.update(ativa=True, tipo="followup", fila=leads[1:], atual=leads[0], canal="whatsapp")
    resto = f" Os outros {total - len(leads)} ficam pra amanhã por causa do limite diário." if total > len(leads) else ""
    return f"Tem {total} follow-ups. Vou fazer {len(leads)} agora.{resto} " + _abrir_atual()


@habilidade("Prospecção: próximo cliente (o atual foi enviado).")
def proximo_cliente():
    if not SESSAO["ativa"] or not SESSAO["atual"]:
        return "Não tem prospecção em andamento. Diga, por exemplo: 'aborda 10 clientes de sushi'."
    lead, hoje = SESSAO["atual"], date.today()
    if SESSAO["tipo"] == "followup":
        _atualizar(lead, status="followup", followup_em=(hoje + timedelta(days=4)).isoformat())
    else:
        _atualizar(lead, status="abordado", abordado_em=hoje.isoformat(),
                   followup_em=(hoje + timedelta(days=getattr(config, "DIAS_FOLLOWUP", 3))).isoformat())
    if SESSAO.get("canal") != "instagram":
        enviados = _somar_envio()
        if enviados >= _limite():
            restantes = len(SESSAO["fila"])
            SESSAO.update(ativa=False, fila=[], atual=None)
            sobra = f" Ficaram {restantes} clientes para amanhã." if restantes else ""
            return f"Chegamos no limite de {_limite()} mensagens de hoje, vou parar por aqui.{sobra}"
    return _avancar()


def _eh_fixo(numero):
    """True se o número é de telefone fixo (sem o 9 do celular)."""
    d = re.sub(r"\D", "", numero or "")
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    return len(d) == 10 and d[2] in "2345"


def _usuario_instagram(valor):
    """Tira o @ ou o link e devolve só o usuário do Instagram."""
    v = (valor or "").strip()
    m = re.search(r"instagram\.com/([A-Za-z0-9_.]+)", v)
    if m:
        v = m.group(1)
    return v.lstrip("@").strip("/ ")


@habilidade("Prospecção: abre o Direct do Instagram do cliente atual (ou do cliente pelo nome) com a mensagem copiada.",
            {"nome": _txt(desc="opcional: nome do cliente; se vazio, usa o cliente atual")})
def abrir_instagram_cliente(nome=None):
    if nome:
        alvo = _norm(nome)
        achados = [l for l in ler_leads() if alvo in _norm(l["nome"])]
        if not achados:
            return f"Não achei '{nome}' na planilha de leads."
        lead = achados[0]
    elif SESSAO["atual"]:
        lead = SESSAO["atual"]
        # relê da planilha (o Instagram pode ter sido adicionado depois que a sessão começou)
        lead = next((l for l in ler_leads() if _chave(l) == _chave(lead)), lead)
    else:
        return "Não tem cliente aberto agora. Diz o nome dele, por exemplo: 'abre o Instagram do Hayumi'."
    usuario = _usuario_instagram(lead["instagram"])
    if not usuario:
        return f"{lead['nome']} não tem Instagram na planilha."
    texto, _ = montar_mensagem(lead, SESSAO["tipo"] or "abordagem")
    copiar(texto)
    if not abrir_url(f"https://ig.me/m/{usuario}"):
        return f"Não consegui abrir o Instagram de {lead['nome']}."
    return (f"Abri o Direct do Instagram de {lead['nome']}, arroba {usuario}. A mensagem já está copiada: "
            f"clica na caixa de mensagem, aperta Ctrl+V e envia. Depois diz 'próximo'.")


@habilidade("Prospecção: pula o cliente atual.")
def pular_cliente():
    if not SESSAO["ativa"] or not SESSAO["atual"]:
        return "Não tem prospecção em andamento."
    _atualizar(SESSAO["atual"], status="pulado")
    return _avancar()


@habilidade("Para a prospecção.")
def parar_prospeccao():
    if not SESSAO["ativa"]:
        return "Não tem prospecção em andamento."
    restantes = len(SESSAO["fila"]) + 1
    SESSAO.update(ativa=False, fila=[], atual=None)
    return f"Prospecção pausada. Ficaram {restantes} clientes para a próxima vez."


@habilidade("Muda o status de um lead (respondeu, fechado, sem interesse...).",
            {"nome": _txt(), "status": _txt(enum=STATUS_VALIDOS), "observacao": _txt()},
            ["nome", "status"])
def atualizar_lead(nome, status, observacao=None):
    linhas = ler_leads()
    alvo = _norm(nome)
    achados = [l for l in linhas if alvo in _norm(l["nome"])]
    if not achados:
        return f"Não achei '{nome}' na planilha de leads."
    if len(achados) > 1:
        return "Achei mais de um: " + ", ".join(l["nome"] for l in achados[:5]) + ". Fala o nome completo."
    l = achados[0]
    l["status"] = status
    if observacao:
        l["observacao"] = (l["observacao"] + " | " + observacao).strip(" |")
    salvar_leads(linhas)
    return f"{l['nome']} agora está como {status.replace('_', ' ')}."


@habilidade("Resumo da prospecção (leads novos, abordados, fechados).")
def resumo_prospeccao():
    linhas = ler_leads()
    if not linhas:
        return "A planilha de leads está vazia."
    cont = {s: 0 for s in STATUS_VALIDOS}
    for l in linhas:
        cont[l["status"]] = cont.get(l["status"], 0) + 1
    hoje = date.today().isoformat()
    pend = sum(1 for l in linhas if l["status"] == "abordado" and l["followup_em"] and l["followup_em"] <= hoje)
    return (f"Você tem {len(linhas)} leads: {cont['novo']} novos, {cont['abordado'] + cont['followup']} abordados, "
            f"{cont['respondeu']} responderam, {cont['fechado']} fechados e {cont['sem_interesse']} sem interesse. "
            f"Follow-ups para hoje: {pend}. Mensagens hoje: {_enviados_hoje()} de {_limite()}.")


@habilidade("Abre a planilha de leads no Excel.")
def abrir_planilha_leads():
    if not os.path.exists(PLANILHA):
        _criar_planilha()
    maximizar_depois(12)
    os.startfile(PLANILHA)
    return "Abrindo a planilha de leads."
