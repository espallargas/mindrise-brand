#!/usr/bin/env python3
"""Gera o conjunto núcleo de logos da mindrise. a partir de tokens/tokens.json.

Uso:  python3 scripts/gen_logo.py
Saída: assets/ (SVG mestre + PNG derivados), assets/manifest.json

Regra: o SVG é a fonte; PNG é derivado. Texto sempre em curvas (Gelasio Bold e Liberation Sans Bold).
Nome do arquivo: mindrise-{marca}-{tipo}-{variante}-{fundo}[-{tamanho}].{ext}
"""
import io, json, pathlib
import uharfbuzz as hb
import cairosvg
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOK = json.loads((ROOT / "tokens" / "tokens.json").read_text())
FONT_WORDMARK = ROOT / "fonts" / "Gelasio-Variable.ttf"
FONT_LABEL = ROOT / "fonts" / "LiberationSans-Bold.ttf"

# ---------- tokens ----------
def hexof(path):
    n = TOK
    for p in path.split("."):
        n = n[p]
    return n["$value"]["hex"]

def num(name):
    return TOK["geometry"][name]["$value"]

EM = 360.0
U = EM / num("u-per-em")
INK, CREAM = hexof("color.neutral.ink"), hexof("color.neutral.cream")
BAR_W, BAR_H, BAR_R = num("bar-width-u") * U, num("bar-height-u") * U, num("bar-radius-u") * U
ARCS3 = [r * U for r in num("arc-radii-u")]
ARCS2 = [r * U for r in num("arc-radii-compact-u")]
GAP, CLEAR = num("icon-gap-u") * U, num("clear-space-u") * U
SQ, SQ_R = num("square-size-u") * U, num("square-radius-u") * U
LAB_CAP, LAB_TOP, LAB_TRK = num("label-cap-u") * U, num("label-top-offset-u") * U, num("label-tracking-em")

BRANDS = {  # chave -> (rótulo, pasta)
    "mae": (None, "01-nucleo"),
    "ia": ("IA", "02-newsletters/ia"),
    "tech": ("TECH", "02-newsletters/tech"),
}

def accent(brand):
    key = "mother" if brand == "mae" else brand
    return {k: hexof(f"color.accent.{key}.{k}") for k in ("light", "mid", "dark", "lightest")}

def palette(brand, mode):
    """mode: 'light' (para fundos claros) ou 'dark' (para fundos escuros)."""
    a = accent(brand)
    ink = INK if mode == "light" else CREAM
    # claro: light, mid, dark (de fora para dentro). Escuro: mid, light, lightest (o miolo é o tom mais forte).
    arcs = (a["light"], a["mid"], a["dark"]) if mode == "light" else (a["mid"], a["light"], a["lightest"])
    if brand == "mae":
        dot = arcs[1]
        label = None
    else:
        dot = a["mid"]
        label = a["mid"] if mode == "light" else a["light"]
    return dict(arcs=arcs, bar=ink, word=ink, dot=dot, label=label, opac=(1, 1, 1))

def mono(color):
    return dict(arcs=(color,) * 3, bar=color, word=color, dot=color, label=color, opac=(0.35, 0.65, 1))

# ---------- fontes ----------
_cache = {}
def load_font(path, wght=None):
    k = (str(path), wght)
    if k in _cache:
        return _cache[k]
    f = TTFont(str(path))
    if wght:
        f = instancer.instantiateVariableFont(f, {"wght": wght})
    b = io.BytesIO(); f.save(b); data = b.getvalue()
    tt = TTFont(io.BytesIO(data))
    r = (tt, hb.Font(hb.Face(data)), tt["head"].unitsPerEm, tt["OS/2"].sCapHeight)
    _cache[k] = r
    return r

