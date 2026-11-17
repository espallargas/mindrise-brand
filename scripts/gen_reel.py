#!/usr/bin/env python3
"""Gera o Reel do Instagram (1080 x 1920, 30 fps, 25 s, MP4 com trilha original) a partir de um JSON de conteúdo.

Uso:  python3 scripts/gen_reel.py <reel/AAAA-MM-DD.json> [pasta de saída]
      python3 scripts/gen_reel.py <json> --validar            só confere o texto e mostra o tempo de cada cena
      python3 scripts/gen_reel.py <json> --quadros [pasta]    grava PNGs dos quadros-chave e uma folha de contato
Saída: {pasta}/mindrise-ia-reel-{nome}.mp4, em que {nome} é o nome do JSON sem a extensão (no Distributor, a data).
       Sem pasta de saída, grava em /tmp/reel e não toca neste repositório.

Estrutura (regras na página Aplicações do Brand book, seção "Instagram", parte "Reel"):
  1. gancho: rótulo da empresa, manchete da principal e, opcional, uma linha de apoio ("sub");
  2. número (opcional): número grande, o que ele mede e, opcional, uma nota;
  3. itens (opcional): rótulo e 1 ou 2 itens, cada um com um destaque curto e uma frase;
  4. "Por que importa": 1 ou 2 frases;
  5. fechamento fixo: logo, frase da marca e "Link na bio".
Pelo menos uma das cenas 2 e 3 precisa existir.

Tempo: a duração total é fixa (18 meios compassos a 86,4 bpm, 25 s). O fechamento tem 3 meios compassos; os outros 15
se dividem entre as cenas de conteúdo na proporção das palavras de cada uma (mínimo de 3 por cena). Cada corte cai num
meio compasso, e a trilha troca de acorde nele.
Ritmo: o script conta as palavras que o leitor precisa ler (rótulos fora) e BLOQUEIA acima de 280 palavras por minuto
numa cena ou de 85 palavras no total; AVISA acima de 240 por minuto ou de 75 no total. Confortável: de 200 a 240.
Altura: bloqueia texto que passe da linha 1560 (os 360 px de baixo ficam livres para a legenda e os botões do Instagram).

Trilha: soft jazz sintetizado do zero (Rhodes por FM, baixo por Karplus-Strong, vibrafone, ride, escovinha e bumbo),
Mi bemol maior, swing. A semente vem do nome do arquivo, então a melodia varia por dia e se repete se o Reel for refeito.
Precisa de ffmpeg, numpy, scipy e Pillow.
"""
import hashlib, json, math, multiprocessing, os, pathlib, shutil, subprocess, sys, tempfile
from concurrent.futures import ProcessPoolExecutor
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOK = json.loads((ROOT / "tokens" / "tokens.json").read_text())
hexof = lambda p: __import__("functools").reduce(lambda n, k: n[k], p.split("."), TOK)["$value"]["hex"]
INK, CREAM, GRAY = (hexof(f"color.neutral.{k}") for k in ("ink", "cream", "warm-gray"))
LAV = hexof("color.neutral.lavender")
LIGHT, MID, DARK = (hexof(f"color.accent.ia.{k}") for k in ("light", "mid", "dark"))

W, H, FPS = 1080, 1920, 30
BPM = 86.4
BEAT = 60 / BPM
HALF = 2 * BEAT
TOTAL_UN, CTA_UN, MIN_UN = 18, 3, 3
DUR = TOTAL_UN * HALF
X, TW = 96, 888
CHAO = 1560
FRASE = "As notícias de IA que importam, nos dias úteis, em 5 minutos."
WPM_AVISO, WPM_LIMITE = 240, 280
PAL_AVISO, PAL_LIMITE = 75, 85

