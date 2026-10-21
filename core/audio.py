"""Microfone: captura contínua e detecção de quando você começa/termina de falar."""
import collections
import queue
import threading
import time

import numpy as np
import sounddevice as sd

import config

TAXA = 16000
BLOCO = 480  # 30 ms


class Ouvido:
    def __init__(self):
        self.fila: "queue.Queue[np.ndarray]" = queue.Queue()
        self.mudo = threading.Event()        # enquanto ela fala, ignora o microfone
        self.ativacao_manual = threading.Event()  # atalho/clique na interface
        self.ruido = 150.0
        self.stream = None
        self.nivel_callback = None           # função(nivel 0..1) para animar a interface

    # ---------- captura ----------
    def _callback(self, indata, frames, tempo, status):
        if self.mudo.is_set():
            return
        bloco = indata[:, 0].copy()
        self.fila.put(bloco)

    def iniciar(self):
        self.stream = sd.InputStream(
            samplerate=TAXA, channels=1, dtype="int16", blocksize=BLOCO,
            device=config.MICROFONE, callback=self._callback,
        )
        self.stream.start()
        self.calibrar()

    def parar(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()

    def limpar(self):
        while not self.fila.empty():
            try:
                self.fila.get_nowait()
            except queue.Empty:
                break

    def calibrar(self, segundos=1.0):
        """Mede o barulho de fundo do ambiente."""
        self.limpar()
        niveis = []
        fim = time.time() + segundos
        while time.time() < fim:
            try:
                niveis.append(_rms(self.fila.get(timeout=0.5)))
            except queue.Empty:
                break
        if niveis:
            self.ruido = max(60.0, float(np.median(niveis)))

    # ---------- escuta ----------
    def _limiar(self):
        return max(self.ruido * config.SENSIBILIDADE, getattr(config, "LIMIAR_MINIMO", 280.0))

    def gravar_direto(self, segundos_max=7.0, parar=None):
        """Grava sem esperar a voz passar do limiar (usado no atalho Ctrl+Alt+M / clique).
        Para quando você fica ~1 s quieto depois de falar, ou no tempo máximo.
        Funciona mesmo com microfone baixo: quem separa voz de silêncio depois é o Whisper."""
        self.limpar()
        gravado, duracao, silencio, falou = [], 0.0, 0.0, False
        seg_bloco = BLOCO / TAXA
        limiar = max(self.ruido * 1.15, 60.0)
        while duracao < segundos_max:
            if parar is not None and parar.is_set():
                break
            try:
                bloco = self.fila.get(timeout=0.2)
            except queue.Empty:
                continue
            nivel = _rms(bloco)
            if self.nivel_callback:
                self.nivel_callback(min(1.0, nivel / (limiar * 4)))
            gravado.append(bloco)
            duracao += seg_bloco
            if nivel > limiar:
                falou, silencio = True, 0.0
            else:
                silencio += seg_bloco
            if falou and silencio >= 1.0 and duracao > 1.2:
                break
        if not gravado:
            return None
        return np.concatenate(gravado).astype(np.float32) / 32768.0

    def ouvir_frase(self, timeout_inicio=None, parar=None):
        """Espera você falar e devolve o áudio (float32 16 kHz) ou None.

        timeout_inicio: desiste se ninguém falar nesse tempo.
        parar: threading.Event que cancela a espera (ex.: ativação manual).
        """
        pre = collections.deque(maxlen=int(0.35 * TAXA / BLOCO))
        inicio_espera = time.time()
        falando = False
        blocos_fala = 0
        gravado = []
        silencio = 0.0
        duracao = 0.0
        seg_bloco = BLOCO / TAXA

        while True:
            if parar is not None and parar.is_set():
                return None
            if not falando and timeout_inicio and time.time() - inicio_espera > timeout_inicio:
                return None
            try:
                bloco = self.fila.get(timeout=0.2)
            except queue.Empty:
                continue

            nivel = _rms(bloco)
            limiar = self._limiar()
            if self.nivel_callback:
                self.nivel_callback(min(1.0, nivel / (limiar * 4)))

            if not falando:
                pre.append(bloco)
                if nivel > limiar:
                    blocos_fala += 1
                    if blocos_fala >= 3:
                        falando = True
                        gravado = list(pre)
                        duracao = len(gravado) * seg_bloco
                        silencio = 0.0
                else:
                    blocos_fala = 0
                    # adapta devagar ao barulho do ambiente
                    self.ruido = 0.97 * self.ruido + 0.03 * max(60.0, nivel)
                continue

            gravado.append(bloco)
            duracao += seg_bloco
            silencio = silencio + seg_bloco if nivel < limiar * 0.8 else 0.0

            if silencio >= config.SILENCIO_FIM or duracao >= config.FALA_MAXIMA:
                if duracao - silencio < 0.35:  # foi só um barulho curto
                    falando, blocos_fala, gravado = False, 0, []
                    pre.clear()
                    continue
                audio = np.concatenate(gravado).astype(np.float32) / 32768.0
                return audio


def _rms(bloco: np.ndarray) -> float:
    return float(np.sqrt(np.mean(bloco.astype(np.float32) ** 2)) + 1e-9)


def bip(tipo="ativar"):
    """Sonzinho curto de confirmação."""
    try:
        taxa = 22050
        if tipo == "ativar":
            notas = [(880, 0.07), (1320, 0.09)]
        else:
            notas = [(1320, 0.07), (880, 0.09)]
        partes = []
        for freq, dur in notas:
            t = np.linspace(0, dur, int(taxa * dur), False)
            onda = 0.18 * np.sin(2 * np.pi * freq * t)
            env = np.minimum(1, np.minimum(t / 0.01, (dur - t) / 0.02))
            partes.append(onda * env)
        sd.play(np.concatenate(partes).astype(np.float32), taxa)
        sd.wait()
    except Exception:
        pass


def listar_microfones():
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            print(f"[{i}] {d['name']}")
