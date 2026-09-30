"""Transcrição de voz para texto com faster-whisper (usa a placa de vídeo se der)."""
import glob
import os
import sys

import config


def _registrar_dlls_cuda():
    """No Windows, as DLLs do CUDA instaladas via pip ficam em site-packages/nvidia/*/bin."""
    if os.name != "nt":
        return
    for base in sys.path:
        for pasta in glob.glob(os.path.join(base, "nvidia", "*", "bin")):
            try:
                os.add_dll_directory(pasta)
                os.environ["PATH"] = pasta + os.pathsep + os.environ.get("PATH", "")
            except Exception:
                pass


def _desviar_av():
    """O faster-whisper importa a biblioteca 'av' (decodificar arquivos de áudio), mas a Marin
    passa o áudio direto do microfone e não precisa dela. Se o Windows bloquear a 'av'
    (Controle Inteligente de Aplicativos), colocamos um módulo vazio no lugar."""
    try:
        import av  # noqa: F401
    except Exception:
        import types
        sys.modules["av"] = types.ModuleType("av")


class Transcritor:
    def __init__(self, log=print):
        _registrar_dlls_cuda()
        _desviar_av()
        from faster_whisper import WhisperModel

        self._Modelo = WhisperModel
        self.log = log
        disp = config.WHISPER_DISPOSITIVO
        self.modelo = None
        if disp in ("auto", "cuda"):
            try:
                self.modelo = WhisperModel(config.WHISPER_MODELO, device="cuda", compute_type="float16")
                self.dispositivo = "GPU"
            except Exception as e:
                if disp == "cuda":
                    raise
                log(f"Whisper na GPU não carregou ({e.__class__.__name__}), usando CPU.")
        if self.modelo is None:
            self._usar_cpu()

    def _usar_cpu(self):
        self.modelo = self._Modelo(config.WHISPER_MODELO, device="cpu", compute_type="int8")
        self.dispositivo = "CPU"

    def transcrever(self, audio, dica=None) -> str:
        try:
            return self._transcrever(audio, dica)
        except Exception as e:
            if self.dispositivo == "GPU":
                # Falta alguma DLL do CUDA: cai para CPU e segue a vida
                self.log(f"Erro na GPU ({e.__class__.__name__}); trocando o Whisper para CPU.")
                self._usar_cpu()
                return self._transcrever(audio, dica)
            raise

    def _transcrever(self, audio, dica):
        segmentos, _ = self.modelo.transcribe(
            audio,
            language="pt",
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
            initial_prompt=dica or PROMPT,
        )
        texto = " ".join(s.text.strip() for s in segmentos).strip()
        return _limpar_alucinacao(texto)


PROMPT = f"Conversa em português com a assistente {config.NOME}."

# Frases que o Whisper "inventa" quando só tem ruído
_ALUCINACOES = [
    "legendas pela comunidade", "amara.org", "obrigado por assistir", "inscreva-se",
    "legenda adriana zanotto", PROMPT.lower().rstrip("."),
]


def _limpar_alucinacao(texto: str) -> str:
    t = texto.lower()
    if any(a in t for a in _ALUCINACOES) and len(t) < 60:
        return ""
    return texto
