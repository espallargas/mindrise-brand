#!/usr/bin/env python3
"""Checa contraste WCAG 2.x dos pares de cores definidos em tokens/tokens.json.
Uso: python3 scripts/contrast.py   (sai com código 1 se um par de TEXTO reprovar)
"""
import json, sys, pathlib
T = json.loads((pathlib.Path(__file__).parent.parent / "tokens" / "tokens.json").read_text())
def hexof(path):
    n = T
    for p in path.split("."): n = n[p]
    return n["$value"]["hex"]
def lum(h):
    h = h.lstrip("#"); ch = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    f = lambda v: v/12.92 if v <= 0.03928 else ((v+0.055)/1.055)**2.4
    r, g, b = map(f, ch); return 0.2126*r + 0.7152*g + 0.0722*b
def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True); return (la+0.05)/(lb+0.05)
# (descrição, primeiro plano, fundo, mínimo, tipo) tipo: "texto" reprova o script; "logo" idem com mínimo 3; "info" só informa
PAIRS = [
 ("texto: tinta no creme", "color.neutral.ink", "color.neutral.cream", 4.5, "texto"),
 ("texto: cinza quente no creme", "color.neutral.warm-gray", "color.neutral.cream", 4.5, "texto"),
 ("texto: ameixa escura no creme", "color.accent.ia.dark", "color.neutral.cream", 4.5, "texto"),
 ("texto: ameixa clara na tinta", "color.accent.ia.light", "color.neutral.ink", 4.5, "texto"),
 ("texto: verde-azulado escuro no creme (provisório)", "color.accent.tech.dark", "color.neutral.cream", 4.5, "texto"),
 ("texto: verde-azulado claro na tinta (provisório)", "color.accent.tech.light", "color.neutral.ink", 4.5, "texto"),
 ("logo: ameixa média no creme", "color.accent.ia.mid", "color.neutral.cream", 3.0, "logo"),
 ("logo: ameixa média na tinta", "color.accent.ia.mid", "color.neutral.ink", 3.0, "logo"),
 ("logo: verde-azulado médio no creme (provisório)", "color.accent.tech.mid", "color.neutral.cream", 3.0, "logo"),
 ("info, texto pequeno: ameixa média no creme", "color.accent.ia.mid", "color.neutral.cream", 4.5, "info"),
 ("info, texto pequeno: ameixa média na tinta", "color.accent.ia.mid", "color.neutral.ink", 4.5, "info"),
 ("info, texto pequeno: verde-azulado médio no creme", "color.accent.tech.mid", "color.neutral.cream", 4.5, "info"),
]
bad = 0
for d, fg, bg, mn, kind in PAIRS:
    r = ratio(hexof(fg), hexof(bg)); ok = r >= mn
    tag = "ok" if ok else ("FALHA" if kind != "info" else "abaixo")
    if not ok and kind != "info": bad += 1
    print(f"{tag:6} {r:5.2f}:1  (mín {mn})  {d}")
sys.exit(1 if bad else 0)