# cenas de destaque (gancho e "Por que importa"): fundo, texto, apoio, rótulo, barra, aurora (fora > dentro), barra da aurora
TEMAS = {
    "ameixa-dark": dict(bg=DARK, txt=CREAM, apoio=LAV, rot=LAV, barra=LIGHT, aurora=(MID, LIGHT, LAV), chao=CREAM),
    "lavanda": dict(bg=LAV, txt=INK, apoio=GRAY, rot=DARK, barra=MID, aurora=(LIGHT, MID, DARK), chao=INK),
}

C = {}      # conteúdo carregado do JSON (preenchido em carregar)
CENAS = []  # (início, fim, função)


def rgb(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

_fc = {}
def F(kind, size):
    k = (kind, size)
    if k not in _fc:
        if kind == "gel":
            f = ImageFont.truetype(str(ROOT / "fonts" / "Gelasio-Variable.ttf"), size)
            try: f.set_variation_by_name("Bold")
            except Exception: pass
        else:
            f = ImageFont.truetype(str(ROOT / "fonts" / ("LiberationSans-Bold.ttf" if kind == "sansb" else "LiberationSans-Regular.ttf")), size)
        _fc[k] = f
    return _fc[k]

_DR = ImageDraw.Draw(Image.new("RGB", (1, 1)))
def tl(s, f): return _DR.textlength(s, font=f)
def prog(t, s, d): return 0.0 if t <= s else 1.0 if t >= s + d else (t - s) / d
def ease(p): return 1 - (1 - p) ** 3
def mix(a, b, p): a, b = rgb(a), rgb(b); return tuple(round(x + (y - x) * p) for x, y in zip(a, b))
def npal(*ss): return sum(len(s.split()) for s in ss if s)

def layout(text, font, x, y, w, lh):
    sp = tl(" ", font); out, cx, cy = [], x, y
    for wd in text.split():
        ww = tl(wd, font)
        if cx > x and cx + ww > x + w: cx, cy = x, cy + lh
        out.append((wd, cx, cy)); cx += ww + sp
    return out, cy + lh

def caber(s, kind, size, w, minimo):
    while size > minimo and tl(s, F(kind, size)) > w: size -= 4
    return size

def words(img, text, font, color, x, y, w, lh, t, start, per=0.045, bg=CREAM):
    d = ImageDraw.Draw(img); items, yend = layout(text, font, x, y, w, lh)
    for i, (wd, wx, wy) in enumerate(items):
        p = ease(prog(t, start + i * per, 0.35))
        if p > 0: d.text((wx, wy + 18 * (1 - p)), wd, font=font, fill=mix(bg, color, p))
    return yend

def fade_text(img, text, font, color, x, y, t, start, bg=CREAM):
    p = ease(prog(t, start, 0.4))
    if p > 0: ImageDraw.Draw(img).text((x, y + 12 * (1 - p)), text, font=font, fill=mix(bg, color, p))

def label(img, text, x, y, color, t, start, bg=CREAM):
    fade_text(img, text.upper(), F("sansb", 34), color, x, y, t, start, bg)

def aurora(img, cx, base, u, t, start, cores, barra):
    d = ImageDraw.Draw(img); pb = ease(prog(t, start, 0.4))
    if pb > 0:
        bw = 9 * u * pb; d.rectangle([cx - bw / 2, base, cx + bw / 2, base + 1.5 * u], fill=rgb(barra))
    for k, (r, c) in enumerate(zip((3, 2, 1), cores)):
        p = ease(prog(t, start + 0.25 + 0.12 * k, 0.45))
        if p > 0: rr = r * u * p; d.pieslice([cx - rr, base - rr, cx + rr, base + rr], 180, 360, fill=rgb(c))


# ---------- geometria de cada cena (usada para desenhar e para validar a altura) ----------
def geo_gancho():
    size = 92
    while size > 72:
        _, y = layout(C["manchete"], F("gel", size), X, 535, TW, round(size * 1.22))
        if y <= 1250: break
        size -= 4
    _, y = layout(C["manchete"], F("gel", size), X, 535, TW, round(size * 1.22))
    yf = y
    if C.get("sub"): _, yf = layout(C["sub"], F("sans", 44), X, y + 40, TW, 58)
    return size, y, yf

def geo_numero():
    n = C["numero"]; size = caber(n["valor"], "gel", 330, TW, 160)
    ytxt = 470 + round(size * 1.3) + round((330 - size) * 0.15)
    _, y = layout(n["texto"], F("gel", 66), X, ytxt, TW, 84)
    yf = y
    if n.get("nota"): _, yf = layout(n["nota"], F("sans", 42), X, y + 40, TW, 60)
    return size, ytxt, y, yf

def geo_itens():
    lista = C["itens"]["lista"]; size = min(caber(i["destaque"], "gel", 150, TW, 90) for i in lista)
    ys, y = [], 490
    for i in lista:
        _, yy = layout(i["texto"], F("sans", 50), X, y + round(size * 1.3), TW, 66)
        ys.append((y, yy)); y = yy + 90
    return size, ys, ys[-1][1]

def geo_importa():
    tx, tw = X + 50, TW - 50; frases = C["por_que_importa"]
    f1 = F("gel", 70 if len(frases) == 2 else 76); lh1 = 90 if len(frases) == 2 else 98
    _, y1 = layout(frases[0], f1, tx, 520, tw, lh1); y2 = y1
    if len(frases) == 2: _, y2 = layout(frases[1], F("gel", 56), tx, y1 + 40, tw, 76)
    return f1, lh1, y1, y2


# ---------- cenas ----------
def cena_gancho(t):
    T = TEMAS[C["faixa"]]; img = Image.new("RGB", (W, H), rgb(T["bg"]))
    aurora(img, X + 4.5 * 20, 380, 20, t, 0.0, T["aurora"], T["chao"])
    label(img, C["rotulo"], X, 470, T["rot"], t, 0.15, bg=T["bg"])
    size, y, _ = geo_gancho()
    words(img, C["manchete"], F("gel", size), T["txt"], X, 535, TW, round(size * 1.22), t, 0.3, per=0.055, bg=T["bg"])
    if C.get("sub"): words(img, C["sub"], F("sans", 44), T["apoio"], X, y + 40, TW, 58, t, 1.4, per=0.03, bg=T["bg"])
    return img

def cena_numero(t):
    n = C["numero"]; img = Image.new("RGB", (W, H), rgb(CREAM))
    label(img, n.get("rotulo", ""), X, 430, DARK, t, 0.0)
    size, ytxt, y, _ = geo_numero()
    fade_text(img, n["valor"], F("gel", size), DARK, X - 8, 470, t, 0.15)
    words(img, n["texto"], F("gel", 66), INK, X, ytxt, TW, 84, t, 0.6, per=0.045)
    if n.get("nota"): words(img, n["nota"], F("sans", 42), GRAY, X, y + 40, TW, 60, t, 1.6, per=0.03)
    return img

def cena_itens(t):
    it = C["itens"]; img = Image.new("RGB", (W, H), rgb(CREAM)); d = ImageDraw.Draw(img)
    label(img, it.get("rotulo", ""), X, 430, DARK, t, 0.0)
    size, ys, _ = geo_itens()
    for i, (item, (y, yy)) in enumerate(zip(it["lista"], ys)):
        s = 0.2 + i * 1.3
        fade_text(img, item["destaque"], F("gel", size), DARK if i == 0 else INK, X - 6, y, t, s)
        words(img, item["texto"], F("sans", 50), GRAY, X, y + round(size * 1.3), TW, 66, t, s + 0.3, per=0.04)
        if i == 0 and len(ys) > 1:
            q = ease(prog(t, 1.0, 0.5))
            if q > 0: d.rectangle([X, yy + 40, X + 220 * q, yy + 46], fill=rgb(LIGHT))
    return img

def cena_importa(t):
    T = TEMAS[C["faixa"]]; img = Image.new("RGB", (W, H), rgb(T["bg"])); d = ImageDraw.Draw(img)
    tx, tw = X + 50, TW - 50; frases = C["por_que_importa"]
    f1, lh1, y1, y2 = geo_importa()
    top = 440; bot = (y2 if len(frases) == 2 else y1) - 6
    p = ease(prog(t, 0.0, 0.5))
    d.rectangle([X, top, X + 10, top + (bot - top) * p], fill=rgb(T["barra"]))
    label(img, "Por que importa", tx, top, T["rot"], t, 0.1, bg=T["bg"])
    words(img, frases[0], f1, T["txt"], tx, 520, tw, lh1, t, 0.25, per=0.06, bg=T["bg"])
    if len(frases) == 2: words(img, frases[1], F("gel", 56), T["apoio"], tx, y1 + 40, tw, 76, t, 1.6, per=0.05, bg=T["bg"])
    return img

_LOGO = {}
def logo():
    if "img" not in _LOGO:
        lg = Image.open(ROOT / "assets" / "02-newsletters" / "ia" / "mindrise-ia-logo-horizontal-claro-2400.png").convert("RGBA")
        _LOGO["img"] = lg.resize((640, round(lg.height * 640 / lg.width)), Image.LANCZOS)
    return _LOGO["img"]

def cena_cta(t):
    img = Image.new("RGB", (W, H), rgb(CREAM)); LG = logo(); p = ease(prog(t, 0.0, 0.6))
    if p > 0:
        lg = LG.copy(); lg.putalpha(lg.getchannel("A").point(lambda v: int(v * p)))
        img.paste(lg, ((W - LG.width) // 2, 640 + round(20 * (1 - p))), lg)
    d = ImageDraw.Draw(img); f = F("gel", 58)
    items, _ = layout(FRASE, f, 0, 0, 820, 76); linhas = {}
    for wd, wx, wy in items: linhas.setdefault(wy, []).append(wd)
    y0 = 640 + LG.height + 110; q = ease(prog(t, 0.5, 0.5))
    for j, (_, ws) in enumerate(sorted(linhas.items())):
        txt = " ".join(ws); lw = tl(txt, f)
        if q > 0: d.text(((W - lw) / 2, y0 + j * 76 + 12 * (1 - q)), txt, font=f, fill=mix(CREAM, INK, q))
    r = ease(prog(t, 1.2, 0.5))
    if r > 0:
        fb = F("sansb", 44); txt = "LINK NA BIO"; lw = tl(txt, fb); yb = y0 + len(linhas) * 76 + 70
        d.rounded_rectangle([(W - lw) / 2 - 40, yb - 22, (W + lw) / 2 + 40, yb + 70], 46, fill=mix(CREAM, DARK, r))
        d.text(((W - lw) / 2, yb), txt, font=fb, fill=CREAM)
    return img


# ---------- conteúdo, validação e tempos ----------
def carregar(path):
    j = json.loads(pathlib.Path(path).read_text())
    erros = []
    if j.get("faixa") not in TEMAS: erros.append(f"faixa deve ser {' ou '.join(TEMAS)}")
    for k in ("rotulo", "manchete", "por_que_importa"):
        if not j.get(k): erros.append(f"falta o campo {k}")
    if isinstance(j.get("por_que_importa"), str): j["por_que_importa"] = [j["por_que_importa"]]
    if j.get("por_que_importa") and not 1 <= len(j["por_que_importa"]) <= 2: erros.append("por_que_importa: 1 ou 2 frases")
    if not j.get("numero") and not j.get("itens"): erros.append("precisa de numero, de itens ou dos dois")
    if j.get("numero") and not (j["numero"].get("valor") and j["numero"].get("texto")): erros.append("numero precisa de valor e texto")
    if j.get("itens"):
        lista = j["itens"].get("lista") or []
        if not 1 <= len(lista) <= 2 or not all(i.get("destaque") and i.get("texto") for i in lista):
            erros.append("itens.lista: 1 ou 2 itens, cada um com destaque e texto")
    if erros: sys.exit("ERRO no JSON: " + "; ".join(erros))
    C.clear(); C.update(j); C["nome"] = pathlib.Path(path).stem

def plano():
    """Lista de (nome, função, palavras) das cenas de conteúdo, na ordem."""
    cs = [("gancho", cena_gancho, npal(C["manchete"], C.get("sub")))]
    if C.get("numero"): n = C["numero"]; cs.append(("numero", cena_numero, npal(n["valor"], n["texto"], n.get("nota"))))
    if C.get("itens"): cs.append(("itens", cena_itens, sum(npal(i["destaque"], i["texto"]) for i in C["itens"]["lista"])))
    cs.append(("importa", cena_importa, npal(*C["por_que_importa"])))
    return cs

def dividir(pesos, total, minimo):
    un = [minimo] * len(pesos); resto = total - minimo * len(pesos)
    if resto < 0: sys.exit("ERRO: cenas demais para 25 s")
    soma = sum(pesos) or 1; alvo = [resto * p / soma for p in pesos]
    extra = [math.floor(a) for a in alvo]
    for i in sorted(range(len(pesos)), key=lambda i: alvo[i] - extra[i], reverse=True)[: resto - sum(extra)]: extra[i] += 1
    return [u + e for u, e in zip(un, extra)]

def montar():
    cs = plano(); un = dividir([p for _, _, p in cs], TOTAL_UN - CTA_UN, MIN_UN)
    CENAS.clear(); a = 0.0; rel = []
    for (nome, fn, pal), u in zip(cs, un):
        CENAS.append((a, a + u * HALF, fn)); rel.append((nome, pal, u * HALF, pal / (u * HALF) * 60)); a += u * HALF
    CENAS.append((a, DUR, cena_cta)); rel.append(("fechamento", 0, DUR - a, 0))
    return rel

def validar():
    rel = montar(); bloqueios, avisos = [], []
    total = sum(p for _, p, _, _ in rel)
    print(f"{'cena':<11}{'palavras':>9}{'segundos':>10}{'pal/min':>9}")
    for nome, pal, s, wpm in rel:
        print(f"{nome:<11}{pal:>9}{s:>10.1f}{wpm:>9.0f}")
        if wpm > WPM_LIMITE: bloqueios.append(f"{nome}: {wpm:.0f} palavras por minuto (limite {WPM_LIMITE}); corte {math.ceil(pal - WPM_LIMITE * s / 60)} palavras")
        elif wpm > WPM_AVISO: avisos.append(f"{nome}: {wpm:.0f} palavras por minuto (confortável até {WPM_AVISO})")
    print(f"{'total':<11}{total:>9}{DUR:>10.1f}")
    if total > PAL_LIMITE: bloqueios.append(f"total de {total} palavras (limite {PAL_LIMITE})")
    elif total > PAL_AVISO: avisos.append(f"total de {total} palavras (confortável até {PAL_AVISO})")
    alturas = {"gancho": geo_gancho()[2], "importa": geo_importa()[3]}
    if C.get("numero"): alturas["numero"] = geo_numero()[3]
    if C.get("itens"): alturas["itens"] = geo_itens()[2]
    for nome, y in alturas.items():
        if y > CHAO: bloqueios.append(f"{nome}: o texto vai até a linha {y:.0f} (limite {CHAO}); encurte")
    for a in avisos: print("AVISO", a)
    for b in bloqueios: print("BLOQUEIO", b)
    return not bloqueios


# ---------- vídeo ----------
def frame(t):
    for a, b, fn in CENAS:
        if a <= t < b or fn is cena_cta:
            img = fn(t - a); fo = prog(t, DUR - 0.6, 0.6)
            if fo > 0: img = Image.blend(img, Image.new("RGB", (W, H), rgb(CREAM)), fo)
            return img

def render_cena(args):
    i, out = args; a, b, _ = CENAS[i]
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                           "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for n in range(round(a * FPS), round(b * FPS)): ff.stdin.write(frame(n / FPS).tobytes())
    ff.stdin.close(); assert ff.wait() == 0, f"ffmpeg falhou na cena {i}"
    return out


# ---------- trilha ----------
def trilha(out_wav):
    import numpy as np
    from scipy.signal import butter, sosfilt, fftconvolve
    from scipy.io import wavfile
    SR = 44100; N = int(round(DUR * SR))
    rng = np.random.default_rng(int(hashlib.sha1(C["nome"].encode()).hexdigest()[:8], 16))
    L = np.zeros(N); R = np.zeros(N); SW = 2 / 3
    hz = lambda m: 440.0 * 2 ** ((m - 69) / 12)
    def add(sig, t0, pan=0.0, gain=1.0):
        i = int(round(t0 * SR))
        if i >= N or i < 0: return
        sig = sig[: N - i] * gain
        L[i:i + len(sig)] += sig * np.sqrt(0.5 * (1 - pan)); R[i:i + len(sig)] += sig * np.sqrt(0.5 * (1 + pan))
    lp = lambda x, f, o=2: sosfilt(butter(o, f, "low", fs=SR, output="sos"), x)
    hp = lambda x, f, o=2: sosfilt(butter(o, f, "high", fs=SR, output="sos"), x)
    bp = lambda x, a, b, o=2: sosfilt(butter(o, [a, b], "band", fs=SR, output="sos"), x)
    hum = lambda: rng.normal(0, 0.006)
    CH = {"Ebmaj9": ([55, 58, 62, 65], 39), "Cm9": ([55, 58, 62, 63], 36), "Fm9": ([56, 60, 63, 67], 41),
          "Bb13": ([56, 60, 62, 67], 46), "Abmaj9": ([55, 60, 63, 67], 44), "Gm7": ([53, 58, 62, 65], 43),
          "Bb7sus": ([56, 60, 63, 67], 46), "Fm7": ([56, 60, 63, 65], 41)}
    PROG = ["Ebmaj9", "Ebmaj9", "Cm9", "Fm9", "Bb13", "Ebmaj9", "Abmaj9", "Gm7", "Cm9",
            "Fm9", "Fm9", "Bb13", "Gm7", "Cm9", "Fm7", "Abmaj9", "Bb7sus", "Ebmaj9"]
    CUTS = {round(a / HALF) for a, _, _ in CENAS[1:]}
    # num corte, o acorde precisa mudar: se a progressão repete ali, troca pelo relativo
    for h in CUTS:
        if 0 < h < len(PROG) - 1 and PROG[h] == PROG[h - 1]: PROG[h] = {"Ebmaj9": "Cm9", "Fm9": "Abmaj9"}.get(PROG[h], "Gm7")
    HB = HALF; last = len(PROG) - 1

    def rhodes(m, dur, vel=0.5):
        n = int((dur + 0.6) * SR); t = np.arange(n) / SR; f = hz(m)
        idx = (1.2 * np.exp(-t / 0.25) + 0.25) * (0.6 + vel)
        s = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t)) + 0.12 * np.exp(-t / 0.05) * np.sin(2 * np.pi * f * 14.0 * t)
        return s * np.minimum(t / 0.004, 1) * np.exp(-t / 1.6) * np.clip(1 - (t - dur) / 0.25, 0, 1) * vel
    def acorde(nome, t0, dur, vel):
        for k, m in enumerate(CH[nome][0]): add(rhodes(m, dur, vel * rng.uniform(0.85, 1.0)), t0 + k * 0.008 + hum(), pan=-0.25 + 0.15 * k)
    for h, nome in enumerate(PROG):
        t0 = h * HB
        if h == last: acorde(nome, t0, DUR - t0, 0.42); continue
        if h not in CUTS and h > 1 and PROG[h] != PROG[h - 1] and rng.random() < 0.5: acorde(nome, t0 - BEAT * (1 - SW), HB * 0.9, 0.36)
        else: acorde(nome, t0, HB * 0.85, 0.40 if h in CUTS else 0.34)
        if h >= 2 and rng.random() < 0.45: acorde(nome, t0 + BEAT + BEAT * SW, BEAT * 0.4, 0.22)

    def baixo(m, dur, vel=0.8):
        f = hz(m); p = int(SR / f); n = int((dur + 0.2) * SR)
        b = lp(rng.uniform(-1, 1, p), f * 6).copy(); out = np.empty(n)
        for i in range(n):
            j = i % p; out[i] = b[j]; b[j] = 0.996 * 0.5 * (b[j] + b[(j + 1) % p])
        t = np.arange(n) / SR
        out = lp(out, 900) * np.minimum(t / 0.006, 1) * np.clip(1 - (t - dur) / 0.08, 0, 1)
        return out * vel / (np.abs(out).max() + 1e-9)
    for h, nome in enumerate(PROG):
        raiz = CH[nome][1]; t0 = h * HB
        if h < 2:
            if h == 0: add(baixo(raiz, 2 * HB * 0.95, 0.7), t0, gain=0.45)
            continue
        if h == last: add(baixo(raiz, DUR - t0, 0.8), t0, gain=0.45); continue
        prox = CH[PROG[h + 1]][1]
        passo = (raiz + 7 if raiz + 7 <= 50 else raiz - 5) if prox == raiz else (prox - 1 if (h % 2 == 0 and prox - 1 != raiz) else prox + 1)
        add(baixo(raiz, BEAT * 0.92, 0.85), t0 + hum(), gain=0.45); add(baixo(passo, BEAT * 0.9, 0.7), t0 + BEAT + hum(), gain=0.45)

    def vibe(m, dur, vel=0.5):
        n = int((dur + 1.0) * SR); t = np.arange(n) / SR; f = hz(m)
        s = np.sin(2 * np.pi * f * t) + 0.25 * np.exp(-t / 0.15) * np.sin(2 * np.pi * 4.0 * f * t) + 0.06 * np.exp(-t / 0.04) * np.sin(2 * np.pi * 9.9 * f * t)
        trem = 1 - 0.25 * (0.5 + 0.5 * np.sin(2 * np.pi * 5.0 * t))
        return s * np.minimum(t / 0.002, 1) * np.exp(-t / 1.3) * np.clip(1 - (t - dur) / 0.4, 0, 1) * trem * vel
    # melodia: notas do acorde de cada meio compasso, com ritmo sorteado (frases a partir do 5º meio compasso)
    for h in range(4, last + 1):
        notas = sorted(m + 12 for m in CH[PROG[h]][0])
        if h == last: add(vibe(notas[-1] if rng.random() < .5 else notas[-2], 2.5 * BEAT, 0.45), h * HB + hum(), pan=0.3); continue
        ritmo = [(0, 1), (1 + SW, .5)] if rng.random() < .6 else [(0, 1.5), (1 + SW, .4)]
        for b, d in ritmo:
            add(vibe(int(rng.choice(notas[1:])), d * BEAT, rng.uniform(0.40, 0.5)), h * HB + b * BEAT + hum(), pan=0.3)

    def ride(vel):
        n = int(1.2 * SR); t = np.arange(n) / SR
        s = sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) for f in (3150, 4470, 5310, 6890, 8120))
        return (0.4 * s / 5 + hp(rng.normal(0, 1, n), 6000) * 0.5) * np.minimum(t / 0.001, 1) * np.exp(-t / 0.45) * vel
    def tapa(vel):
        n = int(0.3 * SR); t = np.arange(n) / SR; return bp(rng.normal(0, 1, n), 1500, 6000) * np.exp(-t / 0.07) * vel
    def bumbo(vel):
        n = int(0.3 * SR); t = np.arange(n) / SR; return np.sin(2 * np.pi * (52 + 30 * np.exp(-t / 0.02)) * t) * np.exp(-t / 0.12) * vel
    nb = int(round(DUR / BEAT))
    for b in range(nb):
        t0 = b * BEAT; fim = b >= nb - 4
        if b >= 8 and not fim:
            add(ride(0.16 if b % 2 == 0 else 0.13), t0 + hum(), pan=0.35)
            if b % 2 == 1: add(ride(0.08), t0 + BEAT * SW + hum(), pan=0.35)
        if b % 2 == 1 and not fim: add(tapa(0.10 if b < 8 else 0.13), t0 + hum(), pan=-0.1)
        if not fim: add(bumbo(0.05), t0)
    add(ride(0.2), (nb - 4) * BEAT, pan=0.35)

    t = np.arange(N) / SR
    sw = bp(rng.normal(0, 1, N), 2500, 9000) * (0.5 + 0.5 * np.sin(np.pi * ((t / BEAT) % 1))) * 0.035
    sw *= np.clip(1 - (t - (DUR - 4 * BEAT)) / BEAT, 0, 1); L += sw; R += sw * 0.9
    ti = np.arange(int(1.6 * SR)) / SR
    for ch in (L, R):
        ir = lp(rng.normal(0, 1, len(ti)), 5000) * np.exp(-ti / 0.45); ir /= np.abs(ir).sum() ** 0.5 * 30
        ch += fftconvolve(ch, ir)[:N] * 0.5
    m = lp(hp(np.stack([L, R]), 50, 4), 12000).T
    m *= (np.clip((DUR - t) / 1.6, 0, 1) ** 1.5 * np.minimum(t / 0.05, 1))[:, None]
    m *= 10 ** (-1.0 / 20) / np.abs(m).max(); m = np.tanh(m * 1.1) / np.tanh(1.1)
    wavfile.write(out_wav, SR, (m * 32767 * 0.89).astype(np.int16))


