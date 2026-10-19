#!/usr/bin/env python3
"""Gera o carrossel do LinkedIn (PDF, 1080 x 1350 px, 4:5) a partir de um JSON de conteúdo.

Uso:  python3 scripts/gen_carousel.py [carousel/exemplo-2026-10-09.json] [pasta de saída]
Saída: {pasta de saída}/mindrise-ia-carrossel-{nome}-creme.pdf (+ PNG de cada slide em /tmp/carrossel).
      {nome} é o nome inteiro do JSON, sem a extensão. Sem pasta de saída, grava em assets/03-aplicacoes/social e atualiza
      assets/manifest.json; com pasta de saída (uso do Distribuidor), não toca neste repositório.

Estrutura: capa, 2 slides por notícia (A: manchete e texto; B: "Por que importa" e número), fechamento.
Todo texto vem da edição já revisada. Fontes: Gelasio Bold (no lugar da Georgia) e Liberation Sans (no lugar da Helvetica).
Logo: lockup completo só na capa e no fechamento (mínimo 240 px); nos demais, o ícone aurora (mínimo 64 px).
"""
import html, io, json, pathlib, sys
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from weasyprint import HTML

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOK = json.loads((ROOT / "tokens" / "tokens.json").read_text())
hexof = lambda p: __import__("functools").reduce(lambda n, k: n[k], p.split("."), TOK)["$value"]["hex"]
INK, CREAM, GRAY, RULE = (hexof(f"color.neutral.{k}") for k in ("ink", "cream", "warm-gray", "rule"))
LAV, PLUM_MID, PLUM_DARK = hexof("color.neutral.lavender"), hexof("color.accent.ia.mid"), hexof("color.accent.ia.dark")
IA = ROOT / "assets" / "02-newsletters" / "ia"
TMP = pathlib.Path("/tmp/carrossel"); TMP.mkdir(exist_ok=True)

def gelasio_bold():
    out = TMP / "Gelasio-Bold.ttf"
    if not out.exists():
        f = instancer.instantiateVariableFont(TTFont(str(ROOT / "fonts" / "Gelasio-Variable.ttf")), {"wght": 700})
        f.save(str(out))
    return out

CSS = f"""
@font-face {{ font-family: 'Gel'; src: url('file://{gelasio_bold()}'); font-weight: 700; }}
@font-face {{ font-family: 'Lib'; src: url('file://{ROOT}/fonts/LiberationSans-Regular.ttf'); font-weight: 400; }}
@font-face {{ font-family: 'Lib'; src: url('file://{ROOT}/fonts/LiberationSans-Bold.ttf'); font-weight: 700; }}
@page {{ size: 1080px 1350px; margin: 0 }}
* {{ box-sizing: border-box; margin: 0; padding: 0 }}
body {{ font-family: 'Lib'; color: {INK}; }}
.s {{ position: relative; width: 1080px; height: 1350px; background: {CREAM}; page-break-after: always; overflow: hidden; }}
.top {{ position: absolute; left: 96px; top: 84px; right: 96px; height: 72px; }}
.top img {{ height: 72px; }}
.n {{ position: absolute; right: 0; top: 24px; font-size: 26px; color: {GRAY}; }}
.body {{ position: absolute; left: 96px; right: 96px; top: 240px; bottom: 120px; }}
.label {{ font-weight: 700; font-size: 30px; letter-spacing: 0.2em; text-transform: uppercase; color: {PLUM_DARK}; margin-bottom: 36px; }}
h1 {{ font-family: 'Gel'; font-weight: 700; font-size: 74px; line-height: 1.12; margin-bottom: 52px; }}
p.t {{ font-size: 42px; line-height: 1.5; }}
.pq h1 {{ margin-bottom: 40px; }}
.box {{ margin-top: 20px; background: {LAV}; border-left: 8px solid {PLUM_MID}; border-radius: 6px; padding: 52px 56px; }}
.box b {{ display: block; font-size: 30px; letter-spacing: 0.04em; margin-bottom: 22px; }}
.box p {{ font-size: 40px; line-height: 1.45; }}
.big {{ font-family: 'Gel'; font-weight: 700; font-size: 150px; line-height: 1; color: {PLUM_DARK}; }}
.cap {{ font-size: 32px; line-height: 1.4; color: {GRAY}; margin-top: 18px; max-width: 800px; }}
.cover h1 {{ font-size: 112px; line-height: 1.08; margin-bottom: 0; }}
.cover .logo {{ position: absolute; left: 96px; top: 84px; width: 520px; margin-left: -30px; }}
.cover .mid {{ position: absolute; left: 96px; right: 96px; top: 470px; }}
.cover .label {{ position: absolute; left: 96px; bottom: 120px; margin: 0; }}
.cover .rule {{ position: absolute; left: 96px; bottom: 190px; width: 120px; height: 6px; background: {PLUM_MID}; }}
.end .logo {{ width: 520px; margin-left: -30px; }}
.end h1 {{ font-size: 104px; margin: 250px 0 70px; }}
.end .url {{ font-weight: 700; font-size: 46px; color: {PLUM_DARK}; }}
"""

