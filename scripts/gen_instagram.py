#!/usr/bin/env python3
"""Gera o carrossel (1080 x 1440, 3:4) e o story (1080 x 1920, 9:16) do Instagram a partir de um JSON de conteúdo.

Uso:  python3 scripts/gen_instagram.py [instagram/exemplo-2026-10-30.json] [pasta de saída]
Saída: {pasta}/mindrise-ia-instagram-{nome}-{n}.jpg (um por slide) e {pasta}/mindrise-ia-story-{nome}.jpg.
      {nome} é o nome do JSON sem a extensão (no Distributor, a data AAAA-MM-DD).
      Sem pasta de saída, grava em /tmp/instagram e não toca neste repositório.

Estrutura (regras na página Aplicações do Brand book, seção "Instagram"):
  1. capa: faixa da marca (logo e frase) em cima, manchete da principal embaixo (geometria fixa em CAPA;
     "rotulo" opcional na capa, padrão "Hoje na mindrise", para posts do perfil como a apresentação);
  2. slides do miolo, um fato por slide: "texto" (rótulo, título, parágrafos) ou "numero" (rótulo, número grande, legenda, parágrafos);
  3. "Por que importa" da principal;
  4. "Também na edição de hoje", com as outras manchetes e a faixa de chamada para o link na bio.
Área livre: os últimos 160 px de cada slide ficam sem texto, porque o Instagram sobrepõe ali as fotos de quem curtiu ou repostou.
A faixa alterna entre ameixa-dark e lavanda (campo "faixa"); no ameixa-mid o ponto do logo some, por isso ele não entra.
Sem contador de slides: o Instagram já mostra a posição.
Fontes: Gelasio Bold (no lugar da Georgia) e Liberation Sans (no lugar da Helvetica). Precisa de weasyprint e pymupdf.
"""
import html, json, pathlib, sys
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from weasyprint import HTML

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOK = json.loads((ROOT / "tokens" / "tokens.json").read_text())
hexof = lambda p: __import__("functools").reduce(lambda n, k: n[k], p.split("."), TOK)["$value"]["hex"]
INK, CREAM, GRAY, RULE = (hexof(f"color.neutral.{k}") for k in ("ink", "cream", "warm-gray", "rule"))
LAV, MID, DARK, LIGHT = (hexof("color.neutral.lavender"), hexof("color.accent.ia.mid"),
                         hexof("color.accent.ia.dark"), hexof("color.accent.ia.light"))
IA = ROOT / "assets" / "02-newsletters" / "ia"
TMP = pathlib.Path("/tmp/instagram-build"); TMP.mkdir(exist_ok=True)

FRASE = "As notícias de IA que importam, nos dias úteis, em 5 minutos."
CHAMADA = "Receba a mindrise nos dias úteis, em 5 minutos."
# faixa: (fundo, logo, cor da frase, cor do texto da chamada, cor da linha "Link na bio")
FAIXAS = {
    "ameixa-dark": (DARK, "mindrise-ia-logo-horizontal-escuro.svg", LAV, CREAM, LAV),
    "lavanda": (LAV, "mindrise-ia-logo-horizontal-claro.svg", GRAY, INK, DARK),
}
LIMITE = 330  # caracteres por slide do miolo; acima disso o texto pode não caber

def gelasio_bold():
    out = TMP / "Gelasio-Bold.ttf"
    if not out.exists():
        instancer.instantiateVariableFont(TTFont(str(ROOT / "fonts" / "Gelasio-Variable.ttf")), {"wght": 700}).save(str(out))
    return out

