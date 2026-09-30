"""Voz da Marin.

Motores:
  - ElevenLabs (voz mais natural/fofa; precisa de chave, tem plano grátis)
  - edge-tts   (grátis, reserva)
  - voz do Windows (offline, último recurso)

A fala funciona em "linha de montagem": enquanto uma frase toca, a próxima já está sendo gerada.
"""
import asyncio
import os
import queue
import re
import tempfile
import threading
import time

import requests

import config

try:
    import pygame
    pygame.mixer.init()
    _PYGAME = True
except Exception:
    _PYGAME = False

_FIM = object()


class Voz:
    def __init__(self, log=print):
        self.log = log
        self.interromper = threading.Event()
        self._pasta = tempfile.mkdtemp(prefix="marin_")
        self._n = 0
        self._n_trava = threading.Lock()
        self._eleven_ok = bool(getattr(config, "ELEVENLABS_CHAVE", ""))
        self.motor = "ElevenLabs" if self._eleven_ok else "Edge"

    # ------------------------------------------------------------------
    # API usada pelo resto da Marin
    # ------------------------------------------------------------------
    def falar(self, texto: str, ao_comecar=None):
        """Fala um texto inteiro e só volta quando terminar."""
        fala = self.nova_fala(ao_comecar)
        for frase in dividir_frases(texto):
            fala.dizer(frase)
        fala.esperar()

    def nova_fala(self, ao_comecar=None):
        """Abre uma fala em que você vai mandando frases aos poucos (ex.: enquanto a IA pensa)."""
        self.interromper.clear()
        return _Fala(self, ao_comecar)

    def parar(self):
        self.interromper.set()
        if _PYGAME:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # geração de áudio
    # ------------------------------------------------------------------
    def _novo_arquivo(self):
        with self._n_trava:
            self._n += 1
            return os.path.join(self._pasta, f"fala_{self._n % 12}.mp3")

    def gerar(self, texto):
        """Devolve o caminho do mp3, ou ("offline", texto) se nenhum motor online funcionar."""
        texto = limpar_para_fala(texto)
        if not texto:
            return None
        if self._eleven_ok:
            try:
                return self._gerar_eleven(texto)
            except Exception as e:
                self.log(f"Voz ElevenLabs falhou ({_resumo(e)}); usando a voz do Edge.")
                if "401" in str(e) or "quota" in str(e).lower():
                    self._eleven_ok = False   # chave errada ou créditos acabaram
                    self.motor = "Edge"
        try:
            return self._gerar_edge(texto)
        except Exception as e:
            self.log(f"Voz online falhou ({_resumo(e)}); usando voz do Windows.")
            return ("offline", texto)

    def _gerar_eleven(self, texto):
        """Tenta o modelo escolhido; se a conta não tiver acesso a ele, cai para um mais simples.
        Sempre pede sotaque brasileiro (language_code) quando o modelo aceita."""
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOZ_ID}"
        if not hasattr(self, "_combos"):
            modelos = [config.ELEVENLABS_MODELO] + [m for m in ("eleven_v4_turbo", "eleven_flash_v2_5")
                                                     if m != config.ELEVENLABS_MODELO]
            self._combos = [(m, lang) for m in modelos for lang in ("pt", None)]
        ultimo = None
        for modelo, lang in list(self._combos):
            corpo = {
                "text": texto,
                "model_id": modelo,
                "voice_settings": {
                    "stability": config.ELEVENLABS_ESTABILIDADE,
                    "similarity_boost": 0.8,
                    "style": config.ELEVENLABS_EXPRESSIVIDADE,
                    "use_speaker_boost": True,
                    "speed": config.ELEVENLABS_VELOCIDADE,
                },
            }
            if lang:
                corpo["language_code"] = lang
            r = requests.post(url, params={"output_format": "mp3_44100_128"}, headers={
                "xi-api-key": config.ELEVENLABS_CHAVE, "Content-Type": "application/json",
            }, json=corpo, timeout=20)
            if r.status_code == 200:
                if self._combos[0] != (modelo, lang):
                    self.log(f"Voz ElevenLabs usando o modelo {modelo}.")
                    self._combos = [(modelo, lang)] + [c for c in self._combos if c != (modelo, lang)]
                break
            ultimo = f"{r.status_code} {r.text[:120]}"
            if r.status_code in (400, 403, 404, 422) and ("model" in r.text.lower() or "language" in r.text.lower()):
                self._combos.remove((modelo, lang))   # combinação não aceita: nem tenta de novo
                continue
            raise RuntimeError(ultimo)
        else:
            raise RuntimeError(ultimo or "nenhum modelo disponível")
        caminho = self._novo_arquivo()
        with open(caminho, "wb") as f:
            f.write(r.content)
        return caminho

    def _gerar_edge(self, texto):
        import edge_tts

        caminho = self._novo_arquivo()

        async def _run():
            com = edge_tts.Communicate(texto, config.VOZ, rate=config.VELOCIDADE_VOZ, pitch=config.TOM_VOZ)
            await com.save(caminho)

        asyncio.run(_run())
        return caminho

    # ------------------------------------------------------------------
    # reprodução
    # ------------------------------------------------------------------
    def tocar(self, item):
        if item is None or self.interromper.is_set():
            return
        if isinstance(item, tuple):
            return self._falar_offline(item[1])
        if not _PYGAME:
            return self._falar_offline("")
        pygame.mixer.music.load(item)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if self.interromper.is_set():
                pygame.mixer.music.stop()
                break
            time.sleep(0.03)
        pygame.mixer.music.unload()

    def _falar_offline(self, texto):
        if not texto:
            return
        try:
            import pyttsx3
            motor = pyttsx3.init()
            for v in motor.getProperty("voices"):
                nome = (v.name or "").lower()
                if "maria" in nome or "portuguese" in nome or "brazil" in nome:
                    motor.setProperty("voice", v.id)
                    break
            motor.say(texto)
            motor.runAndWait()
        except Exception as e:
            self.log(f"Sem voz disponível: {e}")


