# 🎙️ Narrador de vídeos para TikTok

Transforma um texto em **narração com voz de IA em português** e monta o vídeo
vertical (1080x1920) pronto para postar, com:

- voz neural brasileira gratuita (Microsoft Edge TTS: Antonio, Francisca ou Thalita);
- **legendas estilo TikTok**, com a palavra que está sendo falada destacada em amarelo;
- vídeo de fundo cortado para 9:16 e repetido se for mais curto que a narração;
- música de fundo opcional, que **abaixa sozinha quando a voz fala**;
- volume ajustado ao padrão das redes sociais;
- um arquivo `.srt` de legenda, caso prefira usar as legendas do próprio TikTok/CapCut.

## Instalação (uma vez só)

1. Instale o **Python 3.9+**: https://www.python.org/downloads/ (no Windows, marque *"Add Python to PATH"*).
2. Instale o **ffmpeg**:
   - Windows: `winget install ffmpeg`
   - Mac: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`
3. Na pasta `tiktok-narrador`, instale a dependência:
   ```
   pip install -r requirements.txt
   ```

## Como usar

1. Escreva o roteiro num arquivo `.txt` (veja os exemplos em `exemplos/`).
2. Rode:

```bash
# só a narração com legenda sobre fundo escuro
python narrar.py exemplos/polvo.txt

# com o seu vídeo de fundo
python narrar.py exemplos/polvo.txt -v meu_video.mp4

# com vídeo + música + voz feminina, um pouco mais rápida
python narrar.py exemplos/polvo.txt -v meu_video.mp4 -m musica.mp3 --voz francisca --velocidade +15%

# só o áudio (MP3) + legenda .srt, para editar no CapCut
python narrar.py exemplos/polvo.txt --so-audio
```

O resultado sai ao lado do roteiro (`exemplos/polvo.mp4`) ou onde você indicar com `-o`.

## Opções úteis

| Opção | O que faz | Padrão |
|---|---|---|
| `--voz` | `antonio`, `francisca`, `thalita` (ou qualquer voz do `edge-tts --list-voices`) | `antonio` |
| `--velocidade` | velocidade da fala, ex.: `+0%`, `+20%`, `-10%` | `+10%` |
| `--tom` | tom da voz, ex.: `+5Hz`, `-5Hz` | `+0Hz` |
| `-m` / `--volume-musica` | música de fundo e o volume dela (0 a 1) | `0.25` |
| `--manter-audio` | mantém, baixinho, o som original do vídeo | desligado |
| `--sem-legenda` | não coloca legendas no vídeo | — |
| `--palavras-por-legenda` | quantas palavras aparecem por vez | `3` |
| `--cor-destaque` | cor da palavra falada | `#FFE600` |
| `--fonte` / `--tamanho-fonte` | fonte das legendas | `Arial` / `96` |

## Dicas para vídeos de curiosidades

- **Gancho nos primeiros 2 segundos**: comece com uma pergunta ou frase chocante
  ("Você sabia que...", "Esse alimento nunca estraga.").
- **Frases curtas.** A pontuação vira pausa na voz: use `.`, `!` e `?` para dar ritmo.
- **30 a 60 segundos** costuma ser o ideal (≈ 80 a 150 palavras).
- **Termine com uma chamada**: "Segue para mais", "Salva esse vídeo", "Comenta aí".
- Ao postar vídeo com voz sintética, marque no TikTok a opção de **conteúdo gerado por IA**, se for pedido.
- Use vídeos e músicas que você tem direito de usar (gravações suas, bancos gratuitos como Pexels/Pixabay, ou a biblioteca de sons do próprio TikTok).

## Narrar um vídeo que já está pronto (com tempo de cada fala)

Se o vídeo já tem as cenas montadas, escreva o roteiro com o **segundo em que cada fala começa**:

```
[00:00] Sete easter eggs de GTA 6 que ninguém achou!
[00:03] Sete: no topo da torre de rádio mais alta de Vice City...
[00:10] Seis: perdido no mar? ...
```

e rode:

```bash
python narrar.py exemplos/gta6_easter_eggs.txt -v gta6_easter_eggs_tiktok.mp4 --sem-legenda
```

Cada fala é gerada separadamente e colocada no segundo indicado. Se uma fala for maior que o
espaço até a próxima, ela é acelerada um pouco (até 1,35x) e o programa avisa quais trechos
convém encurtar. Use `--sem-legenda` quando o vídeo já tiver texto na tela; o `.srt` continua
sendo gerado. Para mudar a altura das legendas, use `--altura-legenda` (0 = topo, 1920 = base).

> Dica: a voz `thalita` é multilíngue e costuma pronunciar melhor termos em inglês como "easter eggs".
