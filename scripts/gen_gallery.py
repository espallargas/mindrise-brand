#!/usr/bin/env python3
"""Gera previews (docs/previews/*.png) e páginas de galeria (README.md em cada pasta de assets e GALLERY.md).
O GitHub não mostra miniaturas na listagem de arquivos, mas renderiza o README.md da pasta aberta.
Rode depois de scripts/gen_logo.py.   Requer: pillow, cairosvg
"""
import io, json, pathlib
from collections import OrderedDict
from PIL import Image
import cairosvg

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAN = json.loads((ROOT / "assets" / "manifest.json").read_text())
PREV = ROOT / "docs" / "previews"; PREV.mkdir(parents=True, exist_ok=True)
DARK_BG, LIGHT_BG = (20, 20, 19), (240, 238, 230)
DARK_FUNDOS = {"escuro", "tinta", "mono-branco"}
TITLES = {"mae": "Marca-mãe", "ia": "Newsletter de IA", "tech": "Newsletter de tech (provisória)"}

# agrupa por asset (svg + pngs)
groups = OrderedDict()
for m in MAN:
    k = (m["marca"], m["tipo"], m["variante"], m["fundo"])
    groups.setdefault(k, []).append(m)

def thumb(key, files):
    marca, tipo, variante, fundo = key
    svg = next(f for f in files if f["formato"] == "svg")
    out = PREV / (pathlib.Path(svg["arquivo"]).stem + ".png")
    w = 520 if tipo == "logo" else 220
    b = io.BytesIO(); cairosvg.svg2png(url=str(ROOT / svg["arquivo"]), write_to=b, output_width=w); b.seek(0)
    im = Image.open(b).convert("RGBA")
    bg = DARK_BG if fundo in DARK_FUNDOS else LIGHT_BG
    pad = 24
    canvas = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), bg + (255,))
    canvas.paste(im, (pad, pad), im)
    canvas.convert("RGB").save(out, optimize=True)
    return out

def rel(from_dir, target):
    return pathlib.Path(__import__("os").path.relpath(target, from_dir)).as_posix()

def cell(key, files, from_dir):
    marca, tipo, variante, fundo = key
    svg = next(f for f in files if f["formato"] == "svg")
    stem = pathlib.Path(svg["arquivo"]).stem
    t = rel(from_dir, PREV / f"{stem}.png")
    links = [f"[svg]({rel(from_dir, ROOT / svg['arquivo'])})"]
    for f in sorted((f for f in files if f["formato"] == "png"), key=lambda f: int(f["tamanho"])):
        links.append(f"[{f['tamanho']}]({rel(from_dir, ROOT / f['arquivo'])})")
    return f"[![{stem}]({t})]({rel(from_dir, ROOT / svg['arquivo'])})<br>`{tipo}-{variante}-{fundo}`<br>{' · '.join(links)}"

def table(cells, cols):
    rows = ["| " + " | ".join([" "] * cols) + " |", "| " + " | ".join(["---"] * cols) + " |"]
    for i in range(0, len(cells), cols):
        chunk = cells[i:i + cols] + [" "] * (cols - len(cells[i:i + cols]))
        rows.append("| " + " | ".join(chunk) + " |")
    return "\n".join(rows)

SECTIONS = [("logo", "Logos", 2, "Logo horizontal"), ("icone", "Ícones", 3, ""), ("avatar", "Avatares", 3, ""),
            ("favicon", "Favicons", 3, "")]

def page_for(folder_key, marca_list, from_dir, title):
    md = [f"# {title}", "", "Clique na imagem para abrir o SVG mestre. Os números são a largura em px dos PNGs derivados.", ""]
    for tipo, label, cols, _ in SECTIONS:
        cells = []
        for key, files in groups.items():
            if key[0] in marca_list and key[1] == tipo:
                cells.append(cell(key, files, from_dir))
        if cells:
            md += [f"## {label}", "", table(cells, cols), ""]
    return "\n".join(md)

for key, files in groups.items():
    thumb(key, files)

FOLDERS = {"mae": ROOT / "assets/01-nucleo", "ia": ROOT / "assets/02-newsletters/ia", "tech": ROOT / "assets/02-newsletters/tech"}
for marca, d in FOLDERS.items():
    (d / "README.md").write_text(page_for(marca, [marca], d, TITLES[marca]))

# GALLERY.md na raiz: tudo numa página
md = ["# Galeria", "", "Todos os assets em uma página. Para um conjunto só, abra a pasta (cada uma tem seu README com galeria).", ""]
for marca in ("mae", "ia", "tech"):
    sub = page_for(marca, [marca], ROOT, "").split("\n", 4)[-1]
    md += [f"# {TITLES[marca]}", "", sub.replace("## ", "### "), ""]
(ROOT / "GALLERY.md").write_text("\n".join(md))
print(len(groups), "assets,", len(list(PREV.glob('*.png'))), "previews")
