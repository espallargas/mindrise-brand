#!/usr/bin/env python3
"""Gera docs/showcase.png (folha de logos) e docs/palette.png (paleta) a partir de assets/ e tokens/.
Rode depois de scripts/gen_logo.py.   Requer: pillow, cairosvg
"""
import json, pathlib
from PIL import Image, ImageDraw, ImageFont
import cairosvg

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOK = json.loads((ROOT / "tokens" / "tokens.json").read_text())
FONT = str(ROOT / "fonts" / "LiberationSans-Bold.ttf")
FOLDERS = {"mae": "01-nucleo", "ia": "02-newsletters/ia", "tech": "02-newsletters/tech"}
NAMES = {"mae": "Marca-mãe", "ia": "Newsletter de IA", "tech": "Newsletter de tech (provisória)"}

def png(brand, name):
    return Image.open(ROOT / "assets" / FOLDERS[brand] / f"mindrise-{brand}-{name}.png").convert("RGBA")

def showcase():
    W, rowh = 2400, 560
    sheet = Image.new("RGBA", (W, rowh * 3 + 40), (255, 255, 255, 255))
    f = ImageFont.truetype(FONT, 30); d = ImageDraw.Draw(sheet)
    for i, b in enumerate(FOLDERS):
        y = 20 + i * rowh
        d.text((30, y), NAMES[b], font=f, fill=(20, 20, 19, 255))
        lc, lt = png(b, "logo-horizontal-creme-2400"), png(b, "logo-horizontal-tinta-2400")
        s = 0.33
        lc = lc.resize((int(lc.width * s), int(lc.height * s)), Image.LANCZOS); lt = lt.resize(lc.size, Image.LANCZOS)
        sheet.paste(lc, (30, y + 50)); sheet.paste(lt, (60 + lc.width, y + 50))
        y2 = y + 50 + lc.height + 30; x = 30
        for n in ("avatar-quadrado-claro-512", "avatar-quadrado-escuro-512", "icone-aurora-claro-1024", "icone-aurora-escuro-1024"):
            im0 = png(b, n); im = im0.resize((150, 150 * im0.height // im0.width), Image.LANCZOS)
            bg = Image.new("RGBA", (170, im.height + 20), (60, 60, 60, 255) if "escuro" in n else (240, 238, 230, 255))
            bg.paste(im, (10, 10), im); sheet.paste(bg, (x, y2)); x += 200
        for n in ("favicon-compacto-claro-16", "favicon-compacto-claro-32", "favicon-compacto-claro-48", "favicon-padrao-claro-180"):
            im = png(b, n); sheet.paste(im, (x, y2), im); x += im.width + 30
    out = ROOT / "docs"; out.mkdir(exist_ok=True)
    sheet.convert("RGB").save(out / "showcase.png")

def hexof(n, path):
    for p in path.split("."): n = n[p]
    return n["$value"]["hex"]

def palette():
    rows = [("Neutros", [(k, hexof(TOK, f"color.neutral.{k}")) for k in ("ink", "cream", "warm-gray", "rule")]),
            ("Marca-mãe", [(k, hexof(TOK, f"color.accent.mother.{k}")) for k in ("light", "mid", "dark", "lightest")]),
            ("IA", [(k, hexof(TOK, f"color.accent.ia.{k}")) for k in ("light", "mid", "dark", "lightest")]),
            ("Tech (provisório)", [(k, hexof(TOK, f"color.accent.tech.{k}")) for k in ("light", "mid", "dark", "lightest")])]
    parts, y = ['<rect width="1200" height="640" fill="#FAF9F5"/>'], 30
    for title, chips in rows:
        parts.append(f'<text x="30" y="{y+22}" font-family="Liberation Sans" font-weight="700" font-size="22" fill="#141413">{title}</text>')
        x = 300
        for name, h in chips:
            lum = sum(int(h[i:i+2], 16) for i in (1, 3, 5)) / 3
            fg = "#141413" if lum > 140 else "#FAF9F5"
            parts.append(f'<rect x="{x}" y="{y}" width="200" height="110" rx="10" fill="{h}" stroke="#DDD9CB"/>'
                         f'<text x="{x+14}" y="{y+46}" font-family="Liberation Sans" font-weight="700" font-size="20" fill="{fg}">{h}</text>'
                         f'<text x="{x+14}" y="{y+76}" font-family="Liberation Sans" font-size="16" fill="{fg}">{name}</text>')
            x += 220
        y += 150
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="640" viewBox="0 0 1200 640">{"".join(parts)}</svg>'
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(ROOT / "docs" / "palette.png"))

if __name__ == "__main__":
    showcase(); palette(); print("docs/showcase.png e docs/palette.png gerados")