def shape(path, wght, text, size, x0, y0, tracking=0.0, ink_left=False):
    """Retorna lista de (d, bounds_ink) por glifo, e o x final (ink)."""
    tt, font, upem, _ = load_font(path, wght)
    buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
    hb.shape(font, buf, {"kern": True})
    gs, order = tt.getGlyphSet(), tt.getGlyphOrder()
    sc = size / upem
    x, out, shift = x0, [], 0.0
    for i, (info, pos) in enumerate(zip(buf.glyph_infos, buf.glyph_positions)):
        g = gs[order[info.codepoint]]
        bp = BoundsPen(gs); g.draw(bp)
        if i == 0 and ink_left and bp.bounds:
            shift = -bp.bounds[0] * sc
        ox = x + shift + pos.x_offset * sc
        sp = SVGPathPen(gs)
        g.draw(TransformPen(sp, (sc, 0, 0, -sc, ox, y0)))
        b = None
        if bp.bounds:
            b = (ox + bp.bounds[0] * sc, y0 - bp.bounds[3] * sc, ox + bp.bounds[2] * sc, y0 - bp.bounds[1] * sc)
        out.append((sp.getCommands(), b))
        x += pos.x_advance * sc + tracking
    return out

# ---------- peças ----------
def fmt(v):
    return f"{v:.3f}".rstrip("0").rstrip(".")

def icon_svg(x, base, pal, arcs=3):
    """Ícone com a barra apoiada em y=base e x de início = x."""
    cx, cy = x + BAR_W / 2, base - BAR_H
    radii = ARCS3 if arcs == 3 else ARCS2
    parts = []
    for r, col, op in zip(radii, pal["arcs"], pal["opac"]):
        o = f' fill-opacity="{op}"' if op != 1 else ""
        parts.append(f'<path d="M{fmt(cx-r)},{fmt(cy)} A{fmt(r)},{fmt(r)} 0 0 1 {fmt(cx+r)},{fmt(cy)} Z" fill="{col}"{o}/>')
    parts.append(f'<rect x="{fmt(x)}" y="{fmt(cy)}" width="{fmt(BAR_W)}" height="{fmt(BAR_H)}" rx="{fmt(BAR_R)}" fill="{pal["bar"]}"/>')
    return "".join(parts)

def wrap(body, vb, bg=None, title=""):
    x, y, w, h = vb
    r = f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" fill="{bg}"/>' if bg else ""
    t = f"<title>{title}</title>" if title else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{fmt(x)} {fmt(y)} {fmt(w)} {fmt(h)}" '
            f'width="{fmt(w)}" height="{fmt(h)}" role="img">{t}{r}{body}</svg>')

# viewBox compartilhada por todos os lockups (inclui a faixa da etiqueta), para o wordmark não pular entre marcas
def lockup_geometry():
    x_text = BAR_W + GAP
    glyphs = shape(FONT_WORDMARK, 700, "mindrise.", EM, x_text, 0)
    top = min(b[1] for _, b in glyphs if b)
    right = max(b[2] for _, b in glyphs if b)
    bottom = LAB_TOP + LAB_CAP
    return x_text, (-CLEAR, top - CLEAR, right + 2 * CLEAR, bottom - top + 2 * CLEAR)

X_TEXT, LOCKUP_VB = lockup_geometry()

def lockup(brand, pal):
    word = shape(FONT_WORDMARK, 700, "mindrise.", EM, X_TEXT, 0)
    body = icon_svg(0, 0, pal)
    for i, (d, _) in enumerate(word):
        col = pal["dot"] if i == len(word) - 1 else pal["word"]
        body += f'<path d="{d}" fill="{col}"/>'
    label, _folder = BRANDS[brand]
    if label:
        _, _, upem, cap = load_font(FONT_LABEL)
        size = LAB_CAP / (cap / upem)
        for d, _ in shape(FONT_LABEL, None, label, size, X_TEXT, LAB_TOP + LAB_CAP, tracking=LAB_TRK * size, ink_left=True):
            body += f'<path d="{d}" fill="{pal["label"]}"/>'
    return body

def icon_only(pal, arcs=3):
    vb = (-CLEAR, -(BAR_H + ARCS3[0]) - CLEAR, BAR_W + 2 * CLEAR, BAR_H + ARCS3[0] + 2 * CLEAR)
    return icon_svg(0, 0, pal, arcs), vb

