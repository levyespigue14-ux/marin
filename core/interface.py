"""Ponte entre o Python e a interface HUD (janela pywebview) — ou o terminal, se preferir."""
import json
import os
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class InterfaceTerminal:
    """Usada quando o HUD está desligado ou o pywebview não está instalado."""
    ESTADOS = {"iniciando": "⏳ iniciando", "aguardando": "💤 aguardando", "ouvindo": "🎙 ouvindo",
               "pensando": "🧠 pensando", "falando": "🔊 falando", "erro": "⚠ erro"}

    def __init__(self):
        self.api = None

    def estado(self, e, detalhe=""):
        print(f"[{self.ESTADOS.get(e, e)}] {detalhe}".rstrip())

    def mensagem(self, quem, texto):
        print(f"{'Você' if quem == 'voce' else 'Marin'}: {texto}")

    def log(self, texto):
        print("  ·", texto)

    def nivel(self, x):
        pass

    def info(self, **dados):
        pass

    def lembretes(self, itens):
        pass


class InterfaceHUD(InterfaceTerminal):
    """Janela pywebview que carrega o HUD de um servidor local.

    O HUD (hud/index.html) recebe eventos por /eventos (SSE) e chama o Python por POST /api/<metodo>.
    """
    REPETIR = ("estado", "info", "lembretes")   # reenviados quando a janela (re)conecta

    def __init__(self, api):
        import webview
        self.webview = webview
        self.api = api
        self._ultimo_nivel = 0.0
        self._clientes = []
        self._trava = threading.Lock()
        self._ultimos = {}
        self._servidor = self._criar_servidor()
        porta = self._servidor.server_address[1]
        threading.Thread(target=self._servidor.serve_forever, daemon=True).start()
        self.janela = webview.create_window(
            "Marin", url=f"http://127.0.0.1:{porta}/", width=1100, height=700,
            min_size=(760, 520), background_color="#05070d",
        )

    # ---------- servidor local ----------
    def _criar_servidor(self):
        ui = self
        html = os.path.join(RAIZ, "hud", "index.html")

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    with open(html, "rb") as f:
                        corpo = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(corpo)))
                    self.end_headers()
                    self.wfile.write(corpo)
                elif self.path == "/eventos":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    fila = queue.Queue()
                    with ui._trava:
                        ui._clientes.append(fila)
                        for fn in ui.REPETIR:
                            if fn in ui._ultimos:
                                fila.put(ui._ultimos[fn])
                    try:
                        while True:
                            try:
                                msg = fila.get(timeout=15)
                            except queue.Empty:
                                msg = None
                            if msg is None:
                                self.wfile.write(b": ping\n\n")
                            else:
                                self.wfile.write(f"data: {msg}\n\n".encode("utf-8"))
                            self.wfile.flush()
                    except Exception:
                        pass
                    finally:
                        with ui._trava:
                            if fila in ui._clientes:
                                ui._clientes.remove(fila)
                else:
                    self.send_error(404)

            def do_POST(self):
                if not self.path.startswith("/api/"):
                    self.send_error(404)
                    return
                metodo = self.path[len("/api/"):]
                tamanho = int(self.headers.get("Content-Length") or 0)
                try:
                    args = json.loads(self.rfile.read(tamanho) or b"[]")
                    funcao = getattr(ui.api, metodo, None)
                    if metodo.startswith("_") or not callable(funcao):
                        self.send_error(404)
                        return
                    resultado = funcao(*args)
                    corpo = json.dumps(resultado, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                except Exception as e:
                    print(f"[hud] erro em /api/{metodo}: {e}")
                    corpo = json.dumps({"erro": str(e)}).encode("utf-8")
                    self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

        return ThreadingHTTPServer(("127.0.0.1", 0), Handler)

    def _enviar(self, fn, *args):
        msg = json.dumps({"fn": fn, "args": list(args)}, ensure_ascii=False)
        with self._trava:
            if fn in self.REPETIR:
                self._ultimos[fn] = msg
            for fila in self._clientes:
                fila.put(msg)

    # ---------- o que a Marin mostra na tela ----------
    def estado(self, e, detalhe=""):
        self._enviar("estado", e, detalhe)

    def mensagem(self, quem, texto):
        self._enviar("mensagem", quem, texto)

    def log(self, texto):
        print("  ·", texto)
        self._enviar("log", texto)

    def nivel(self, x):
        agora = time.time()
        if agora - self._ultimo_nivel > 0.06:
            self._ultimo_nivel = agora
            self._enviar("nivel", round(x, 3))

    def info(self, **dados):
        self._enviar("info", dados)

    def lembretes(self, itens):
        self._enviar("lembretes", itens)

    def iniciar(self, funcao):
        """Abre a janela (precisa ser na thread principal) e roda `funcao` em paralelo."""
        self.webview.start(funcao, debug=False)
