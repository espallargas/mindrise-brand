#!/usr/bin/env python3
"""Gera o cover de marca da mindrise. (imagem social padrão do site, 1200 x 630 px).

Uso:  python3 scripts/gen_cover_marca.py
Saída: assets/03-aplicacoes/social/mindrise-ia-cover-marca-creme.svg e PNG (1200 e 2400),
       e entradas "cover" (variante "marca") em assets/manifest.json

É a imagem que o beehiiv usa como cartão de compartilhamento (og:image / twitter:image) nas
páginas do site. Não muda por edição: lockup da IA centralizado sobre o creme, com o statement
embaixo. Texto em curvas (Gelasio Bold). Nome do arquivo:
mindrise-{marca}-cover-marca-{fundo}[-{tamanho}].{ext}
"""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_logo as g  # noqa: E402

ROOT = g.ROOT
OUT = ROOT / "assets" / "03-aplicacoes" / "social"
W, H = 1200, 630

LOCK_W = 760.0  # largura visível do lockup (px); legível em miniatura no WhatsApp
STATEMENT = "As notícias de IA que importam, em 5 minutos."
TEXT_SIZE = 32
GAP = 56  # espaço entre o lockup e o statement


def build(brand="ia"):
    pal = g.palette(brand, "light")
    vx, vy, vw, vh = g.LOCKUP_VB[0] + g.CLEAR, g.LOCKUP_VB[1] + g.CLEAR, g.LOCKUP_VB[2] - 2 * g.CLEAR, g.LOCKUP_VB[3] - 2 * g.CLEAR
    s = LOCK_W / vw
    lock_h = vh * s

    cap = TEXT_SIZE * 0.72
    block_h = lock_h + GAP + cap
    top = (H - block_h) / 2

    body = [f'<rect width="{W}" height="{H}" fill="{g.CREAM}"/>']
    lx = (W - LOCK_W) / 2
    body.append(f'<g transform="translate({g.fmt(lx - vx * s)},{g.fmt(top - vy * s)}) scale({g.fmt(s)})">{g.lockup(brand, pal)}</g>')

    glyphs = g.shape(g.FONT_WORDMARK, 700, STATEMENT, TEXT_SIZE, 0, 0)
    text_w = max(b[2] for _, b in glyphs if b)
    tx = (W - text_w) / 2
    base = top + lock_h + GAP + cap
    for d, _ in g.shape(g.FONT_WORDMARK, 700, STATEMENT, TEXT_SIZE, tx, base):
        body.append(f'<path d="{d}" fill="{g.INK}"/>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img">'
            f'<title>mindrise. IA, cover de marca</title>{"".join(body)}</svg>')


def main():
    svg = build("ia")
    OUT.mkdir(parents=True, exist_ok=True)
    name = "mindrise-ia-cover-marca-creme"
    (OUT / f"{name}.svg").write_text(svg)
    rel = lambda p: str(p.relative_to(ROOT))
    entries = [dict(arquivo=rel(OUT / f"{name}.svg"), formato="svg", tamanho="vetor")]
    for w in (W, W * 2):
        p = OUT / f"{name}-{w}.png"
        g.cairosvg.svg2png(bytestring=svg.encode(), write_to=str(p), output_width=w)
        entries.append(dict(arquivo=rel(p), formato="png", tamanho=str(w)))
    for e in entries:
        e.update(marca="ia", tipo="cover", variante="marca", fundo="creme")

    mf = ROOT / "assets" / "manifest.json"
    data = json.loads(mf.read_text()) if mf.exists() else []
    data = [d for d in data if not d["arquivo"].startswith(f"assets/03-aplicacoes/social/{name}")] + entries
    mf.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(name)


if __name__ == "__main__":
    main()
