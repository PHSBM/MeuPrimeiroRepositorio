#!/usr/bin/env python3
"""
Narrador de vídeos para TikTok.

Transforma um roteiro em texto numa narração com voz neural em português
(Microsoft Edge TTS, gratuito) e monta um vídeo vertical 1080x1920 com:
  - a narração,
  - legendas estilo TikTok (palavra atual destacada),
  - música de fundo opcional (abaixa sozinha quando a voz fala).

Uso rápido:
    python narrar.py exemplos/polvo.txt -v meu_video.mp4

Veja todas as opções com:
    python narrar.py --help
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

VOZES = {
    "antonio": "pt-BR-AntonioNeural",    # masculina, firme (padrão)
    "francisca": "pt-BR-FranciscaNeural",  # feminina, clara
    "thalita": "pt-BR-ThalitaMultilingualNeural",  # feminina, jovem
}

LARGURA, ALTURA = 1080, 1920
TICKS_POR_SEGUNDO = 10_000_000  # edge-tts usa unidades de 100 ns


@dataclass
class Palavra:
    texto: str
    inicio: float  # segundos
    fim: float


# --------------------------------------------------------------------------- #
# 1. Voz
# --------------------------------------------------------------------------- #
async def _sintetizar(texto: str, voz: str, velocidade: str, tom: str,
                      destino_mp3: Path) -> list[Palavra]:
    import edge_tts  # importado aqui para o --help funcionar sem a dependência

    comunicador = edge_tts.Communicate(
        texto, voz, rate=velocidade, pitch=tom, boundary="WordBoundary",
        # respeita proxy da rede (empresas, faculdades etc.), se houver
        proxy=os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
    )
    palavras: list[Palavra] = []
    with open(destino_mp3, "wb") as f:
        async for pedaco in comunicador.stream():
            if pedaco["type"] == "audio":
                f.write(pedaco["data"])
            elif pedaco["type"] == "WordBoundary":
                inicio = pedaco["offset"] / TICKS_POR_SEGUNDO
                fim = inicio + pedaco["duration"] / TICKS_POR_SEGUNDO
                palavras.append(Palavra(pedaco["text"], inicio, fim))
    return palavras


def sintetizar(texto: str, voz: str, velocidade: str, tom: str,
               destino_mp3: Path) -> list[Palavra]:
    """Gera o MP3 da narração e devolve o tempo de cada palavra."""
    return asyncio.run(_sintetizar(texto, voz, velocidade, tom, destino_mp3))


# --------------------------------------------------------------------------- #
# 2. Legendas
# --------------------------------------------------------------------------- #
def _tempo_ass(s: float) -> str:
    cs = int(round(s * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    seg, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{seg:02d}.{cs:02d}"


def _tempo_srt(s: float) -> str:
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    seg, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{seg:02d},{ms:03d}"


def agrupar(palavras: list[Palavra], por_grupo: int) -> list[list[Palavra]]:
    """Junta palavras em blocos curtos; quebra antes em fim de frase."""
    grupos: list[list[Palavra]] = []
    atual: list[Palavra] = []
    for p in palavras:
        atual.append(p)
        fim_de_frase = p.texto.rstrip()[-1:] in ".!?…"
        if len(atual) >= por_grupo or fim_de_frase:
            grupos.append(atual)
            atual = []
    if atual:
        grupos.append(atual)
    return grupos


def gerar_ass(palavras: list[Palavra], destino: Path, por_grupo: int,
              fonte: str, tamanho: int, cor_destaque: str, altura_y: int = 1150) -> None:
    # Cores ASS são &HBBGGRR; recebemos #RRGGBB.
    rr, gg, bb = cor_destaque[1:3], cor_destaque[3:5], cor_destaque[5:7]
    destaque = f"&H00{bb}{gg}{rr}".upper()

    cabecalho = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {LARGURA}
PlayResY: {ALTURA}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TikTok,{fonte},{tamanho},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,3,5,80,80,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    linhas = []
    for grupo in agrupar(palavras, por_grupo):
        for i, p in enumerate(grupo):
            inicio = p.inicio
            # a palavra fica destacada até a próxima começar (sem "piscar")
            fim = grupo[i + 1].inicio if i + 1 < len(grupo) else p.fim + 0.15
            partes = []
            for j, q in enumerate(grupo):
                t = q.texto.upper().replace("{", "(").replace("}", ")")
                if j == i:
                    partes.append(f"{{\\c{destaque}\\fscx110\\fscy110}}{t}{{\\r}}")
                else:
                    partes.append(t)
            # posição: um pouco abaixo do centro, longe da interface do TikTok
            texto = f"{{\\pos(540,{altura_y})}}" + " ".join(partes)
            linhas.append(
                f"Dialogue: 0,{_tempo_ass(inicio)},{_tempo_ass(fim)},TikTok,,0,0,0,,{texto}"
            )
    destino.write_text(cabecalho + "\n".join(linhas) + "\n", encoding="utf-8")


def gerar_srt(palavras: list[Palavra], destino: Path, por_grupo: int) -> None:
    blocos = []
    for n, grupo in enumerate(agrupar(palavras, por_grupo), start=1):
        texto = " ".join(p.texto for p in grupo)
        blocos.append(
            f"{n}\n{_tempo_srt(grupo[0].inicio)} --> {_tempo_srt(grupo[-1].fim)}\n{texto}\n"
        )
    destino.write_text("\n".join(blocos), encoding="utf-8")


# --------------------------------------------------------------------------- #
# 3. Montagem com ffmpeg
# --------------------------------------------------------------------------- #
def duracao(arquivo: Path) -> float:
    saida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(arquivo)],
        capture_output=True, text=True, check=True,
    )
    return float(saida.stdout.strip())


def montar(narracao: Path, saida: Path, pasta_tmp: Path, video: Path | None,
           musica: Path | None, volume_musica: float, manter_audio: bool,
           cor_fundo: str, legenda_ass: Path | None,
           total: float | None = None) -> None:
    if total is None:
        total = duracao(narracao) + 0.6  # pequena folga no final

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]

    # entrada 0: vídeo (em loop se for mais curto que a narração) ou fundo liso
    if video:
        cmd += ["-stream_loop", "-1", "-i", str(video.resolve())]
    else:
        cmd += ["-f", "lavfi", "-i",
                f"color=c={cor_fundo}:s={LARGURA}x{ALTURA}:r=30"]
    # entrada 1: narração
    cmd += ["-i", str(narracao.resolve())]
    # entrada 2: música (em loop)
    if musica:
        cmd += ["-stream_loop", "-1", "-i", str(musica.resolve())]

    filtros = []
    # vídeo: preenche a tela 9:16 cortando as bordas, 30 fps
    v = (f"[0:v]scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=increase,"
         f"crop={LARGURA}:{ALTURA},setsar=1,fps=30")
    if legenda_ass:
        # caminho relativo (cwd = pasta_tmp) evita problemas de escape no Windows
        v += f",ass={legenda_ass.name}"
    filtros.append(v + "[v]")

    # áudio
    filtros.append("[1:a]aresample=44100,volume=1.0,asplit=2[voz][voz_sc]")
    fundos = []
    if musica:
        filtros.append(f"[2:a]aresample=44100,volume={volume_musica}[mus]")
        fundos.append("[mus]")
    if manter_audio and video and _tem_audio(video):
        filtros.append("[0:a]aresample=44100,volume=0.25[orig]")
        fundos.append("[orig]")

    if fundos:
        if len(fundos) > 1:
            filtros.append(f"{''.join(fundos)}amix=inputs={len(fundos)}:normalize=0[fundo]")
        else:
            filtros.append(f"{fundos[0]}anull[fundo]")
        # "ducking": o fundo abaixa enquanto a voz fala
        filtros.append("[fundo][voz_sc]sidechaincompress=threshold=0.03:ratio=8:"
                       "attack=20:release=400[fundo_duck]")
        filtros.append("[voz][fundo_duck]amix=inputs=2:normalize=0,"
                       "loudnorm=I=-14:TP=-1.5[a]")
    else:
        filtros.append("[voz_sc]anullsink")
        filtros.append("[voz]loudnorm=I=-14:TP=-1.5[a]")

    cmd += [
        "-filter_complex", ";".join(filtros),
        "-map", "[v]", "-map", "[a]",
        "-t", f"{total:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(saida.resolve()),
    ]
    subprocess.run(cmd, check=True, cwd=pasta_tmp)


def _tem_audio(arquivo: Path) -> bool:
    saida = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(arquivo)],
        capture_output=True, text=True,
    )
    return bool(saida.stdout.strip())



# --------------------------------------------------------------------------- #
# 2b. Roteiro com marcações de tempo  ->  "[00:03] texto"
# --------------------------------------------------------------------------- #
MARCA = re.compile(r"^\s*\[(\d+):(\d{1,2}(?:\.\d+)?)\]\s*(.*)$")
ACELERACAO_MAX = 1.35  # acelera a fala no máximo 35% para caber no trecho


def ler_trechos(conteudo: str) -> list[tuple[float, str]] | None:
    """Devolve [(inicio_s, texto), ...] se o roteiro tiver marcações de tempo."""
    trechos: list[tuple[float, str]] = []
    for linha in conteudo.splitlines():
        m = MARCA.match(linha)
        if m:
            trechos.append((int(m[1]) * 60 + float(m[2]), m[3].strip()))
        elif linha.strip() and trechos:
            trechos[-1] = (trechos[-1][0], f"{trechos[-1][1]} {linha.strip()}")
    trechos = [(t, txt) for t, txt in trechos if txt]
    return sorted(trechos) if trechos else None


def narrar_trechos(trechos: list[tuple[float, str]], fim_total: float, voz: str,
                   velocidade: str, tom: str, pasta: Path, destino: Path) -> list[Palavra]:
    """Gera cada trecho, encaixa no tempo certo e junta numa só faixa."""
    entradas, filtros, todas = [], [], []
    for i, (inicio, texto) in enumerate(trechos):
        mp3 = pasta / f"trecho{i:02d}.mp3"
        palavras = sintetizar(texto, voz, velocidade, tom, mp3)
        dur = duracao(mp3)
        vaga = (trechos[i + 1][0] if i + 1 < len(trechos) else fim_total) - inicio
        fator = 1.0
        if dur > vaga * 0.97:
            fator = min(dur / (vaga * 0.95), ACELERACAO_MAX)
            if dur / fator > vaga:
                print(f"⚠️  Trecho [{inicio:.0f}s] ficou {dur / fator - vaga:.1f}s mais longo "
                      f"que o espaço ({vaga:.1f}s). Encurte o texto.")
        print(f"   [{inicio:5.1f}s] {dur:4.1f}s de fala em {vaga:4.1f}s"
              + (f" (acelerado {fator:.2f}x)" if fator > 1 else ""))
        entradas += ["-i", str(mp3)]
        atraso = int(inicio * 1000)
        filtros.append(f"[{i}:a]aresample=44100,atempo={fator:.4f},"
                       f"adelay={atraso}|{atraso}[t{i}]")
        todas += [Palavra(p.texto, inicio + p.inicio / fator, inicio + p.fim / fator)
                  for p in palavras]
    rotulos = "".join(f"[t{i}]" for i in range(len(trechos)))
    filtros.append(f"{rotulos}amix=inputs={len(trechos)}:normalize=0,"
                   f"apad,atrim=0:{fim_total:.3f}[a]")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *entradas,
                    "-filter_complex", ";".join(filtros), "-map", "[a]",
                    "-ac", "1", str(destino)], check=True)
    return todas

# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description="Gera narração com voz IA em português + vídeo vertical para TikTok.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exemplo:\n  python narrar.py exemplos/polvo.txt -v fundo.mp4 -m musica.mp3",
    )
    ap.add_argument("roteiro", type=Path, help="arquivo .txt com o texto da narração")
    ap.add_argument("-v", "--video", type=Path, help="vídeo de fundo (opcional; repete se for curto)")
    ap.add_argument("-m", "--musica", type=Path, help="música de fundo (opcional)")
    ap.add_argument("-o", "--saida", type=Path, help="arquivo final (padrão: <roteiro>.mp4)")
    ap.add_argument("--voz", default="antonio",
                    help=f"{', '.join(VOZES)} ou o nome completo de uma voz edge-tts (padrão: antonio)")
    ap.add_argument("--velocidade", default="+10%", help="ex.: +0%%, +15%%, -10%% (padrão: +10%%)")
    ap.add_argument("--tom", default="+0Hz", help="ex.: +5Hz, -5Hz (padrão: +0Hz)")
    ap.add_argument("--volume-musica", type=float, default=0.25, help="0 a 1 (padrão: 0.25)")
    ap.add_argument("--manter-audio", action="store_true", help="mantém (baixinho) o som original do vídeo")
    ap.add_argument("--sem-legenda", action="store_true", help="não queima legendas no vídeo")
    ap.add_argument("--palavras-por-legenda", type=int, default=3)
    ap.add_argument("--fonte", default="Arial")
    ap.add_argument("--tamanho-fonte", type=int, default=96)
    ap.add_argument("--altura-legenda", type=int, default=1150,
                    help="posição vertical da legenda, de 0 (topo) a 1920 (padrão: 1150)")
    ap.add_argument("--cor-destaque", default="#FFE600", help="cor da palavra falada (#RRGGBB)")
    ap.add_argument("--cor-fundo", default="#111111", help="cor do fundo quando não há vídeo")
    ap.add_argument("--so-audio", action="store_true", help="gera só o MP3 + legenda .srt (sem vídeo)")
    args = ap.parse_args(argv)

    if not args.roteiro.is_file():
        sys.exit(f"Roteiro não encontrado: {args.roteiro}")
    for arq in (args.video, args.musica):
        if arq and not arq.is_file():
            sys.exit(f"Arquivo não encontrado: {arq}")
    if not shutil.which("ffmpeg") and not args.so_audio:
        sys.exit("ffmpeg não encontrado. Instale-o (veja o README) e tente de novo.")

    conteudo = args.roteiro.read_text(encoding="utf-8")
    trechos = ler_trechos(conteudo)
    texto = " ".join(conteudo.split())
    if trechos and not args.video:
        sys.exit("Roteiro com marcações de tempo precisa de um vídeo (-v).")
    if not texto:
        sys.exit("O roteiro está vazio.")
    voz = VOZES.get(args.voz.lower(), args.voz)
    saida = args.saida or args.roteiro.with_suffix(".mp3" if args.so_audio else ".mp4")

    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp)
        print(f"🎙️  Gerando narração com {voz} ({args.velocidade})...")
        total = None
        if trechos:
            total = duracao(args.video)
            mp3 = pasta / "narracao.wav"
            palavras = narrar_trechos(trechos, total, voz, args.velocidade,
                                      args.tom, pasta, mp3)
        else:
            mp3 = pasta / "narracao.mp3"
            palavras = sintetizar(texto, voz, args.velocidade, args.tom, mp3)

        if args.so_audio:
            if trechos:
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3),
                                "-b:a", "192k", str(saida)], check=True)
            else:
                shutil.copy(mp3, saida)
            gerar_srt(palavras, saida.with_suffix(".srt"), args.palavras_por_legenda)
            print(f"✅ Pronto: {saida} e {saida.with_suffix('.srt')}")
            return

        ass = None
        if not args.sem_legenda:
            ass = pasta / "legenda.ass"
            gerar_ass(palavras, ass, args.palavras_por_legenda, args.fonte,
                      args.tamanho_fonte, args.cor_destaque, args.altura_legenda)

        print("🎬 Montando o vídeo...")
        montar(mp3, saida, pasta, args.video, args.musica, args.volume_musica,
               args.manter_audio, args.cor_fundo, ass, total)
        gerar_srt(palavras, saida.with_suffix(".srt"), args.palavras_por_legenda)

    print(f"✅ Pronto: {saida}  ({duracao(saida):.1f}s)")


if __name__ == "__main__":
    main()
