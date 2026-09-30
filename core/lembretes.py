"""Lembretes que a Marin avisa falando na hora certa."""
import json
import os
import threading
import time
from datetime import datetime

PASTA_DADOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ARQUIVO = os.path.join(PASTA_DADOS, "lembretes.json")


class Lembretes:
    def __init__(self, ao_vencer=None):
        os.makedirs(PASTA_DADOS, exist_ok=True)
        self.ao_vencer = ao_vencer
        self._trava = threading.Lock()
        self.itens = self._carregar()

    def _carregar(self):
        try:
            with open(ARQUIVO, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _salvar(self):
        with open(ARQUIVO, "w", encoding="utf-8") as f:
            json.dump(self.itens, f, ensure_ascii=False, indent=2)

    def adicionar(self, mensagem: str, quando: datetime):
        with self._trava:
            self.itens.append({"mensagem": mensagem, "quando": quando.isoformat(timespec="seconds")})
            self.itens.sort(key=lambda x: x["quando"])
            self._salvar()

    def listar(self):
        with self._trava:
            return list(self.itens)

    def remover(self, indice: int):
        with self._trava:
            if 0 <= indice < len(self.itens):
                item = self.itens.pop(indice)
                self._salvar()
                return item
        return None

    def iniciar(self):
        threading.Thread(target=self._vigiar, daemon=True).start()

    def _vigiar(self):
        while True:
            agora = datetime.now()
            vencidos = []
            with self._trava:
                for item in list(self.itens):
                    if datetime.fromisoformat(item["quando"]) <= agora:
                        vencidos.append(item)
                        self.itens.remove(item)
                if vencidos:
                    self._salvar()
            for item in vencidos:
                if self.ao_vencer:
                    try:
                        self.ao_vencer(item["mensagem"])
                    except Exception as e:
                        print("Erro ao avisar lembrete:", e)
            time.sleep(5)