def square(pal, bg, arcs=3, radius=SQ_R):
    ic_h = BAR_H + ARCS3[0]
    base = (SQ + ic_h) / 2
    body = f'<rect width="{fmt(SQ)}" height="{fmt(SQ)}" rx="{fmt(radius)}" fill="{bg}"/>' + icon_svg((SQ - BAR_W) / 2, base, pal, arcs)
    return body, (0, 0, SQ, SQ)

# ---------- saída ----------
MANIFEST = []

def emit(brand, tipo, variante, fundo, body, vb, bg=None, png_widths=(), title=""):
    folder = ROOT / "assets" / BRANDS[brand][1]
    folder.mkdir(parents=True, exist_ok=True)
    base = f"mindrise-{brand}-{tipo}-{variante}-{fundo}"
    svg = wrap(body, vb, bg, title)
    (folder / f"{base}.svg").write_text(svg)
    rel = lambda p: str(p.relative_to(ROOT))
    MANIFEST.append(dict(arquivo=rel(folder / f"{base}.svg"), marca=brand, tipo=tipo, variante=variante, fundo=fundo, formato="svg", tamanho="vetor"))
    for w in png_widths:
        p = folder / f"{base}-{w}.png"
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(p), output_width=w)
        MANIFEST.append(dict(arquivo=rel(p), marca=brand, tipo=tipo, variante=variante, fundo=fundo, formato="png", tamanho=str(w)))

def build():
    for brand in BRANDS:
        title = "mindrise." if brand == "mae" else f"mindrise. {BRANDS[brand][0]}"
        light, dark = palette(brand, "light"), palette(brand, "dark")
        # logo horizontal: transparente (claro/escuro), com fundo (creme/tinta), monocromático
        emit(brand, "logo", "horizontal", "claro", lockup(brand, light), LOCKUP_VB, None, (2400,), title)
        emit(brand, "logo", "horizontal", "escuro", lockup(brand, dark), LOCKUP_VB, None, (2400,), title)
        emit(brand, "logo", "horizontal", "creme", lockup(brand, light), LOCKUP_VB, CREAM, (2400,), title)
        emit(brand, "logo", "horizontal", "tinta", lockup(brand, dark), LOCKUP_VB, INK, (2400,), title)
        emit(brand, "logo", "horizontal", "mono-preto", lockup(brand, mono(INK)), LOCKUP_VB, None, (), title)
        emit(brand, "logo", "horizontal", "mono-branco", lockup(brand, mono("#FFFFFF")), LOCKUP_VB, None, (), title)
        # ícone
        for fundo, pal in (("claro", light), ("escuro", dark)):
            b, vb = icon_only(pal)
            emit(brand, "icone", "aurora", fundo, b, vb, None, (1024,), title)
        # avatar quadrado (3 arcos, cantos 3u) e avatar pleno (sem cantos, para upload em redes que recortam)
        for fundo, pal, bg in (("claro", light, CREAM), ("escuro", dark, INK)):
            b, vb = square(pal, bg)
            emit(brand, "avatar", "quadrado", fundo, b, vb, None, (1024, 512), title)
            b, vb = square(pal, bg, radius=0)
            emit(brand, "avatar", "pleno", fundo, b, vb, None, (1024,), title)
        # favicons: compacto (2 arcos) de 16 a 63 px; 3 arcos a partir de 64 px
        for fundo, pal, bg in (("claro", light, CREAM), ("escuro", dark, INK)):
            b, vb = square(pal, bg, arcs=2)
            emit(brand, "favicon", "compacto", fundo, b, vb, None, (16, 32, 48), title)
            b, vb = square(pal, bg, arcs=3)
            emit(brand, "favicon", "padrao", fundo, b, vb, None, (180,), title)
    (ROOT / "assets" / "manifest.json").write_text(json.dumps(MANIFEST, indent=2, ensure_ascii=False))
    print(f"{len(MANIFEST)} arquivos gerados")

if __name__ == "__main__":
    build()
