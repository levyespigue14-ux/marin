"""Vigia do Gmail: a cada poucos minutos confere se chegou e-mail importante
(Workana, vagas, clientes) e a Marin avisa em voz alta.

Só LÊ os e-mails (não apaga, não responde, não marca como lido).
Precisa de uma "senha de app" do Google no arquivo .env (veja o README / instruções da Marin):
    GMAIL_USUARIO=seuemail@gmail.com
    GMAIL_SENHA_APP=xxxxxxxxxxxxxxxx
"""
import email
import imaplib
import json
import os
import re
import threading
import time
from email.header import decode_header, make_header
from email.utils import parseaddr

import config
from core.ferramentas import PASTA_DADOS, habilidade

VISTOS = os.path.join(PASTA_DADOS, "gmail_vistos.json")


def _cfg(nome, padrao):
    return getattr(config, nome, padrao)


def _decodificar(valor):
    try:
        return str(make_header(decode_header(valor or ""))).strip()
    except Exception:
        return (valor or "").strip()


def _origem(remetente, assunto):
    """Diz de onde veio o e-mail (Workana, Gupy...) se for importante. Senão, devolve None."""
    nome, endereco = parseaddr(remetente)
    texto = f"{nome} {endereco}".lower()
    for chave, rotulo in _cfg("GMAIL_REMETENTES", {}).items():
        if chave.lower() in texto:
            return rotulo
    a = assunto.lower()
    if any(p in a for p in _cfg("GMAIL_PALAVRAS", [])):
        return _decodificar(nome) or endereco
    return None


class VigiaGmail:
    def __init__(self, ao_chegar, log=print):
        self.ao_chegar = ao_chegar      # função(origem, assunto)
        self.log = log
        self.usuario = os.getenv("GMAIL_USUARIO", "")
        self.senha = os.getenv("GMAIL_SENHA_APP", "").replace(" ", "")
        self.vistos = self._carregar_vistos()

    @property
    def configurado(self):
        return bool(self.usuario and self.senha)

    def _carregar_vistos(self):
        try:
            with open(VISTOS, encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return None   # primeira vez: não avisa os e-mails antigos

    def _salvar_vistos(self):
        with open(VISTOS, "w", encoding="utf-8") as f:
            json.dump(sorted(self.vistos)[-500:], f)

    def buscar_novos(self):
        """Devolve [(origem, assunto)] dos e-mails importantes que ainda não foram avisados."""
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        try:
            imap.login(self.usuario, self.senha)
            imap.select("INBOX", readonly=True)          # readonly: não marca nada como lido
            _, dados = imap.uid("search", None, "UNSEEN")
            uids = dados[0].split()[-30:] if dados and dados[0] else []
            primeira_vez = self.vistos is None
            if primeira_vez:
                self.vistos = set()
            novos = []
            for uid in uids:
                uid_txt = uid.decode()
                if uid_txt in self.vistos:
                    continue
                self.vistos.add(uid_txt)
                if primeira_vez:
                    continue
                _, msg = imap.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
                if not msg or not msg[0]:
                    continue
                cab = email.message_from_bytes(msg[0][1])
                assunto = _decodificar(cab.get("Subject"))
                origem = _origem(_decodificar(cab.get("From")), assunto)
                if origem:
                    novos.append((origem, assunto))
            self._salvar_vistos()
            return novos
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def _rodar(self):
        intervalo = max(60, int(_cfg("GMAIL_INTERVALO", 120)))
        while True:
            try:
                for origem, assunto in self.buscar_novos():
                    self.ao_chegar(origem, assunto)
            except imaplib.IMAP4.error as e:
                self.log(f"Erro Gmail: login recusado ({e}). Confira a senha de app no .env.")
                return
            except Exception as e:
                print(f"[gmail] falhou agora, tento de novo depois: {e}")
            time.sleep(intervalo)

    def iniciar(self):
        if not self.configurado:
            self.log("Gmail não configurado (falta GMAIL_USUARIO e GMAIL_SENHA_APP no .env).")
            return False
        threading.Thread(target=self._rodar, daemon=True).start()
        return True


VIGIA = None   # preenchido pelo main.py


@habilidade("Confere agora se chegou e-mail importante no Gmail (Workana, vagas de emprego, clientes).")
def verificar_email():
    if not VIGIA or not VIGIA.configurado:
        return "O Gmail ainda não está configurado. Falta colocar a senha de app no arquivo .env."
    try:
        novos = VIGIA.buscar_novos()
    except Exception as e:
        return f"Não consegui acessar o Gmail agora ({e.__class__.__name__})."
    if not novos:
        return "Nenhum e-mail novo importante."
    return "Chegou: " + "; ".join(f"{o}: {a}" for o, a in novos[:5])