def img(name):
    return f'file://{IA / name}'

def esc(s):
    return html.escape(s, quote=False)

def chrome(n, total):
    return f'<div class="top"><img src="{img("mindrise-ia-icone-aurora-claro.svg")}"><div class="n">{n}/{total}</div></div>'

def build(c):
    total = 2 + 2 * len(c["noticias"])
    s = []
    s.append(f'<div class="s cover"><img class="logo" src="{img("mindrise-ia-logo-horizontal-claro.svg")}">'
             f'<div class="mid"><h1>{esc(c["capa"]["titulo"])}</h1></div>'
             f'<div class="rule"></div><div class="label">{esc(c["capa"]["rotulo"])}</div></div>')
    n = 2
    for it in c["noticias"]:
        s.append(f'<div class="s">{chrome(n, total)}<div class="body"><div class="label">{esc(it["empresa"])}</div>'
                 f'<h1>{esc(it["manchete"])}</h1><p class="t">{esc(it["texto"])}</p></div></div>')
        n += 1
        num = f'<h1 style="font-size:52px;line-height:1.15">{esc(it["manchete"])}</h1>'
        if it.get("numero"):
            num = (f'<div class="big">{esc(it["numero"]["valor"])}</div>'
                   f'<div class="cap">{esc(it["numero"]["legenda"])}</div>')
        pq = it["por_que_importa"]
        fs = 40 if len(pq) < 300 else 36 if len(pq) < 380 else 32
        s.append(f'<div class="s">{chrome(n, total)}<div class="body pq"><div class="label">{esc(it["empresa"])}</div>{num}'
                 f'<div class="box"><b>Por que importa</b><p style="font-size:{fs}px">{esc(pq)}</p></div></div></div>')
        n += 1
    f = c["fechamento"]
    s.append(f'<div class="s end"><div class="body" style="top:84px"><img class="logo" src="{img("mindrise-ia-logo-horizontal-claro.svg")}">'
             f'<h1>{esc(f["titulo"])}</h1><div class="url">{esc(f["endereco"])}</div></div></div>')
    return f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{''.join(s)}</body></html>"

def main():
    src = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "carousel" / "exemplo-2026-10-09.json"
    name = src.stem
    c = json.loads(src.read_text())
    padrao = ROOT / "assets" / "03-aplicacoes" / "social"
    pasta = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else padrao
    out = pasta / f"mindrise-ia-carrossel-{name}-creme.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=build(c), base_url=str(ROOT)).write_pdf(str(out))
    if pasta != padrao:
        print(out)
        return
    mf = ROOT / "assets" / "manifest.json"
    data = json.loads(mf.read_text()) if mf.exists() else []
    rel = str(out.relative_to(ROOT))
    data = [d for d in data if d.get("arquivo") != rel] + [dict(arquivo=rel, marca="ia", tipo="carrossel", variante=name, fundo="creme", formato="pdf", tamanho="1080x1350")]
    mf.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(out)

if __name__ == "__main__":
    main()
