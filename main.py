"""
███╗   ███╗ █████╗ ██████╗ ██╗███╗   ██╗
████╗ ████║██╔══██╗██╔══██╗██║████╗  ██║
██╔████╔██║███████║██████╔╝██║██╔██╗ ██║
██║╚██╔╝██║██╔══██║██╔══██╗██║██║╚██╗██║
██║ ╚═╝ ██║██║  ██║██║  ██║██║██║ ╚████║
╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝
Assistente pessoal por voz.  Uso:
    python main.py              -> abre com a interface HUD
    python main.py --terminal   -> só voz, no terminal
    python main.py --microfones -> lista os microfones
"""
import queue
import re
import sys
import threading
import time
import traceback
import unicodedata

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import config
from core import ferramentas
from core.lembretes import Lembretes

DISPENSAR = ["obrigado", "obrigada", "valeu", "so isso", "e so isso", "nada nao", "pode ir", "tchau", "deixa pra la"]
PREFIXOS = {"ei", "ok", "oi", "ola", "hey", "e", "fala", "alo", "o"}


def normalizar(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", " ", t)


def extrair_comando(texto: str):
    """Se o texto chama a Marin, devolve o pedido (pode ser ""). Se não chama, devolve None."""
    palavras = re.findall(r"\S+", texto)
    norm = [normalizar(p).strip() for p in palavras]
    ativ = set(config.PALAVRAS_ATIVACAO)
    # "ma rin" separado
    for i in range(len(norm) - 1):
        if f"{norm[i]} {norm[i + 1]}" in ativ:
            norm[i], norm[i + 1] = "marin", ""
    idx = next((i for i, p in enumerate(norm) if p in ativ), None)
    if idx is None:
        return None
    resto = [p for i, p in enumerate(palavras) if i != idx and norm[i] != ""]
    # tira "ei", "ok" do começo
    while resto and normalizar(resto[0]).strip() in PREFIXOS:
        resto.pop(0)
    comando = " ".join(resto).strip(" ,.!?;:")
    return comando if len(comando) > 2 else ""


class Marin:
    def __init__(self, ui):
        self.ui = ui
        self.fala_trava = threading.Lock()
        self.cancelar_escuta = threading.Event()   # interrompe a espera por fala
        self.pedido_manual = threading.Event()     # clique no reator / atalho
        self.textos = queue.Queue()                # mensagens digitadas na interface
        self.ouvido = self.stt = self.voz = self.cerebro = None
        self._timer_esconder = None

    # ---------- aparecer quando chamada / sumir depois ----------
    def aparecer(self):
        if self._timer_esconder:
            self._timer_esconder.cancel()
            self._timer_esconder = None
        self.ui.mostrar()

    def sumir_depois(self):
        segundos = getattr(config, "ESCONDER_DEPOIS", 0)
        if not segundos:
            return
        if self._timer_esconder:
            self._timer_esconder.cancel()
        self._timer_esconder = threading.Timer(segundos, self.ui.esconder)
        self._timer_esconder.daemon = True
        self._timer_esconder.start()

    # ---------- chamadas vindas da interface ----------
    def ativar(self):
        if self.voz and self.fala_trava.locked():
            self.voz.parar()        # clicar enquanto ela fala = interromper
            return
        self.pedido_manual.set()
        self.cancelar_escuta.set()

    def enviar_texto(self, texto):
        texto = (texto or "").strip()
        if texto:
            self.textos.put(texto)
            self.cancelar_escuta.set()

    def parar_fala(self):
        if self.voz:
            self.voz.parar()

    # ---------- inicialização ----------
    def iniciar(self):
        try:
            self._carregar()
            self._loop()
        except Exception as e:
            traceback.print_exc()
            self.ui.estado("erro", str(e))
            self.ui.log(f"Erro fatal: {e}")

    def _carregar(self):
        from core.audio import Ouvido
        from core.cerebro import Cerebro
        from core.stt import Transcritor
        from core.tts import Voz

        self.ui.estado("iniciando", "carregando voz")
        self.voz = Voz(log=self.ui.log)

        self.ui.estado("iniciando", "verificando cérebro")
        self.cerebro = Cerebro(log=self.ui.log, ao_usar_ferramenta=lambda n: self.ui.estado("pensando", n))
        problema = self.cerebro.verificar()
        if problema:
            self.ui.log(problema)
            self.ui.estado("erro", problema)
            self.falar(problema)
            raise SystemExit(problema)
        self.cerebro.aquecer()

        self.ui.estado("iniciando", "carregando ouvido (Whisper)")
        self.stt = Transcritor(log=self.ui.log)

        self.ui.estado("iniciando", "calibrando microfone")
        self.ouvido = Ouvido()
        self.ouvido.nivel_callback = self.ui.nivel
        self.ouvido.iniciar()

        self.lembretes = Lembretes(ao_vencer=self._avisar_lembrete)
        ferramentas.LEMBRETES = self.lembretes
        self.lembretes.iniciar()
        self._atualizar_lembretes()

        from core import gmail
        gmail.VIGIA = gmail.VigiaGmail(ao_chegar=self._avisar_email, log=self.ui.log)
        if gmail.VIGIA.iniciar():
            self.ui.log("Gmail: de olho nos e-mails do Workana e das vagas.")

        if config.ATALHO_GLOBAL:
            try:
                import keyboard
                keyboard.add_hotkey(config.ATALHO_GLOBAL, self.ativar)
            except Exception as e:
                self.ui.log(f"Atalho global indisponível: {e}")

        nome_voz = config.VOZ.replace("pt-BR-", "").replace("MultilingualNeural", "").replace("Neural", "")
        self.ui.info(modelo=config.MODELO_IA, whisper=f"{config.WHISPER_MODELO} · {self.stt.dispositivo}",
                     voz=nome_voz if self.voz.motor == "Edge" else "ElevenLabs", cidade=config.CIDADE_PADRAO,
                     atalho=config.ATALHO_GLOBAL)
        self.ui.log(f"Pronta. Diga \"{config.NOME}\" ou use {config.ATALHO_GLOBAL}.")
        hora = time.localtime().tm_hour
        nome = config.COMO_ME_CHAMAR
        saudacao = {"madrugada": f"Opa, ainda acordado, {nome}?", "manhã": f"Bom dia, {nome}!",
                    "tarde": f"Boa tarde, {nome}!", "noite": f"Boa noite, {nome}!"}[ferramentas.periodo_do_dia(hora)]
        self.falar(f"{saudacao} {config.NOME} online e pronta.")

    # ---------- loop principal ----------
    def _loop(self):
        while True:
            self.ui.estado("aguardando")
            if self._tratar_entradas():
                continue
            self.cancelar_escuta.clear()
            audio = self.ouvido.ouvir_frase(parar=self.cancelar_escuta)
            if audio is None:
                continue
            texto = self.stt.transcrever(audio)
            if not texto:
                continue
            comando = extrair_comando(texto)
            if comando is None:
                continue                      # não era com ela
            self.aparecer()
            if comando == "":
                self._modo_comando()
            else:
                self.processar(comando)
                self._conversa()
            self.sumir_depois()

    def _tratar_entradas(self):
        """Trata texto digitado e clique/atalho. Devolve True se tratou algo."""
        if not self.textos.empty():
            self.processar(self.textos.get(), digitado=True)
            return True
        if self.pedido_manual.is_set():
            self.pedido_manual.clear()
            self.aparecer()
            self._modo_comando()
            self.sumir_depois()
            return True
        return False

    def _ouvir_pedido(self, timeout):
        self.ui.estado("ouvindo")
        self.cancelar_escuta.clear()
        audio = self.ouvido.ouvir_frase(timeout_inicio=timeout, parar=self.cancelar_escuta)
        if audio is None:
            return None
        self.ui.estado("pensando", "transcrevendo")
        return self.stt.transcrever(audio)

    def _modo_comando(self):
        from core.audio import bip
        self.ouvido.mudo.set()
        bip("ativar")
        self.ouvido.limpar()
        self.ouvido.mudo.clear()
        # no atalho/clique grava direto, sem depender do volume do microfone
        self.ui.estado("ouvindo")
        self.cancelar_escuta.clear()
        audio = self.ouvido.gravar_direto(parar=self.cancelar_escuta)
        texto = None
        if audio is not None:
            self.ui.estado("pensando", "transcrevendo")
            texto = self.stt.transcrever(audio)
        if not texto:
            self.ui.log("Não entendi nada. Fale mais perto do microfone.")
            return
        comando = extrair_comando(texto)
        self.processar(comando if comando else texto)
        self._conversa()

    def _conversa(self):
        """Depois de responder, fica escutando um pouco sem precisar chamar pelo nome."""
        while True:
            texto = self._ouvir_pedido(timeout=config.TEMPO_CONVERSA)
            if not texto:
                return
            n = normalizar(texto).strip()
            if any(n == d or n.startswith(d + " ") or n.endswith(" " + d) for d in DISPENSAR) and len(n.split()) <= 5:
                self.falar("Disponha. Estou por aqui.")
                return
            comando = extrair_comando(texto)
            self.processar(comando if comando else texto)

    # ---------- ações ----------
    def processar(self, texto, digitado=False):
        self.ui.mensagem("voce", texto)
        self.ui.estado("pensando")
        t0 = time.time()

        # pedidos comuns: resposta instantânea, sem passar pela IA
        try:
            from core import rapido
            resposta = rapido.tentar(texto)
        except Exception as e:
            self.ui.log(f"Erro no atalho rápido: {e}")
            resposta = None
        if resposta:
            self.cerebro.lembrar(texto, resposta)
            self.ui.mensagem("marin", resposta)
            self.falar(resposta)
            return
        with self.fala_trava:
            self.ouvido and self.ouvido.mudo.set()
            primeira = []

            def comecou():
                if not primeira:
                    primeira.append(time.time() - t0)
                self.ui.estado("falando")

            fala = self.voz.nova_fala(ao_comecar=comecou)
            try:
                resposta = self.cerebro.responder(texto, ao_frase=fala.dizer)
            except Exception as e:
                traceback.print_exc()
                resposta = "Tive um problema para pensar agora. Confere se o Ollama está aberto."
                self.ui.log(f"Erro no cérebro: {e}")
                fala.dizer(resposta)
            self.ui.mensagem("marin", resposta)
            self._atualizar_lembretes()
            fala.esperar()
            if primeira:
                self.ui.log(f"⏱ começou a falar em {primeira[0]:.1f}s")
            self._soltar_microfone()

    def falar(self, texto):
        with self.fala_trava:
            self.ouvido and self.ouvido.mudo.set()
            try:
                self.voz.falar(texto, ao_comecar=lambda: self.ui.estado("falando"))
            finally:
                self._soltar_microfone()

    def _soltar_microfone(self):
        time.sleep(0.2)
        if self.ouvido:
            self.ouvido.limpar()
            self.ouvido.mudo.clear()

    def _avisar_lembrete(self, mensagem):
        from core.audio import bip
        self.aparecer()
        self.ui.mensagem("marin", f"⏰ Lembrete: {mensagem}")
        self._atualizar_lembretes()
        with self.fala_trava:
            self.ouvido.mudo.set()
            bip("ativar")
            self.ouvido.mudo.clear()
        self.falar(f"{config.tratamento().capitalize()}, lembrete: {mensagem}")
        self.sumir_depois()

    def _avisar_email(self, origem, assunto):
        from core.audio import bip
        assunto = assunto if len(assunto) <= 110 else assunto[:107] + "..."
        self.aparecer()
        self.ui.mensagem("marin", f"📩 {origem}: {assunto}")
        with self.fala_trava:
            self.ouvido.mudo.set()
            bip("ativar")
            self.ouvido.mudo.clear()
        self.falar(f"{config.tratamento().capitalize()}, chegou e-mail do {origem}: {assunto}")
        self.sumir_depois()

    def _atualizar_lembretes(self):
        if getattr(self, "lembretes", None):
            itens = [{"quando": x["quando"], "mensagem": x["mensagem"]} for x in self.lembretes.listar()]
            self.ui.lembretes(itens)


class Api:
    """Métodos que o JavaScript da interface pode chamar (POST /api/<metodo>)."""
    def __init__(self):
        self.marin = None

    def ativar(self):
        self.marin.ativar()

    def enviar_texto(self, texto):
        self.marin.enviar_texto(texto)

    def parar_fala(self):
        self.marin.parar_fala()

    def esquecer(self):
        self.marin.cerebro.esquecer()
        return "ok"


def main():
    if "--microfones" in sys.argv:
        from core.audio import listar_microfones
        listar_microfones()
        return

    usar_hud = config.USAR_HUD and "--terminal" not in sys.argv
    api = Api()
    ui = None
    if usar_hud:
        try:
            from core.interface import InterfaceHUD
            ui = InterfaceHUD(api)
        except Exception as e:
            print(f"HUD indisponível ({e}); usando o terminal.")
    if ui is None:
        from core.interface import InterfaceTerminal
        ui = InterfaceTerminal()

    marin = Marin(ui)
    api.marin = marin

    if hasattr(ui, "iniciar"):
        ui.iniciar(marin.iniciar)
    else:
        print(__doc__)
        try:
            marin.iniciar()
        except KeyboardInterrupt:
            print("\nAté mais!")


if __name__ == "__main__":
    main()