def css(h):
    return f"""
@font-face {{ font-family: 'Gel'; src: url('file://{gelasio_bold()}'); font-weight: 700; }}
@font-face {{ font-family: 'Lib'; src: url('file://{ROOT}/fonts/LiberationSans-Regular.ttf'); font-weight: 400; }}
@font-face {{ font-family: 'Lib'; src: url('file://{ROOT}/fonts/LiberationSans-Bold.ttf'); font-weight: 700; }}
@page {{ size: 1080px {h}px; margin: 0 }}
* {{ box-sizing: border-box; margin: 0; padding: 0 }}
body {{ font-family: 'Lib'; color: {INK}; }}
.s {{ position: relative; width: 1080px; height: {h}px; background: {CREAM}; page-break-after: always; overflow: hidden; }}
.top {{ position: absolute; left: 96px; top: 96px; height: 72px; }}
.top img {{ height: 72px; }}
.body {{ position: absolute; left: 96px; right: 96px; top: 300px; }}
.label {{ font-weight: 700; font-size: 30px; letter-spacing: 0.2em; text-transform: uppercase; color: {DARK}; margin-bottom: 40px; }}
h2 {{ font-family: 'Gel'; font-weight: 700; font-size: 76px; line-height: 1.12; margin-bottom: 56px; }}
p.t {{ font-size: 44px; line-height: 1.5; margin-bottom: 36px; }}
.big {{ font-family: 'Gel'; font-weight: 700; font-size: 220px; line-height: 1; color: {DARK}; }}
.cap {{ font-size: 40px; line-height: 1.4; color: {GRAY}; margin: 16px 0 70px; }}
.box {{ background: {LAV}; border-left: 8px solid {MID}; border-radius: 6px; padding: 60px; }}
.box b {{ display: block; font-size: 32px; letter-spacing: 0.04em; margin-bottom: 26px; }}
.box p {{ font-size: 43px; line-height: 1.5; }}
.band {{ position: absolute; left: 0; right: 0; top: 0; }}
.cv .logo {{ position: absolute; left: 66px; width: 640px; }}
.cv .fr {{ position: absolute; left: 96px; right: 160px; font-size: 40px; line-height: 1.35; }}
.cv .label {{ position: absolute; left: 96px; margin: 0; }}
.cv h1 {{ position: absolute; left: 96px; right: 96px; font-family: 'Gel'; font-weight: 700; line-height: 1.1; }}
.end ul {{ list-style: none; }}
.end .body {{ top: 260px; }}
.end li {{ font-family: 'Gel'; font-weight: 700; font-size: 50px; line-height: 1.18; padding: 30px 0; border-top: 2px solid {RULE}; }}
.cta {{ position: absolute; left: 0; right: 0; bottom: 0; height: 480px; padding: 80px 96px 0; }}
.cta .a {{ font-family: 'Gel'; font-weight: 700; font-size: 66px; line-height: 1.15; }}
.cta .b {{ font-size: 36px; margin-top: 24px; }}
"""

e = lambda s: html.escape(s, quote=False)

def chrome():
    return f'<div class="top"><img src="file://{IA}/mindrise-ia-icone-aurora-claro.svg"></div>'

# Geometria única da capa. Todo post do perfil (edição diária, apresentação, destaque) sai daqui, para a grade ficar alinhada.
# Não mude estes números sem regerar os posts fixados: a grade mistura posts antigos e novos.
CAPA = {"band": 520, "ltop": 100, "ftop": 320, "labtop": 610, "htop": 670, "hsize": 84}
# story: tudo desce (o topo da tela fica sob a barra do perfil) e sobra espaço embaixo para o adesivo de link
STORY = {"band": 780, "ltop": 300, "ftop": 540, "labtop": 870, "htop": 930, "hsize": 82}

def capa(c, faixa, story=False):
    bg, logo, fr, _, _ = FAIXAS[faixa]
    g = STORY if story else CAPA
    band, ltop, ftop, labtop, htop, hsize = (g[k] for k in ("band", "ltop", "ftop", "labtop", "htop", "hsize"))
    rotulo = c.get("rotulo", "Hoje na mindrise")
    return (f'<div class="s cv"><div class="band" style="height:{band}px;background:{bg}"></div>'
            f'<img class="logo" style="top:{ltop}px" src="file://{IA}/{logo}">'
            f'<div class="fr" style="top:{ftop}px;color:{fr}">{e(FRASE)}</div>'
            f'<div class="label" style="top:{labtop}px">{e(rotulo)}</div>'
            f'<h1 style="top:{htop}px;font-size:{hsize}px">{e(c["manchete"])}</h1></div>')

