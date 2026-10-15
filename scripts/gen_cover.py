#!/usr/bin/env python3
"""Gera capas de post (imagem única, 1200 x 627 px) a partir de um JSON de uma notícia.

Uso:  python3 scripts/gen_cover.py cover/exemplo-2026-10-14.json [pasta de saída]
Variantes: manchete (creme), numero (creme, número grande), escuro (tinta, manchete).
Texto em curvas (Gelasio Bold, Liberation Sans). Todo texto vem da edição já revisada.
"""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_logo as g

W, H, M = 1200, 627, 72
REG = g.ROOT / "fonts" / "LiberationSans-Regular.ttf"
PLUM_DARK, PLUM_LIGHT = g.hexof("color.accent.ia.dark"), g.hexof("color.accent.ia.light")
GRAY = g.hexof("color.neutral.warm-gray")

def width(font, wght, text, size, tracking=0):
    gl = g.shape(font, wght, text, size, 0, 0, tracking)
    return max((b[2] for _, b in gl if b), default=0)

def wrap(font, wght, text, size, max_w):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if width(font, wght, t, size) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    return lines + [cur]

def paths(font, wght, text, size, x, y, color, tracking=0):
    return "".join(f'<path d="{d}" fill="{color}"/>' for d, _ in g.shape(font, wght, text, size, x, y, tracking))

def lockup_at(mode, x, y_bottom, h):
    vx, vy, vw, vh = g.LOCKUP_VB[0] + g.CLEAR, g.LOCKUP_VB[1] + g.CLEAR, g.LOCKUP_VB[2] - 2 * g.CLEAR, g.LOCKUP_VB[3] - 2 * g.CLEAR
    s = h / vh
    pal = g.palette("ia", mode)
    return (f'<g transform="translate({g.fmt(x - vx * s)},{g.fmt(y_bottom - h - vy * s)}) scale({g.fmt(s)})">{g.lockup("ia", pal)}</g>', vw * s)

def label(text, color, y=M + 22):
    _, _, upem, cap = g.load_font(g.FONT_LABEL)
    size = 24 / (cap / upem)
    return paths(g.FONT_LABEL, None, text, size, M, y, color, tracking=0.2 * size)

def build(c, variante):
    dark = variante == "escuro"
    bg, ink, accent, sub = (g.INK, g.CREAM, PLUM_LIGHT, g.CREAM) if dark else (g.CREAM, g.INK, PLUM_DARK, GRAY)
    body = [f'<rect width="{W}" height="{H}" fill="{bg}"/>', label(c["empresa"], accent)]
    if variante == "numero":
        n = c["numero"]
        body.append(paths(g.FONT_WORDMARK, 700, n["valor"], 190, M - 6, 300, accent))
        for i, ln in enumerate(wrap(REG, None, n["legenda"], 36, 900)):
            body.append(paths(REG, None, ln, 36, M, 385 + i * 48, ink))
    else:
        size = 70
        lines = wrap(g.FONT_WORDMARK, 700, c["manchete"], size, W - 2 * M)
        while len(lines) > 4:
            size -= 4; lines = wrap(g.FONT_WORDMARK, 700, c["manchete"], size, W - 2 * M)
        for i, ln in enumerate(lines):
            body.append(paths(g.FONT_WORDMARK, 700, ln, size, M, 190 + i * size * 1.18, ink))
    lk, _ = lockup_at("dark" if dark else "light", M, H - M, 60)
    body.append(lk)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">{"".join(body)}</svg>'

def main():
    c = json.loads(pathlib.Path(sys.argv[1]).read_text())
    out = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else g.ROOT / "assets" / "03-aplicacoes" / "social"
    out.mkdir(parents=True, exist_ok=True)
    for v in ("manchete", "numero", "escuro"):
        svg = build(c, v)
        stem = out / f"mindrise-ia-capa-{pathlib.Path(sys.argv[1]).stem}-{v}"
        stem.with_suffix(".svg").write_text(svg)
        g.cairosvg.svg2png(bytestring=svg.encode(), write_to=str(stem) + "-1200.png", output_width=W)
        g.cairosvg.svg2png(bytestring=svg.encode(), write_to=str(stem) + "-2400.png", output_width=W * 2)
        print(stem.name)
        if out == g.ROOT / "assets" / "03-aplicacoes" / "social":
            mf = g.ROOT / "assets" / "manifest.json"
            data = json.loads(mf.read_text()) if mf.exists() else []
            nome = pathlib.Path(sys.argv[1]).stem
            novos = [dict(arquivo=str(f.relative_to(g.ROOT)), marca="ia", tipo="capa", variante=v, fundo="tinta" if v == "escuro" else "creme",
                          formato=f.suffix[1:], tamanho="vetor" if f.suffix == ".svg" else f.stem.split("-")[-1])
                     for f in sorted(out.glob(f"mindrise-ia-capa-{nome}-{v}*"))]
            data = [d for d in data if not d["arquivo"].startswith(f"assets/03-aplicacoes/social/mindrise-ia-capa-{nome}-{v}")] + novos
            mf.write_text(json.dumps(data, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