# ---------- principal ----------
def quadros(pasta):
    pasta = pathlib.Path(pasta); pasta.mkdir(parents=True, exist_ok=True); ims = []
    for a, b, _ in CENAS:
        t = a + min(b - a - 0.2, 3.2); im = frame(t); im.save(pasta / f"quadro-{t:.1f}.png"); ims.append(im.resize((360, 640)))
    folha = Image.new("RGB", (360 * len(ims), 640), "white")
    for i, im in enumerate(ims): folha.paste(im, (i * 360, 0))
    folha.save(pasta / "folha.png"); print("ok", pasta / "folha.png")

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]; flags = [a for a in sys.argv[1:] if a.startswith("--")]
    if not args: sys.exit(__doc__)
    carregar(args[0]); ok = validar()
    if "--validar" in flags: sys.exit(0 if ok else 1)
    if not ok: sys.exit("BLOQUEADO: ajuste o texto do JSON e rode de novo.")
    if "--quadros" in flags: quadros(args[1] if len(args) > 1 else "/tmp/reel-quadros"); return
    for prog_ in ("ffmpeg", "ffprobe"):
        if not shutil.which(prog_): sys.exit(f"ERRO: {prog_} não encontrado")
    saida = pathlib.Path(args[1] if len(args) > 1 else "/tmp/reel"); saida.mkdir(parents=True, exist_ok=True)
    final = saida / f"mindrise-ia-reel-{C['nome']}.mp4"
    with tempfile.TemporaryDirectory() as tmp:
        with ProcessPoolExecutor(mp_context=multiprocessing.get_context("fork")) as ex:
            fut = ex.submit(trilha, f"{tmp}/trilha.wav")
            outs = list(ex.map(render_cena, [(i, f"{tmp}/cena{i}.mp4") for i in range(len(CENAS))]))
            fut.result()
        pathlib.Path(f"{tmp}/lista.txt").write_text("".join(f"file '{o}'\n" for o in outs))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", f"{tmp}/lista.txt",
                        "-c", "copy", f"{tmp}/mudo.mp4"], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{tmp}/mudo.mp4", "-i", f"{tmp}/trilha.wav",
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=7", "-ar", "44100",
                        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", f"{tmp}/final.mp4"], check=True)
        shutil.move(f"{tmp}/final.mp4", final)
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,duration", "-of", "csv=p=0",
                          str(final)], capture_output=True, text=True).stdout.split()
    print("ok", final, dur)

if __name__ == "__main__":
    main()