def miolo(sl):
    ps = "".join(f'<p class="t">{e(p)}</p>' for p in sl.get("paragrafos", []))
    if sl["tipo"] == "numero":
        head = f'<div class="big">{e(sl["valor"])}</div><div class="cap">{e(sl["legenda"])}</div>'
    else:
        head = f'<h2>{e(sl["titulo"])}</h2>'
    return f'<div class="s">{chrome()}<div class="body"><div class="label">{e(sl["rotulo"])}</div>{head}{ps}</div></div>'

def tamanho(sl):
    return sum(len(sl.get(k, "")) for k in ("titulo", "valor", "legenda")) + sum(len(p) for p in sl.get("paragrafos", []))

def build(c, faixa):
    _, _, _, cta_a, cta_b = FAIXAS[faixa]
    bg = FAIXAS[faixa][0]
    s = [capa(c["capa"], faixa)]
    s += [miolo(sl) for sl in c["miolo"]]
    pq = c["por_que_importa"]
    s.append(f'<div class="s">{chrome()}<div class="body"><div class="label">{e(pq["rotulo"])}</div>'
             f'<div class="box"><b>Por que importa</b><p>{e(pq["texto"])}</p></div></div></div>')
    lis = "".join(f"<li>{e(m)}</li>" for m in c["tambem"])
    s.append(f'<div class="s end">{chrome()}<div class="body"><div class="label">Também na edição de hoje</div><ul>{lis}</ul></div>'
             f'<div class="cta" style="background:{bg}"><div class="a" style="color:{cta_a}">{e(CHAMADA)}</div>'
             f'<div class="b" style="color:{cta_b}">Link na bio</div></div></div>')
    return f"<html><head><meta charset='utf-8'><style>{css(1440)}</style></head><body>{''.join(s)}</body></html>"

def jpgs(pdf, nomes):
    import pymupdf as fitz
    doc = fitz.open(str(pdf))
    if len(doc) != len(nomes):
        sys.exit(f"ERRO: o PDF tem {len(doc)} páginas, esperava {len(nomes)}")
    for page, nome in zip(doc, nomes):
        pix = page.get_pixmap(dpi=96)  # 1 px CSS = 1 px de imagem
        pix.save(str(nome), jpg_quality=90)

def main():
    src = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "instagram" / "exemplo-2026-10-30.json"
    pasta = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path("/tmp/instagram")
    pasta.mkdir(parents=True, exist_ok=True)
    nome = src.stem
    c = json.loads(src.read_text())
    faixa = c.get("faixa", "ameixa-dark")
    if faixa not in FAIXAS:
        sys.exit(f"ERRO: faixa '{faixa}' inválida; use {', '.join(FAIXAS)}")
    if not 1 <= len(c["miolo"]) <= 3:
        sys.exit("ERRO: o miolo tem de 1 a 3 slides")
    if not 1 <= len(c["tambem"]) <= 2:
        sys.exit("ERRO: 'tambem' tem 1 ou 2 manchetes")
    for i, sl in enumerate(c["miolo"], 2):
        if tamanho(sl) > LIMITE:
            print(f"AVISO: o slide {i} tem {tamanho(sl)} caracteres (limite {LIMITE}); confira se o texto coube")
    if len(c["por_que_importa"]["texto"]) > 420:
        print("AVISO: o 'Por que importa' passa de 420 caracteres; confira se coube")

    pdf = TMP / f"{nome}.pdf"
    HTML(string=build(c, faixa), base_url=str(ROOT)).write_pdf(str(pdf))
    total = 1 + len(c["miolo"]) + 2
    saidas = [pasta / f"mindrise-ia-instagram-{nome}-{n}.jpg" for n in range(1, total + 1)]
    jpgs(pdf, saidas)

    spdf = TMP / f"{nome}-story.pdf"
    HTML(string=f"<html><head><meta charset='utf-8'><style>{css(1920)}</style></head><body>{capa(c['capa'], faixa, story=True)}</body></html>",
         base_url=str(ROOT)).write_pdf(str(spdf))
    story = pasta / f"mindrise-ia-story-{nome}.jpg"
    jpgs(spdf, [story])
    for p in saidas + [story]:
        print(p)

if __name__ == "__main__":
    main()
