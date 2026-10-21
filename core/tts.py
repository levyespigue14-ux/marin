"""Voz da Marin.

Motores:
  - Voz própria (XTTS: imita os áudios da pasta voz_marin/, roda no PC, grátis)
  - Kokoro     (voz local no PC: grátis, sem limite, sem internet)
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
        # Com o ElevenLabs como voz principal, a voz própria (XTTS, pesada) só é carregada
        # se o ElevenLabs falhar. Assim a Marin abre bem mais rápido e sobra placa de vídeo pra IA.
        self._propria_adiada = (getattr(config, "VOZ_PRINCIPAL", "propria") == "elevenlabs" and self._eleven_ok
                                and getattr(config, "USAR_VOZ_PROPRIA", False))
        self._propria = None if self._propria_adiada else _carregar_voz_propria(log)
        self._kokoro = None if (self._propria or self._propria_adiada) else _carregar_kokoro(log)
        if getattr(config, "VOZ_PRINCIPAL", "propria") == "elevenlabs" and self._eleven_ok:
            self.motor = "ElevenLabs (reserva: " + ("voz própria)" if (self._propria or self._propria_adiada) else "Edge)")
        elif self._propria:
            self.motor = "Voz própria (local)"
        else:
            self.motor = "Kokoro (local)" if self._kokoro else ("ElevenLabs" if self._eleven_ok else "Edge")

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
        if getattr(config, "VOZ_PRINCIPAL", "propria") == "elevenlabs" and self._eleven_ok:
            try:
                return self._gerar_eleven(texto)
            except Exception as e:
                self.log(f"Voz ElevenLabs falhou ({_resumo(e)}); usando a voz própria.")
                if "401" in str(e) or "quota" in str(e).lower():
                    self._eleven_ok = False
                    self.log("Créditos do ElevenLabs acabaram: a Marin passa a usar a voz própria (grátis).")
        if self._propria is None and self._propria_adiada:
            self._propria_adiada = False
            self._propria = _carregar_voz_propria(self.log)
        if self._propria:
            try:
                return self._gerar_propria(texto)
            except Exception as e:
                self.log(f"Voz própria falhou ({_resumo(e)}); usando a reserva.")
        if self._kokoro:
            try:
                return self._gerar_kokoro(texto)
            except Exception as e:
                self.log(f"Voz local falhou ({_resumo(e)}); usando a voz online.")
        if self._eleven_ok:
            try:
                return self._gerar_eleven(texto)
            except Exception as e:
                self.log(f"Voz ElevenLabs falhou ({_resumo(e)}); usando a voz do Edge.")
                if "401" in str(e) or "quota" in str(e).lower():
                    self._eleven_ok = False   # chave errada ou créditos acabaram
                    self.motor = "Edge"
                    self.log("ATENÇÃO: a voz do ElevenLabs parou (créditos acabaram ou chave inválida). "
                             "Rode o testar_voz.bat para ver o motivo. Até lá ela fala com a voz reserva.")
        try:
            return self._gerar_edge(texto)
        except Exception as e:
            self.log(f"Voz online falhou ({_resumo(e)}); usando voz do Windows.")
            return ("offline", texto)

    def _voz_eleven_id(self):
        """Acha o ID da voz pelo nome (ELEVENLABS_VOZ_NOME) uma vez só; senão usa o ELEVENLABS_VOZ_ID."""
        if not hasattr(self, "_eleven_id"):
            self._eleven_id = config.ELEVENLABS_VOZ_ID
            nome = (getattr(config, "ELEVENLABS_VOZ_NOME", "") or "").strip().lower()
            if nome:
                try:
                    r = requests.get("https://api.elevenlabs.io/v1/voices",
                                     headers={"xi-api-key": config.ELEVENLABS_CHAVE}, timeout=15)
                    for v in r.json().get("voices", []):
                        if v.get("name", "").strip().lower() == nome:
                            self._eleven_id = v["voice_id"]
                            break
                    else:
                        self.log(f"Não achei a voz '{nome}' no ElevenLabs; usando o ELEVENLABS_VOZ_ID.")
                except Exception as e:
                    self.log(f"Não consegui listar as vozes do ElevenLabs ({_resumo(e)}).")
        return self._eleven_id

    def _gerar_eleven(self, texto):
        """Usa o cache: frase que já foi falada antes não gasta crédito de novo (fica salva para sempre)."""
        import hashlib
        import shutil
        chave_cache = hashlib.sha1(f"{self._voz_eleven_id()}|{texto.strip().lower()}".encode("utf-8")).hexdigest()
        pasta_cache = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache_voz")
        no_cache = os.path.join(pasta_cache, chave_cache + ".mp3")
        if os.path.exists(no_cache):
            return no_cache
        caminho = self._gerar_eleven_api(texto)
        if len(texto) <= getattr(config, "CACHE_VOZ_MAX_CARACTERES", 200):
            try:
                os.makedirs(pasta_cache, exist_ok=True)
                shutil.copy(caminho, no_cache)
            except Exception:
                pass
        return caminho

    def _gerar_eleven_api(self, texto):
        """Tenta o modelo escolhido; se a conta não tiver acesso a ele, cai para um mais simples.
        Sempre pede sotaque brasileiro (language_code) quando o modelo aceita."""
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self._voz_eleven_id()}"
        if not hasattr(self, "_combos"):
            # se o modelo escolhido não estiver disponível, cai primeiro no multilingual_v2
            # (o mais natural em português); o flash é o último porque soa mais robótico
            reservas = ("eleven_multilingual_v2", "eleven_v4_turbo", "eleven_turbo_v2_5", "eleven_flash_v2_5")
            modelos = [config.ELEVENLABS_MODELO] + [m for m in reservas if m != config.ELEVENLABS_MODELO]
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

    def _gerar_propria(self, texto):
        import wave

        import numpy as np

        modelo, latente, falante, trava = self._propria
        with trava:   # o modelo usa a placa de vídeo: uma frase por vez
            out = modelo.inference(texto, "pt", latente, falante,
                                   temperature=float(getattr(config, "VOZ_PROPRIA_EMOCAO", 0.65)),
                                   top_p=0.8, top_k=40, repetition_penalty=10.0,
                                   speed=float(getattr(config, "VOZ_PROPRIA_VELOCIDADE", 1.0)),
                                   enable_text_splitting=True)
        wav = out["wav"]
        if hasattr(wav, "cpu"):
            wav = wav.cpu().numpy()
        pcm = (np.clip(np.asarray(wav, dtype=np.float32), -1, 1) * 32767).astype(np.int16)
        caminho = self._novo_arquivo()[:-4] + ".wav"
        with wave.open(caminho, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(pcm.tobytes())
        return caminho

    def _gerar_kokoro(self, texto):
        import wave

        import numpy as np

        k, estilo = self._kokoro
        agudo = max(0.8, min(1.4, float(getattr(config, "VOZ_LOCAL_AGUDO", 1.0))))
        # gera um pouco mais devagar e toca mais rápido: a voz fica mais aguda e a velocidade final igual
        amostras, taxa = k.create(texto, voice=estilo,
                                  speed=getattr(config, "VOZ_LOCAL_VELOCIDADE", 1.0) / agudo, lang="pt-br")
        caminho = self._novo_arquivo()[:-4] + ".wav"
        pcm = (np.clip(amostras, -1, 1) * 32767).astype(np.int16)
        with wave.open(caminho, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(int(taxa * agudo))
            w.writeframes(pcm.tobytes())
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
_KOKORO_CACHE = {}
_PROPRIA_CACHE = {}
_EXT_AUDIO = (".wav", ".mp3", ".flac", ".ogg", ".m4a")


def _carregar_voz_propria(log=print):
    """Carrega o XTTS e "aprende" a voz dos áudios da pasta voz_marin/ (uma vez só)."""
    if not getattr(config, "USAR_VOZ_PROPRIA", False):
        return None
    if "v" in _PROPRIA_CACHE:
        return _PROPRIA_CACHE["v"]
    _PROPRIA_CACHE["v"] = None
    pasta = getattr(config, "PASTA_VOZ_MARIN", "voz_marin")
    arquivos = [f for f in os.listdir(pasta) if f.lower().endswith(_EXT_AUDIO)] if os.path.isdir(pasta) else []
    # se existir a versão .wav limpa de um áudio, ignora o original (mp3) para não contar duas vezes
    stems_wav = {os.path.splitext(f)[0].lower() for f in arquivos if f.lower().endswith(".wav")}
    audios = sorted(os.path.join(pasta, f) for f in arquivos
                    if f.lower().endswith(".wav") or os.path.splitext(f)[0].lower() not in stems_wav)
    if not audios:
        return None
    try:
        os.environ.setdefault("COQUI_TOS_AGREED", "1")   # aceito no instalar_voz_propria.bat
        import torch
        from TTS.api import TTS
        log("Carregando a voz própria da Marin (na primeira vez demora)...")
        dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(dispositivo)
        modelo = tts.synthesizer.tts_model
        # usa o áudio inteiro (até 60 s) para captar melhor o timbre
        latente, falante = modelo.get_conditioning_latents(audio_path=audios, gpt_cond_len=30,
                                                           gpt_cond_chunk_len=6, max_ref_length=60)
        _PROPRIA_CACHE["v"] = (modelo, latente, falante, threading.Lock())
        log(f"Voz própria carregada ({len(audios)} áudio(s), usando {'placa de vídeo' if dispositivo == 'cuda' else 'processador'}).")
    except Exception as e:
        log(f"Não consegui carregar a voz própria ({_resumo(e)}). Rode o instalar_voz_propria.bat.")
    return _PROPRIA_CACHE["v"]



def _carregar_kokoro(log=print):
    """Carrega o modelo local uma vez só. Devolve (kokoro, estilo_da_voz) ou None."""
    if not getattr(config, "USAR_VOZ_LOCAL", False):
        return None
    if "k" in _KOKORO_CACHE:
        return _KOKORO_CACHE["k"]
    pasta = getattr(config, "PASTA_MODELOS", "modelos")
    modelo = os.path.join(pasta, "kokoro-v1.0.onnx")
    vozes = os.path.join(pasta, "voices-v1.0.bin")
    if not (os.path.exists(modelo) and os.path.exists(vozes)):
        log("Voz local não instalada (rode o instalar_voz_local.bat). Usando a voz online.")
        _KOKORO_CACHE["k"] = None
        return None
    try:
        from kokoro_onnx import Kokoro
        k = Kokoro(modelo, vozes)
        mistura = getattr(config, "VOZ_LOCAL_MISTURA", {"pf_dora": 1.0}) or {"pf_dora": 1.0}
        total = sum(mistura.values()) or 1
        estilo = sum(k.get_voice_style(v) * (p / total) for v, p in mistura.items())
        _KOKORO_CACHE["k"] = (k, estilo)
        log("Voz local (Kokoro) carregada.")
    except Exception as e:
        log(f"Não consegui carregar a voz local ({_resumo(e)}). Usando a voz online.")
        _KOKORO_CACHE["k"] = None
    return _KOKORO_CACHE["k"]


def dividir_frases(texto: str):
    partes = re.split(r"(?<=[.!?…])\s+", texto.strip())
    return [p for p in partes if p.strip()]


def limpar_para_fala(texto: str) -> str:
    """Tira markdown, links e emojis antes de falar."""
    pronuncia = getattr(config, "PRONUNCIA_NOME", "")
    if pronuncia:
        texto = re.sub(rf"\b{re.escape(config.COMO_ME_CHAMAR)}\b", pronuncia, texto)
    texto = re.sub(r"```.*?```", " ", texto, flags=re.S)
    texto = re.sub(r"https?://\S+", "o link", texto)
    texto = re.sub(r"[*_#`>|]", "", texto)
    texto = re.sub(r"^\s*[-•]\s*", "", texto, flags=re.M)
    texto = re.sub(r"[\U0001F000-\U0001FAFF☀-➿]", "", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def _resumo(e):
    return str(e)[:80] or e.__class__.__name__
