"""Baixa os arquivos da voz local (Kokoro) para a pasta modelos/. Roda uma vez só (~350 MB)."""
import os
import sys
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modelos")
os.makedirs(PASTA, exist_ok=True)

for nome in ("voices-v1.0.bin", "kokoro-v1.0.onnx"):
    destino = os.path.join(PASTA, nome)
    if os.path.exists(destino) and os.path.getsize(destino) > 1_000_000:
        print(f"{nome}: já baixado.")
        continue
    print(f"Baixando {nome}...")

    def progresso(blocos, tam_bloco, total):
        if total > 0:
            print(f"\r  {min(100, blocos * tam_bloco * 100 // total)}%", end="", flush=True)

    urllib.request.urlretrieve(BASE + nome, destino + ".parcial", progresso)
    os.replace(destino + ".parcial", destino)
    print("  pronto!")

print("\nVoz local instalada. Feche e abra a Marin de novo.")
