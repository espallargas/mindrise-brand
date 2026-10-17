#!/usr/bin/env python3
"""Valida e gera os covers ilustrados da mindrise IA (SVG 600 x 315, PNG 1200 e 2400 de largura).

O agente desenha só o SVG. Este script confere o vocabulário e a composição, renderiza os PNGs,
dá o nome certo aos arquivos e grava spec.json e manifest.json na pasta da edição.
Nunca escreve no repositório da marca: a saída vai para --editions-dir (o repositório mindrise-editions).

Uso:
  python3 scripts/cover_ilustrado.py sortear-fundo --data 2026-10-17 --editions-dir /caminho/mindrise-editions/editions
  python3 scripts/cover_ilustrado.py historico --editions-dir /caminho/mindrise-editions/editions [--antes 2026-10-17] [-n 4]
  python3 scripts/cover_ilustrado.py validar cover.svg --fundo ameixa-dark
  python3 scripts/cover_ilustrado.py gerar cover.svg --data 2026-10-17 --fundo ameixa-dark --motivo nome-do-motivo \
      --ideia "uma frase" --titulo "evento" --empresa Meta --categoria Modelos --editions-dir /caminho/.../editions

Saída de erro: JSON em stdout e código de saída diferente de zero.
Regras: guia "Covers ilustrados" no Brand book (Aplicações). Cores vêm de tokens/tokens.json.
"""
import argparse, io, json, pathlib, random, re, sys, xml.etree.ElementTree as ET
from collections import Counter
import cairosvg
from PIL import Image, ImageChops

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOK = json.loads((ROOT / "tokens" / "tokens.json").read_text())

def hexof(path):
    n = TOK
    for k in path.split("."):
        n = n[k]
    return n["$value"]["hex"].upper()

INK, CREAM, LAV = hexof("color.neutral.ink"), hexof("color.neutral.cream"), hexof("color.neutral.lavender")
LIGHT, MID, DARK = hexof("color.accent.ia.light"), hexof("color.accent.ia.mid"), hexof("color.accent.ia.dark")
FUNDOS = {"creme": CREAM, "lavanda": LAV, "ameixa-light": LIGHT, "ameixa-mid": MID, "ameixa-dark": DARK}
PALETA = {INK, CREAM, LAV, LIGHT, MID, DARK}

# Geometria (unidades do viewBox 600 x 315). Mantenha igual ao guia.
VB_W, VB_H = 600, 315
CENTRO = (300.0, 157.5)
TOL_CENTRO = 2.0            # unidades (4 px no PNG de 1200)
LARGURA = (140, 460)        # largura da caixa que envolve as formas
ALTURA = (100, 150)         # altura da caixa
MAX_TONS = 4                # tons de forma, fora o fundo
CONTRASTE_DESTAQUE = 3.0

ELEMENTOS = {"svg", "g", "rect", "path", "circle", "title", "desc"}
PROIBIDOS_ATTR = {"stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "style", "filter", "opacity",
                  "fill-opacity", "class", "mask", "clip-path"}

def tag(e):
    return e.tag.split("}")[-1]

