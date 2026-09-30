# Marin — assistente pessoal por voz

Assistente estilo "Jarvis", com voz feminina, que roda no seu PC. O cérebro é uma IA local (Ollama), então é grátis e privado.

## Como instalar (só uma vez)

1. Instale o **Python 3.12** (python.org) e marque **"Add Python to PATH"**.
2. Dê dois cliques em **`instalar.bat`**. Ele cria o ambiente, instala tudo, instala o Ollama e baixa os modelos (cerca de 6 GB no total).

## Como usar

Dê dois cliques em **`iniciar.bat`**.

- Diga **"Marin"** e faça o pedido: *"Marin, que horas são?"*, *"Marin, toca Legião Urbana"*.
- Ou diga só "Marin", espere o bip e fale.
- Ou clique no círculo, aperte **Espaço** na janela, ou **Ctrl+Alt+M** de qualquer lugar.
- Depois que ela responde, dá pra continuar a conversa por alguns segundos sem chamar pelo nome. Diga "obrigado" para encerrar.
- **Esc** ou clicar no círculo enquanto ela fala faz ela parar.
- Também dá pra digitar na caixa de texto.

## O que ela sabe fazer

| Área | Exemplos |
|---|---|
| Controle do PC | "abre o Chrome", "fecha o Spotify", "abre o GitHub", "volume em 30", "tira um print", "bloqueia o PC", "desliga o computador" (ela pede confirmação) |
| Hora, clima, pesquisa | "que dia é hoje?", "vai chover amanhã?", "clima em São Paulo", "pesquisa o preço da RTX 4060" |
| Música e YouTube | "toca Matuê no YouTube", "pausa", "próxima música" |
| Lembretes e anotações | "me lembra de beber água daqui 30 minutos", "lembrete às 19h pra aula", "quais meus lembretes?", "anota: ligar pro cliente", "lê minhas anotações" |

## Voz fofa (ElevenLabs)

A voz grátis do Edge é boa, mas não chega no estilo anime. O ElevenLabs tem vozes bem mais naturais e deixa você **criar uma voz nova só descrevendo como ela é**. O plano grátis dá 10 mil créditos por mês, o que dá mais ou menos 100 a 200 respostas. Quando acabar, a Marin volta sozinha pra voz do Edge.

1. Crie uma conta em **elevenlabs.io**.
2. Vá em **Voices → Create a Voice → Voice Design** e cole esta descrição:

   > A young adult woman with a bright, sweet, bubbly anime-heroine voice. Soft and slightly high-pitched but natural, cheerful, playful and expressive, speaking fluent Brazilian Portuguese with a warm smile in her voice. Clear, close-mic studio quality.

   Texto de teste: *"Oi, Levy! Nossa, que bom te ver. Deixa comigo, já abri o YouTube pra você. Prontinho!"*
3. Gere, ouça as opções e salve a que mais gostar com o nome **Marin**.
4. Na lista de vozes, abra a Marin e copie o **Voice ID**.
5. Vá no seu perfil (canto inferior esquerdo) → **API Keys → Create API Key** e copie a chave.
6. No `config.py`, preencha:
   ```python
   ELEVENLABS_CHAVE = "sk_...sua chave..."
   ELEVENLABS_VOZ_ID = "...o voice id..."
   ```
7. Rode o `testar_voz.bat` pra ouvir.

Ajuste fino no `config.py`: `ELEVENLABS_ESTABILIDADE` menor deixa ela mais emotiva, `ELEVENLABS_VELOCIDADE` muda o ritmo.

## Personalizar

Tudo fica em **`config.py`**: nome, como ela te chama, cidade, voz, modelo de IA, sensibilidade do microfone e atalho.

- **Outra voz grátis:** `VOZ = "pt-BR-FranciscaNeural"` (evite subir muito o `TOM_VOZ`: fica robótico).
- **IA mais esperta:** com 8 GB de VRAM, `qwen2.5:7b` é o equilíbrio ideal. Para testar outro: `ollama pull llama3.1:8b` e troque `MODELO_IA`.
- **Ela ativa sozinha com barulho / não te escuta:** aumente ou diminua `SENSIBILIDADE`.
- **Microfone errado:** `iniciar.bat --microfones` lista os microfones; coloque o número em `MICROFONE`.

## Criar uma habilidade nova

Em `core/ferramentas.py`:

```python
@habilidade("Abre a pasta de projetos.")
def abrir_projetos():
    os.startfile(r"C:\Users\king0\PycharmProjects")
    return "Pasta de projetos aberta."
```

Pronto: ela já entende "abre meus projetos".

## Estrutura

```
main.py            orquestra tudo (escuta → entende → age → fala)
config.py          configurações
core/audio.py      microfone e detecção de fala
core/stt.py        voz → texto (faster-whisper, GPU)
core/cerebro.py    IA local (Ollama) + uso de ferramentas
core/ferramentas.py habilidades
core/tts.py        texto → voz (ElevenLabs ou edge-tts)
core/lembretes.py  lembretes
hud/index.html     interface
data/              lembretes e anotações
```

## Problemas comuns

- **"O Ollama não está rodando":** abra o Ollama pelo menu Iniciar.
- **Whisper usando CPU:** funciona normalmente, só um pouco mais lento. Para usar a GPU, confira se o driver da NVIDIA está atualizado.
- **Sem voz:** a voz neural precisa de internet. Sem internet ela usa a voz do Windows.
- **Janela não abre:** rode `iniciar.bat --terminal` para usar só por voz.
