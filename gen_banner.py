#!/usr/bin/env python3
"""Gera banners de redes da mindrise. a partir dos tokens e do gerador de logo.

Uso:  python3 scripts/gen_banner.py
Saída: assets/03-aplicacoes/social/ (SVG mestre + PNG), e entradas "banner" em assets/manifest.json

Cada rede tem composição própria (decisão de 15/10). Hoje: LinkedIn (página da empresa).
Texto sempre em curvas (Gelasio Bold). Nome do arquivo:
mindrise-{marca}-banner-{rede}-{fundo}[-{tamanho}].{ext}
"""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_logo as g  # noqa: E402  (importa tokens, fontes e lockup sem regerar os assets)

ROOT = g.ROOT
OUT = ROOT / "assets" / "03-aplicacoes" / "social"
RULE = g.hexof("color.neutral.rule")

# --- LinkedIn, página da empresa: 1512 x 256 (mesma proporção 5,9:1 do 1128 x 191 anterior) ---
W, H = 1512, 256
# Zonas, escaladas de 1128 x 191: logo da página cobre o canto inferior esquerdo (0-402 x 94-256);
# o miolo seguro fica em x 153-1359 e y 28-228.
SAFE_X0, SAFE_X1, SAFE_Y0, SAFE_Y1 = 460, 1359, 40, 216

STATEMENT = ["As notícias de IA que importam,", "todo dia, em 5 minutos."]
TEXT_SIZE = 26
LEAD = 37


def lockup_visible(brand="ia"):
    """Caixa visível do lockup (sem a zona de proteção), em unidades de em = 360."""
    x, y, w, h = g.LOCKUP_VB
    return (x + g.CLEAR, y + g.CLEAR, w - 2 * g.CLEAR, h - 2 * g.CLEAR)


def linkedin(brand="ia"):
    pal = g.palette(brand, "light")
    vx, vy, vw, vh = lockup_visible(brand)
    lock_h = 66.0  # altura visível do lockup no banner (px)
    s = lock_h / vh
    lock_w = vw * s

    # texto
    lines = []
    for i, line in enumerate(STATEMENT):
        lines.append((line, i))
    text_h = TEXT_SIZE * 0.72 + LEAD * (len(STATEMENT) - 1)  # altura de cap + entrelinhas

    # bloco: lockup | filete | texto, centralizado na faixa segura vertical
    gap = 36
    text_w = max(
        max(b[2] for _, b in g.shape(g.FONT_WORDMARK, 700, line, TEXT_SIZE, 0, 0) if b) for line in STATEMENT
    )
    block_w = lock_w + gap + 1 + gap + text_w
    x0 = SAFE_X1 - block_w  # alinha o bloco à direita da faixa segura
    cy = (SAFE_Y0 + SAFE_Y1) / 2

    body = [f'<rect width="{W}" height="{H}" fill="{g.CREAM}"/>']
    # lockup
    ty = cy - lock_h / 2 - vy * s
    body.append(f'<g transform="translate({g.fmt(x0 - vx * s)},{g.fmt(ty)}) scale({g.fmt(s)})">{g.lockup(brand, pal)}</g>')
    # filete
    rx = x0 + lock_w + gap
    body.append(f'<rect x="{g.fmt(rx)}" y="{g.fmt(cy - 36)}" width="1.5" height="72" fill="{RULE}"/>')
    # texto
    tx = rx + 1 + gap
    first_base = cy - text_h / 2 + TEXT_SIZE * 0.72
    for line, i in lines:
        for d, _ in g.shape(g.FONT_WORDMARK, 700, line, TEXT_SIZE, tx, first_base + LEAD * i):
            body.append(f'<path d="{d}" fill="{g.INK}"/>')
    return "".join(body), (x0, x0 + block_w)


def emit(name, svg, widths):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.svg").write_text(svg)
    rel = lambda p: str(p.relative_to(ROOT))
    entries = [dict(arquivo=rel(OUT / f"{name}.svg"), formato="svg", tamanho="vetor")]
    for w in widths:
        p = OUT / f"{name}-{w}.png"
        g.cairosvg.svg2png(bytestring=svg.encode(), write_to=str(p), output_width=w)
        entries.append(dict(arquivo=rel(p), formato="png", tamanho=str(w)))
    return entries


def main():
    body, span = linkedin("ia")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img">'
           f'<title>mindrise. IA, banner LinkedIn</title>{body}</svg>')
    entries = emit("mindrise-ia-banner-linkedin-creme", svg, (W, W * 2))
    for e in entries:
        e.update(marca="ia", tipo="banner", variante="linkedin", fundo="creme")

    mf = ROOT / "assets" / "manifest.json"
    data = json.loads(mf.read_text()) if mf.exists() else []
    data = [d for d in data if d.get("tipo") != "banner"] + entries
    mf.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"banner LinkedIn: bloco de x={span[0]:.0f} a x={span[1]:.0f} (faixa segura {SAFE_X0}-{SAFE_X1})")


if __name__ == "__main__":
    main()