def lum(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

def contraste(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)

def vertices_se_so_retas(d):
    """Devolve os vértices distintos de um path feito só de M, L, H, V e Z; None se tiver curva."""
    toks = re.findall(r"[MmLlHhVvZzCcSsQqTtAa]|-?\d*\.?\d+(?:e-?\d+)?", d)
    cmds = [t for t in toks if t.isalpha()]
    if any(c in "CcSsQqTtAa" for c in cmds):
        return None
    pts, i, x, y, cmd = [], 0, 0.0, 0.0, None
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd in "Zz":
                continue
            continue_ = False
        if cmd in "Mm" or cmd in "Ll":
            nx, ny = float(toks[i]), float(toks[i + 1]); i += 2
            x, y = (nx, ny) if cmd.isupper() else (x + nx, y + ny)
            pts.append((round(x, 2), round(y, 2)))
            if cmd == "M": cmd = "L"
            if cmd == "m": cmd = "l"
        elif cmd in "Hh":
            nx = float(toks[i]); i += 1
            x = nx if cmd == "H" else x + nx
            pts.append((round(x, 2), round(y, 2)))
        elif cmd in "Vv":
            ny = float(toks[i]); i += 1
            y = ny if cmd == "V" else y + ny
            pts.append((round(x, 2), round(y, 2)))
        else:
            i += 1
    return set(pts)

def validar_svg(svg_text, fundo):
    erros, avisos, info = [], [], {}
    if fundo not in FUNDOS:
        return [f"fundo inválido: {fundo} (use {', '.join(FUNDOS)})"], avisos, info
    bg = FUNDOS[fundo]
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as e:
        return [f"SVG inválido: {e}"], avisos, info
    if tag(root) != "svg":
        return ["a raiz não é <svg>"], avisos, info
    if root.get("viewBox", "").split() != ["0", "0", str(VB_W), str(VB_H)]:
        erros.append(f'viewBox deve ser "0 0 {VB_W} {VB_H}"')
    if root.get("width") != "1200" or root.get("height") != "630":
        erros.append('width="1200" e height="630" são obrigatórios')

    # <metadata> (por exemplo, credenciais de conteúdo C2PA que algumas ferramentas embutem) é ignorado, com seus filhos
    ignorar = set()
    for m in root.iter():
        if tag(m) == "metadata":
            ignorar.update(m.iter())
    filhos = [e for e in root.iter() if e is not root and e not in ignorar]
    fills, area_hint = {}, {}
    primeiro_rect_ok = False
    for n, e in enumerate(filhos):
        t = tag(e)
        if t not in ELEMENTOS:
            erros.append(f"elemento não permitido: <{t}>")
            continue
        for a in e.attrib:
            if a in PROIBIDOS_ATTR:
                erros.append(f"atributo não permitido: {a} em <{t}>")
        tr = e.get("transform")
        if tr and not (t == "g" and re.fullmatch(r"\s*translate\([-\d.,\s]+\)\s*", tr)):
            erros.append(f"transform não permitido: {tr}")
        if t in ("title", "desc", "g"):
            continue
        f = (e.get("fill") or "").upper()
        if not re.fullmatch(r"#[0-9A-F]{6}", f):
            erros.append(f"<{t}> sem fill em hex: {e.get('fill')}")
            continue
        if f not in PALETA:
            erros.append(f"cor fora da paleta: {f}")
        if not primeiro_rect_ok:
            ok = (t == "rect" and float(e.get("width", 0)) == VB_W and float(e.get("height", 0)) == VB_H
                  and float(e.get("x", 0)) == 0 and float(e.get("y", 0)) == 0)
            if not ok:
                erros.append("o primeiro elemento de forma deve ser o retângulo de fundo 600 x 315")
            elif f != bg:
                erros.append(f"o fundo do SVG ({f}) não é o do fundo informado ({fundo}, {bg})")
            primeiro_rect_ok = True
            continue
        if t == "path":
            v = vertices_se_so_retas(e.get("d", ""))
            if v is not None and len(v) == 3:
                erros.append("triângulo não permitido (path com 3 vértices e só retas)")
        if f != bg:
            fills[f] = fills.get(f, 0) + 1
    if not primeiro_rect_ok:
        erros.append("faltou o retângulo de fundo")
    if len(fills) > MAX_TONS:
        erros.append(f"{len(fills)} tons de forma; o máximo é {MAX_TONS} fora o fundo")
    info["tons"] = sorted(fills)

    # Renderiza e mede a caixa que envolve as formas
    if not erros:
        png = cairosvg.svg2png(bytestring=svg_text.encode(), output_width=2 * VB_W)
        im = Image.open(io.BytesIO(png)).convert("RGB")
        fundo_im = Image.new("RGB", im.size, bg)
        box = ImageChops.difference(im, fundo_im).getbbox()
        if not box:
            erros.append("o cover não tem nenhuma forma além do fundo")
        else:
            x0, y0, x1, y1 = (v / 2 for v in box)
            cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
            info["caixa"] = dict(x0=x0, y0=y0, x1=x1, y1=y1, largura=w, altura=h, centro=[cx, cy])
            if abs(cx - CENTRO[0]) > TOL_CENTRO or abs(cy - CENTRO[1]) > TOL_CENTRO:
                erros.append(f"centro da caixa em ({cx:.1f}; {cy:.1f}), esperado ({CENTRO[0]}; {CENTRO[1]}) ± {TOL_CENTRO}")
            if not LARGURA[0] <= w <= LARGURA[1]:
                erros.append(f"largura da caixa {w:.0f} fora de {LARGURA[0]} a {LARGURA[1]}")
            if not ALTURA[0] <= h <= ALTURA[1]:
                erros.append(f"altura da caixa {h:.0f} fora de {ALTURA[0]} a {ALTURA[1]}")
            # Contraste e área por cor (aviso, não bloqueia, desde que algum tom chegue a 3:1)
            raw = im.tobytes()
            contagem = Counter(zip(raw[0::3], raw[1::3], raw[2::3]))
            total = {}
            for p, n in contagem.items():
                hx = "#%02X%02X%02X" % p
                if hx != bg:
                    total[hx] = total.get(hx, 0) + n
            soma = sum(total.values()) or 1
            rel = {}
            for hx, n in total.items():
                c = contraste(hx, bg)
                rel[hx] = dict(contraste=round(c, 2), parte_da_area=round(n / soma, 2))
                if c < CONTRASTE_DESTAQUE and n / soma >= 0.15:
                    avisos.append(f"{hx} ocupa {n / soma:.0%} das formas e tem contraste {c:.2f}:1 com o fundo (< {CONTRASTE_DESTAQUE}:1)")
            info["cores"] = rel
            if rel and max(v["contraste"] for v in rel.values()) < CONTRASTE_DESTAQUE:
                erros.append(f"nenhuma forma chega a {CONTRASTE_DESTAQUE}:1 de contraste com o fundo")
    return erros, avisos, info

def specs(editions_dir, antes=None):
    base = pathlib.Path(editions_dir)
    out = []
    for p in sorted(base.glob("*/spec.json")):
        try:
            s = json.loads(p.read_text())
        except Exception:
            continue
        if antes and s.get("data", p.parent.name) >= antes:
            continue
        out.append(s)
    return sorted(out, key=lambda s: s.get("data", ""))

def nome(data, fundo, tam=None, ext="png"):
    return f"mindrise-ia-cover-{data}-ilustrado-{fundo}" + (f"-{tam}" if tam else "") + f".{ext}"

def cmd_sortear(a):
    ant = specs(a.editions_dir, a.data)
    ultimo = ant[-1]["fundo"] if ant else None
    opcoes = [f for f in FUNDOS if f != ultimo]
    f = random.Random(a.data).choice(opcoes)   # semente = data: rodar de novo no mesmo dia dá o mesmo fundo
    print(json.dumps(dict(fundo=f, fundo_anterior=ultimo, opcoes=opcoes), ensure_ascii=False))

def cmd_historico(a):
    for s in specs(a.editions_dir, a.antes)[-a.n:]:
        print(json.dumps(dict(data=s.get("data"), fundo=s.get("fundo"), motivo=s.get("motivo"), ideia=s.get("ideia")), ensure_ascii=False))

def cmd_validar(a):
    erros, avisos, info = validar_svg(pathlib.Path(a.svg).read_text(), a.fundo)
    print(json.dumps(dict(ok=not erros, erros=erros, avisos=avisos, info=info), ensure_ascii=False, indent=1))
    sys.exit(1 if erros else 0)

def cmd_gerar(a):
    svg_text = pathlib.Path(a.svg).read_text()
    erros, avisos, info = validar_svg(svg_text, a.fundo)
    ant = specs(a.editions_dir, a.data)
    if ant and ant[-1]["fundo"] == a.fundo:
        erros.append(f"o fundo {a.fundo} é o mesmo da edição anterior ({ant[-1].get('data')})")
    if a.motivo in [s.get("motivo") for s in ant[-4:]]:
        erros.append(f"o motivo '{a.motivo}' já foi usado num dos últimos quatro covers")
    if erros:
        print(json.dumps(dict(ok=False, erros=erros, avisos=avisos), ensure_ascii=False, indent=1))
        sys.exit(1)
    pasta = pathlib.Path(a.editions_dir) / a.data
    pasta.mkdir(parents=True, exist_ok=True)
    arquivos = []
    (pasta / nome(a.data, a.fundo, ext="svg")).write_text(svg_text)
    arquivos.append((nome(a.data, a.fundo, ext="svg"), "svg", "vetor"))
    for w in (1200, 2400):
        n = nome(a.data, a.fundo, w)
        cairosvg.svg2png(bytestring=svg_text.encode(), write_to=str(pasta / n), output_width=w)
        arquivos.append((n, "png", str(w)))
    spec = dict(data=a.data, fundo=a.fundo, motivo=a.motivo, ideia=a.ideia,
                evento=dict(titulo=a.titulo, empresa=a.empresa, categoria=a.categoria))
    (pasta / "spec.json").write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n")
    mf = pasta / "manifest.json"
    dados = json.loads(mf.read_text()) if mf.exists() else []
    dados = [d for d in dados if d.get("tipo") != "cover" or d.get("variante") != "ilustrado"]
    dados += [dict(arquivo=f"editions/{a.data}/{n}", marca="ia", tipo="cover", variante="ilustrado", fundo=a.fundo,
                   formato=fmt, tamanho=tam) for n, fmt, tam in arquivos]
    mf.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(dict(ok=True, pasta=str(pasta), arquivos=[n for n, _, _ in arquivos], avisos=avisos), ensure_ascii=False, indent=1))

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sortear-fundo"); s.add_argument("--data", required=True); s.add_argument("--editions-dir", required=True); s.set_defaults(f=cmd_sortear)
    s = sub.add_parser("historico"); s.add_argument("--editions-dir", required=True); s.add_argument("--antes"); s.add_argument("-n", type=int, default=4); s.set_defaults(f=cmd_historico)
    s = sub.add_parser("validar"); s.add_argument("svg"); s.add_argument("--fundo", required=True); s.set_defaults(f=cmd_validar)
    s = sub.add_parser("gerar"); s.add_argument("svg")
    for k in ("data", "fundo", "motivo", "ideia", "titulo", "empresa", "categoria", "editions-dir"):
        s.add_argument("--" + k, required=True)
    s.set_defaults(f=cmd_gerar)
    a = p.parse_args()
    a.f(a)

if __name__ == "__main__":
    main()