class _Fala:
    """Linha de montagem: gera a próxima frase enquanto a atual toca."""

    def __init__(self, voz: Voz, ao_comecar=None):
        self.voz = voz
        self.ao_comecar = ao_comecar
        self.frases = queue.Queue()
        self.audios = queue.Queue(maxsize=3)
        self._comecou = False
        self._t_gerar = threading.Thread(target=self._gerador, daemon=True)
        self._t_tocar = threading.Thread(target=self._tocador, daemon=True)
        self._t_gerar.start()
        self._t_tocar.start()

    def dizer(self, frase):
        if frase and frase.strip():
            self.frases.put(frase)

    def esperar(self):
        self.frases.put(_FIM)
        self._t_tocar.join()

    def _gerador(self):
        while True:
            frase = self.frases.get()
            if frase is _FIM or self.voz.interromper.is_set():
                if frase is not _FIM:
                    # descarta o resto até o fim
                    while self.frases.get() is not _FIM:
                        pass
                self.audios.put(_FIM)
                return
            self.audios.put(self.voz.gerar(frase))

    def _tocador(self):
        while True:
            item = self.audios.get()
            if item is _FIM:
                return
            if not self._comecou and self.ao_comecar:
                self._comecou = True
                self.ao_comecar()
            self.voz.tocar(item)


# ----------------------------------------------------------------------
def dividir_frases(texto: str):
    partes = re.split(r"(?<=[.!?…])\s+", texto.strip())
    return [p for p in partes if p.strip()]


def limpar_para_fala(texto: str) -> str:
    """Tira markdown, links e emojis antes de falar."""
    texto = re.sub(r"```.*?```", " ", texto, flags=re.S)
    texto = re.sub(r"https?://\S+", "o link", texto)
    texto = re.sub(r"[*_#`>|]", "", texto)
    texto = re.sub(r"^\s*[-•]\s*", "", texto, flags=re.M)
    texto = re.sub(r"[\U0001F000-\U0001FAFF☀-➿]", "", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def _resumo(e):
    return str(e)[:80] or e.__class__.__name__
