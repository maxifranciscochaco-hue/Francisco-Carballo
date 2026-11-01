#!/usr/bin/env python3
"""Genera el video explicativo: perfil reticulado en galpones / naves industriales
(anclajes, plomos y niveles). Salida: video/nave_reticulado.mp4 (+ .srt y guion).

Uso:  python3 video/generar_video.py
Requiere: Pillow, ffmpeg.
"""
import math, os, subprocess, sys
from multiprocessing import Pool
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, SS = 1280, 720, 24, 2
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)))

# ---------- paleta ----------
BG = (14, 24, 38)
PANEL = (24, 38, 58)
WHITE = (236, 242, 250)
GREY = (140, 156, 176)
STEEL = (120, 170, 220)
CYAN = (70, 200, 220)
GREEN = (110, 210, 140)
ORANGE = (255, 160, 60)
RED = (240, 90, 80)
CONC = (88, 94, 104)
YELLOW = (250, 215, 80)

FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_fc = {}
def font(sz, bold=False):
    k = (sz, bold)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(FB if bold else FR, int(sz * SS))
    return _fc[k]

def mix(c, d, a):
    a = max(0.0, min(1.0, a))
    return tuple(int(c[i] * a + d[i] * (1 - a)) for i in range(3))

def cl(x): return max(0.0, min(1.0, x))
def ease(x):
    x = cl(x); return x * x * (3 - 2 * x)
def r(sec, a, dur=0.8):
    """progreso eased 0..1 de un evento que arranca en a segundos"""
    return ease((sec - a) / dur)

class D:
    def __init__(self):
        self.im = Image.new("RGB", (W * SS, H * SS), BG)
        self.d = ImageDraw.Draw(self.im)
    def P(self, p): return (p[0] * SS, p[1] * SS)
    def line(self, a, b, c=WHITE, w=2, k=1.0):
        """linea de a hacia b dibujada hasta fraccion k"""
        if k <= 0: return
        b2 = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
        self.d.line([self.P(a), self.P(b2)], fill=c, width=int(w * SS))
        rr = w * SS / 2
        for p in (a, b2):
            x, y = self.P(p)
            self.d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=c)
    def dash(self, a, b, c=GREY, w=1.5, seg=10, gap=7, k=1.0):
        L = math.hypot(b[0] - a[0], b[1] - a[1]) * k
        if L <= 0: return
        ux, uy = (b[0] - a[0]) / math.hypot(b[0] - a[0], b[1] - a[1]), (b[1] - a[1]) / math.hypot(b[0] - a[0], b[1] - a[1])
        t = 0
        while t < L:
            e = min(t + seg, L)
            self.d.line([self.P((a[0] + ux * t, a[1] + uy * t)), self.P((a[0] + ux * e, a[1] + uy * e))], fill=c, width=int(w * SS))
            t += seg + gap
    def rect(self, x0, y0, x1, y1, c=PANEL, o=None, w=2):
        x0, x1 = min(x0, x1), max(x0, x1); y0, y1 = min(y0, y1), max(y0, y1)
        self.d.rectangle([x0 * SS, y0 * SS, x1 * SS, y1 * SS], fill=c, outline=o, width=int(w * SS))
    def rrect(self, x0, y0, x1, y1, c=PANEL, o=None, rad=10, w=2):
        self.d.rounded_rectangle([x0 * SS, y0 * SS, x1 * SS, y1 * SS], radius=rad * SS, fill=c, outline=o, width=int(w * SS))
    def poly(self, pts, c, o=None):
        self.d.polygon([self.P(p) for p in pts], fill=c, outline=o)
    def circ(self, x, y, rad, c, o=None):
        self.d.ellipse([(x - rad) * SS, (y - rad) * SS, (x + rad) * SS, (y + rad) * SS], fill=c, outline=o)
    def text(self, xy, s, sz=22, c=WHITE, bold=False, anchor="la", a=1.0):
        if a <= 0: return
        self.d.text(self.P(xy), s, font=font(sz, bold), fill=mix(c, BG, a), anchor=anchor)
    def arrow(self, a, b, c=WHITE, w=2, k=1.0, head=9):
        self.line(a, b, c, w, k)
        if k >= 1:
            ang = math.atan2(b[1] - a[1], b[0] - a[0])
            for s in (-0.45, 0.45):
                self.line(b, (b[0] - head * math.cos(ang + s), b[1] - head * math.sin(ang + s)), c, w)
    def dim(self, a, b, label, c=ORANGE, a_=1.0, off=(0, -12), sz=18):
        col = mix(c, BG, a_)
        self.arrow(a, b, col, 2); self.arrow(b, a, col, 2)
        self.text(((a[0] + b[0]) / 2 + off[0], (a[1] + b[1]) / 2 + off[1]), label, sz, c, True, "mm", a_)
    def out(self):
        return self.im.resize((W, H), Image.LANCZOS)

# ---------- elementos comunes ----------
def header(d, n, title, sec):
    a = r(sec, 0.1, 0.6)
    d.circ(58, 52, 24, ORANGE)
    d.text((58, 52), str(n), 26, BG, True, "mm", a)
    d.text((98, 52), title, 34, WHITE, True, "lm", a)
    d.line((40, 90), (40 + 1200 * a, 90), mix(STEEL, BG, 0.5), 2)

def caption(d, lines, sec, dur):
    """subtitulos: lines = lista de frases repartidas en dur segundos"""
    n = len(lines)
    i = min(n - 1, int(sec / dur * n))
    s = lines[i]
    d.rect(0, 628, W, H, (8, 14, 24))
    t0 = i * dur / n
    a = cl((sec - t0) / 0.3)
    d.text((W / 2, 674), s, 23, WHITE, False, "mm", a)

def legend_item(d, x, y, col, label, a, sub=None):
    d.rect(x, y - 9, x + 18, y + 9, mix(col, BG, a))
    d.text((x + 32, y), label, 22, WHITE, True, "lm", a)
    if sub: d.text((x + 32, y + 24), sub, 16, GREY, False, "lm", a)

# ---------- cercha (perfil reticulado) ----------
def truss_pts(x0, x1, yb, ye, ya, N):
    B = [(x0 + (x1 - x0) * i / N, yb) for i in range(N + 1)]
    T = []
    for i in range(N + 1):
        f = 1 - abs(2 * i / N - 1)
        T.append((x0 + (x1 - x0) * i / N, ye + (ya - ye) * f))
    return B, T

def truss_groups(B, T):
    N = len(B) - 1
    top = [(T[i], T[i + 1]) for i in range(N)]
    bot = [(B[i], B[i + 1]) for i in range(N)]
    ver = [(B[i], T[i]) for i in range(N + 1)]
    dia = []
    for i in range(N):
        if i < N // 2: dia.append((T[i], B[i + 1]))
        else: dia.append((T[i + 1], B[i]))
    return top, bot, ver, dia

def draw_group(d, segs, col, w, k):
    n = len(segs)
    for i, (a, b) in enumerate(segs):
        kk = cl(k * n - i)
        d.line(a, b, col, w, kk)

def support(d, x, y, a=1.0):
    d.poly([(x, y), (x - 14, y + 20), (x + 14, y + 20)], mix(GREY, BG, a))

# ================= ESCENAS =================
def s_title(d, sec, dur):
    a = r(sec, 0.2, 1.0)
    # silueta de nave de fondo
    B, T = truss_pts(190, 1090, 470, 440, 330, 12)
    top, bot, ver, dia = truss_groups(B, T)
    k = r(sec, 0.3, 2.5)
    for g, col in ((top, STEEL), (bot, STEEL), (ver, mix(STEEL, BG, 0.6)), (dia, mix(STEEL, BG, 0.6))):
        draw_group(d, g, mix(col, BG, 0.55), 3, k)
    d.line((190, 440), (190, 590), mix(STEEL, BG, 0.4), 8, k)
    d.line((1090, 440), (1090, 590), mix(STEEL, BG, 0.4), 8, k)
    d.line((120, 590), (1160, 590), mix(GREY, BG, 0.5), 3, k)
    d.text((W / 2, 170), "ESTRUCTURA DE PERFIL RETICULADO", 44, WHITE, True, "mm", a)
    d.text((W / 2, 225), "en galpones y naves industriales", 32, STEEL, False, "mm", a)
    b = r(sec, 1.4, 0.8)
    d.text((W / 2, 285), "Anclajes  ·  Plomos  ·  Niveles", 30, ORANGE, True, "mm", b)
    d.text((W / 2, 660), "Guía visual para obra: replanteo, montaje y control", 20, GREY, False, "mm", r(sec, 2.4, 0.8))

CAP2 = ["El perfil reticulado, o cercha, es una viga armada formada por barras rectas unidas en nudos.",
        "Los cordones, superior e inferior, resisten la flexión como tracción y compresión.",
        "Los montantes y las diagonales unen los cordones y transmiten el corte.",
        "Cada barra trabaja solo a tracción o compresión: por eso salva grandes luces con poco acero."]
def s_truss(d, sec, dur):
    header(d, 1, "El perfil reticulado (cercha)", sec)
    B, T = truss_pts(100, 800, 470, 430, 290, 8)
    top, bot, ver, dia = truss_groups(B, T)
    draw_group(d, bot, CYAN, 7, r(sec, 1.0, 1.6))
    draw_group(d, top, STEEL, 7, r(sec, 2.2, 1.6))
    draw_group(d, ver, GREEN, 4, r(sec, 5.0, 1.6))
    draw_group(d, dia, ORANGE, 4, r(sec, 6.6, 1.6))
    # nudos
    kn = r(sec, 8.0, 0.6)
    if kn > 0:
        for p in B + T:
            d.circ(p[0], p[1], 6 * kn, WHITE)
        d.text((450, 515), "● nudos (soldados o abulonados con chapa de nudo)", 17, GREY, False, "mm", kn)
    support(d, 100, 470); support(d, 800, 470)
    d.dim((100, 540), (800, 540), "LUZ (L)", ORANGE, r(sec, 0.6, 0.6), (0, 18))
    d.dim((848, 290), (848, 470), "ALTURA", GREY, r(sec, 0.8, 0.6), (-4, 0), 15) if False else None
    legend_item(d, 880, 200, STEEL, "Cordón superior", r(sec, 2.2, 0.5), "comprimido (arriba)")
    legend_item(d, 880, 270, CYAN, "Cordón inferior", r(sec, 1.0, 0.5), "traccionado (abajo)")
    legend_item(d, 880, 340, GREEN, "Montantes", r(sec, 5.0, 0.5), "barras verticales")
    legend_item(d, 880, 410, ORANGE, "Diagonales", r(sec, 6.6, 0.5), "barras inclinadas")
    d.text((880, 500), "Perfiles típicos: ángulos dobles,", 17, GREY, False, "lm", r(sec, 8.0, 0.6))
    d.text((880, 524), "PNC, PNU o tubos estructurales", 17, GREY, False, "lm", r(sec, 8.0, 0.6))
    caption(d, CAP2, sec, dur)

CAP3 = ["En una nave industrial, la cercha apoya sobre columnas y forma el pórtico principal.",
        "Sobre el cordón superior se fijan las correas, que reciben la cubierta.",
        "Las columnas descargan en placas base, ancladas a pedestales de hormigón.",
        "Todo el conjunto depende de tres controles: anclajes, plomos y niveles."]
def s_nave(d, sec, dur):
    header(d, 2, "La nave: pórtico, correas y fundaciones", sec)
    gy = 560
    xl, xr = 160, 760
    ytop = 360
    k = r(sec, 0.6, 1.2)
    # terreno y pedestales
    d.line((60, gy), (1220, gy), GREY, 3, r(sec, 0.1, 0.8))
    for x in (xl, xr):
        d.rect(x - 34, gy, x + 34, gy + 50, CONC)
    # columnas
    for x in (xl, xr):
        d.line((x, gy), (x, ytop), STEEL, 12, k)
        d.rect(x - 28, gy - 6, x + 28, gy, mix(YELLOW, BG, k))
    # cercha
    B, T = truss_pts(xl, xr, ytop, ytop - 26, ytop - 150, 10)
    top, bot, ver, dia = truss_groups(B, T)
    kt = r(sec, 2.0, 2.0)
    draw_group(d, bot, CYAN, 5, kt); draw_group(d, top, STEEL, 5, kt)
    draw_group(d, ver, GREEN, 3, kt); draw_group(d, dia, ORANGE, 3, kt)
    # correas
    kc = r(sec, 4.6, 1.2)
    if kc > 0:
        for p in T:
            d.rect(p[0] - 7, p[1] - 14 * kc - 6, p[0] + 7, p[1] - 6, mix(YELLOW, BG, kc), None)
    # etiquetas con linea guia
    def label(txt, p, q, col, t0):
        a = r(sec, t0, 0.6)
        if a <= 0: return
        d.line(p, q, mix(col, BG, a), 2)
        d.circ(p[0], p[1], 4, mix(col, BG, a))
        d.text((q[0] + 8, q[1]), txt, 20, WHITE, True, "lm", a)
    label("Cabreada / cercha", (T[7][0], T[7][1] + 30), (860, 270), CYAN, 3.6)
    label("Correas + cubierta", (T[6][0], T[6][1] - 16), (860, 215), YELLOW, 5.4)
    label("Cumbrera", (T[5][0], T[5][1] - 16), (860, 160), GREY, 6.0) if False else None
    label("Columna", (xr, 450), (860, 400), STEEL, 7.0)
    label("Placa base + anclajes", (xr + 28, gy - 3), (860, 520), YELLOW, 7.8)
    label("Pedestal de H°A°", (xr + 34, gy + 30), (860, 585), GREY, 8.6)
    # flecha de luz
    d.dim((xl, 625 - 10), (xr, 625 - 10), "LUZ", ORANGE, r(sec, 9.2, 0.6), (0, -16)) if False else None
    caption(d, CAP3, sec, dur)

CAP4 = ["Primero se hormigona el pedestal con los bulones de anclaje ubicados con una plantilla.",
        "Los bulones son barras roscadas con gancho o placa en el extremo embebido.",
        "Se colocan tuercas de nivelación y sobre ellas se apoya la placa base.",
        "Luego arandela, tuerca y contratuerca; por último, el grout sin retracción bajo la placa.",
        "La posición de cada bulón se controla en planta: un error acá se arrastra a toda la nave."]
def s_anclajes(d, sec, dur):
    header(d, 3, "Anclajes: bulones, placa base y grout", sec)
    cx = 400
    yt = 470                      # tope pedestal
    kp = r(sec, 0.4, 1.0)
    d.rect(cx - 200, yt, cx + 200, yt + 150 * kp + 1, CONC)
    d.text((cx, yt + 120), "Pedestal H°A°", 20, WHITE, True, "mm", kp)
    # bulones
    kb = r(sec, 1.8, 1.4)
    bx = (cx - 120, cx + 120)
    ytip = yt - 78
    for x in bx:
        yb = yt + 105
        yi = yb - (yb - ytip) * kb
        d.line((x, yb), (x, yi), STEEL, 7)
        d.line((x, yb), (x + 22, yb), STEEL, 7, kb)           # gancho
        # rosca
        for yy in range(int(yi), int(yt - 6), 7):
            d.line((x - 5, yy), (x + 5, yy + 3), mix(WHITE, BG, 0.5), 1)
    # plantilla
    kt = r(sec, 1.4, 0.8) * (1 - r(sec, 3.8, 0.6))
    if kt > 0:
        d.rect(cx - 150, yt - 150, cx + 150, yt - 138, mix(ORANGE, BG, kt))
        d.text((cx, yt - 165), "plantilla de replanteo", 17, ORANGE, False, "mm", kt)
    # tuercas de nivelacion
    kn = r(sec, 3.4, 0.6)
    ynut = yt - 30
    if kn > 0:
        for x in bx:
            d.rect(x - 15, ynut - 12 * kn, x + 15, ynut, mix(ORANGE, BG, kn))
    # placa base cayendo
    kpl = r(sec, 4.6, 1.4)
    yplate = (yt - 150) + (ynut - 12 - 16 - (yt - 150)) * kpl
    if kpl > 0:
        d.rect(cx - 170, yplate, cx + 170, yplate + 16, YELLOW)
        # columna
        d.rect(cx - 32, yplate - 250, cx + 32, yplate, STEEL)
        d.rect(cx - 32, yplate - 250, cx - 22, yplate, mix(STEEL, WHITE, 0.3))
        d.rect(cx + 22, yplate - 250, cx + 32, yplate, mix(STEEL, WHITE, 0.3))
    # arandela + tuerca + contratuerca
    kt2 = r(sec, 6.4, 0.8)
    if kt2 > 0:
        yp = yplate + 16
        for x in bx:
            d.rect(x - 18, yp - 14 - 3, x + 18, yp - 14, mix(GREY, BG, kt2))   # (no se ve sobre placa -> arandela sobre)
        for x in bx:
            d.rect(x - 18, yplate - 4, x + 18, yplate, mix(WHITE, BG, kt2))
            d.rect(x - 15, yplate - 22 * kt2, x + 15, yplate - 4, mix(ORANGE, BG, kt2))
            d.rect(x - 15, yplate - 40 * kt2, x + 15, yplate - 22 * kt2, mix(ORANGE, BG, kt2 * 0.8))
    # grout
    kg = r(sec, 8.0, 1.2)
    if kg > 0:
        gy0 = yplate + 16
        d.rect(cx - 180, gy0, cx - 180 + 360 * kg, yt, (150, 160, 150))
        d.text((cx, (gy0 + yt) / 2), "grout", 15, BG, True, "mm", kg)
    # niveles / acotaciones
    ka = r(sec, 9.6, 0.7)
    if ka > 0:
        d.dim((cx - 120, yt + 190 - 40), (cx + 120, yt + 190 - 40), "±3 mm", ORANGE, ka, (0, 14), 17) if False else None
        d.dim((cx - 120, yt - 175 + 0), (cx + 120, yt - 175), "entre bulones: ± 3 mm (ref.)", ORANGE, ka, (0, -16), 16) if False else None
    # leyenda
    def item(y, col, t, sub, t0):
        legend_item(d, 760, y, col, t, r(sec, t0, 0.5), sub)
    item(180, STEEL, "Bulón de anclaje", "barra roscada + gancho", 2.4)
    item(250, ORANGE, "Tuercas de nivelación", "fijan la cota de la placa", 4.0)
    item(320, YELLOW, "Placa base", "reparte la carga al hormigón", 5.8)
    item(390, WHITE, "Arandela + tuerca + contratuerca", "ajuste final, sin aflojarse", 7.0)
    item(460, (150, 160, 150), "Grout sin retracción", "25 a 50 mm bajo la placa", 8.6)
    kk = r(sec, 9.8, 0.6)
    if kk > 0:
        d.rrect(760, 510, 1230, 590, PANEL, ORANGE, 8, 2)
        d.text((775, 535), "Tolerancia de referencia:", 18, ORANGE, True, "lm", kk)
        d.text((775, 562), "±3 mm entre bulones del grupo (AISC)", 18, WHITE, False, "lm", kk)
    caption(d, CAP4, sec, dur)

CAP5 = ["El plomo mide si la columna está perfectamente vertical.",
        "Se busca con plomada, nivel láser o estación total, siempre en dos ejes: X e Y.",
        "Si la columna está inclinada, se corrige con las tuercas de nivelación y tensores provisorios.",
        "Tolerancia de referencia: desvío máximo de la altura dividido 500.",
        "Ejemplo: en una columna de 8 metros, el desvío admisible es de 16 milímetros."]
def s_plomo(d, sec, dur):
    header(d, 4, "Plomos: verticalidad de columnas", sec)
    bx, gy, top = 380, 560, 175
    corr = r(sec, 4.2, 3.0)
    dx = 70 * (1 - corr)
    col = mix(GREEN, RED, corr)
    tx = bx + dx
    # suelo
    d.line((200, gy), (560, gy), GREY, 3)
    d.rect(bx - 60, gy, bx + 60, gy + 30, CONC)
    # eje teorico vertical
    d.dash((bx, top - 20), (bx, gy), mix(GREEN, BG, r(sec, 0.8, 0.6)), 2)
    # columna inclinada
    ang = math.atan2(dx, gy - top)
    nx, ny = math.cos(ang) * 14, math.sin(ang) * 14
    pts = [(bx - 14, gy), (bx + 14, gy), (tx + 14, top), (tx - 14, top)]
    d.poly(pts, mix(STEEL, BG, 0.9))
    d.line((bx, gy), (tx, top), col, 3)
    d.rect(bx - 28, gy - 8, bx + 28, gy, YELLOW)
    # plomada
    kp = r(sec, 1.8, 1.0)
    if kp > 0:
        d.line((tx, top), (tx, top + (gy - top - 18) * kp), WHITE, 2)
        py = top + (gy - top - 18) * kp
        d.poly([(tx, py + 18), (tx - 9, py), (tx + 9, py)], WHITE)
    # desvio
    if dx > 2:
        d.dim((bx, gy + 48), (tx, gy + 48), "Δ", ORANGE, r(sec, 2.8, 0.5), (0, 16), 20)
    kh = r(sec, 0.6, 0.6)
    d.dim((300, top), (300, gy), "H", GREY, kh, (-14, 0), 20)
    # estado
    st = "FUERA DE PLOMO" if corr < 0.98 else "EN PLOMO ✔"
    d.text((bx, top - 34), st, 22, col, True, "mm", r(sec, 2.4, 0.5))
    # panel derecho
    k1 = r(sec, 4.0, 0.7)
    d.rrect(660, 130, 1235, 270, PANEL, STEEL, 10, 2)
    d.text((685, 160), "Control en dos ejes", 22, WHITE, True, "lm", r(sec, 1.2, 0.6))
    d.text((685, 195), "Verificar plomo en X (frente) y en Y (lateral)", 17, GREY, False, "lm", r(sec, 1.2, 0.6))
    d.text((685, 225), "Instrumentos: plomada · láser · estación total", 17, GREY, False, "lm", r(sec, 1.2, 0.6))
    d.rrect(660, 295, 1235, 435, PANEL, ORANGE, 10, 2)
    kt = r(sec, 7.0, 0.7)
    d.text((685, 325), "Tolerancia de referencia", 22, ORANGE, True, "lm", kt)
    d.text((685, 365), "Δ  ≤  H / 500", 34, WHITE, True, "lm", kt)
    d.text((685, 405), "Ejemplo: H = 8 m  →  Δ ≤ 16 mm", 19, GREY, False, "lm", r(sec, 8.4, 0.7))
    d.rrect(660, 460, 1235, 590, PANEL, GREEN, 10, 2)
    kc = r(sec, 5.0, 0.7)
    d.text((685, 490), "Cómo se corrige", 22, GREEN, True, "lm", kc)
    d.text((685, 520), "• tuercas de nivelación (ajuste fino)", 17, WHITE, False, "lm", kc)
    d.text((685, 545), "• tensores / riendas provisorias", 17, WHITE, False, "lm", kc)
    d.text((685, 570), "• re-verificar tras ajustar y ajustar tuercas", 17, WHITE, False, "lm", kc)
    caption(d, CAP5, sec, dur)

CAP6 = ["Los niveles fijan las cotas de cada elemento respecto de una referencia única de obra.",
        "Se transfieren con nivel óptico, láser rotativo o hilo de nylon entre columnas.",
        "Hay cuatro cotas clave: pedestal, placa base, apoyo de la cabreada y cumbrera.",
        "Un error de nivel en las placas se traduce en cerchas torcidas y correas desalineadas.",
        "Además, la cercha se fabrica con contraflecha para compensar su propio peso."]
def s_niveles(d, sec, dur):
    header(d, 5, "Niveles: cotas de la estructura", sec)
    gy = 560
    xl, xr = 140, 640
    ytop = 330
    # estructura
    d.line((60, gy), (700, gy), GREY, 3)
    for x in (xl, xr):
        d.rect(x - 30, gy, x + 30, gy + 30, CONC)
        d.line((x, gy), (x, ytop), STEEL, 10)
        d.rect(x - 24, gy - 6, x + 24, gy, YELLOW)
    B, T = truss_pts(xl, xr, ytop, ytop - 20, ytop - 120, 8)
    # contraflecha: cordon inferior levemente curvo
    top, bot, ver, dia = truss_groups(B, T)
    cf = 14
    def lift(p):
        t = (p[0] - xl) / (xr - xl)
        return (p[0], p[1] - cf * 4 * t * (1 - t) * r(sec, 7.5, 1.2))
    for g, col, w in ((top, STEEL, 5), (bot, CYAN, 5), (ver, GREEN, 3), (dia, ORANGE, 3)):
        draw_group(d, [(lift(a), lift(b)) for a, b in g], col, w, 1)
    # niveles
    levels = [("Cota cumbrera", "+9,50", T[4][1] - cf * r(sec, 7.5, 1.2) , 5.2),
              ("Apoyo de cabreada", "+7,50", ytop, 3.8),
              ("Cara sup. placa base", "±0,00", gy - 6, 2.6),
              ("Cara sup. pedestal", "−0,05", gy + 0, 1.4)]
    for i, (n, v, y, t0) in enumerate(levels):
        a = r(sec, t0, 0.7)
        if a <= 0: continue
        yy = y if i != 3 else gy + 14
        ly = yy if i != 3 else yy + 22
        d.dash((60, yy), (730 * a + 60 if a < 1 else 730, yy), mix(ORANGE, BG, a), 2, 12, 6)
        d.rrect(740, ly - 20, 1000, ly + 20, PANEL, ORANGE, 8, 2)
        d.text((752, ly), n, 17, WHITE, True, "lm", a)
        d.text((1010, ly), v, 22, ORANGE, True, "lm", a)
    # barrido laser
    kl = r(sec, 0.6, 1.2)
    if sec < 3.8:
        d.circ(80, gy - 6 - 2, 6 * (1 if kl > 0 else 0), RED)
        d.text((80, gy - 28), "nivel láser", 15, RED, False, "mm", kl)
    d.text((865, 112), "Cotas de ejemplo (m)", 16, GREY, False, "mm", r(sec, 1.0, 0.5))
    kc = r(sec, 7.5, 0.8)
    d.text((385, ytop + 70), "contraflecha (exagerada)", 15, CYAN, False, "mm", kc)
    d.text((1010, 610 - 30), "", 12, WHITE)
    caption(d, CAP6, sec, dur)

CAP7 = ["La secuencia de montaje ordena todos los controles.",
        "Uno: replanteo y verificación de bulones, planta y cotas, antes de izar nada.",
        "Dos y tres: nivelar placas, colocar columnas y plomarlas con tensores provisorios.",
        "Cuatro: izar y fijar las cabreadas controlando el nivel de apoyo.",
        "Cinco y seis: arriostrar, colocar correas y recién después hacer el grout final."]
def s_secuencia(d, sec, dur):
    header(d, 6, "Secuencia de montaje y controles", sec)
    steps = [("Replanteo", "Verificar bulones: posición en planta, proyección y rosca limpia"),
             ("Placas y columnas", "Nivelar con tuercas, izar columnas y apoyar"),
             ("Plomo", "Plomar en 2 ejes y asegurar con tensores provisorios"),
             ("Cabreadas", "Izar, controlar nivel de apoyo y alineación; fijar"),
             ("Arriostramientos", "Cruces, correas y tensores antes de cargar o soltar el aparejo"),
             ("Cierre", "Control final de plomos y niveles, ajuste de tuercas y grout")]
    for i, (t, s) in enumerate(steps):
        y = 150 + i * 78
        a = r(sec, 1.2 + i * 1.5, 0.7)
        if a <= 0: continue
        x = 60 + (1 - a) * 40
        d.rrect(x, y - 30, x + 1160, y + 36, PANEL, mix(STEEL, BG, 0.6), 10, 2)
        d.circ(x + 38, y + 3, 24, ORANGE)
        d.text((x + 38, y + 3), str(i + 1), 26, BG, True, "mm", a)
        d.text((x + 82, y - 8), t, 24, WHITE, True, "lm", a)
        d.text((x + 82, y + 20), s, 18, GREY, False, "lm", a)
    caption(d, CAP7, sec, dur)

CAP8 = ["Antes de dar por terminado el montaje, repasá esta lista.",
        "Recordá que los valores mostrados son de referencia: manda el proyecto y el pliego.",
        "Seguridad primero: arnés, línea de vida y nada se suelta hasta quedar fijo."]
def s_checklist(d, sec, dur):
    header(d, 7, "Checklist de control en obra", sec)
    items = [("Anclajes", "posición, proyección y rosca de cada bulón", ORANGE),
             ("Placas base", "nivel, asiento firme y grout completo", YELLOW),
             ("Columnas", "plomo en X e Y dentro de H/500 (ref.)", GREEN),
             ("Cabreadas", "nivel de apoyo, alineación y contraflecha", CYAN),
             ("Arriostres y correas", "colocados antes de cargar la estructura", STEEL),
             ("Seguridad", "arnés, líneas de vida y aparejos verificados", RED)]
    for i, (t, s, c) in enumerate(items):
        y = 150 + i * 62
        a = r(sec, 0.8 + i * 0.9, 0.6)
        d.text((70, y), "✔", 30, c, True, "lm", a)
        d.text((125, y - 10), t, 24, WHITE, True, "lm", a)
        d.text((125, y + 16), s, 18, GREY, False, "lm", a)
    kb = r(sec, 6.5, 0.8)
    d.rrect(60, 540, 1220, 612, PANEL, ORANGE, 10, 2)
    d.text((W / 2, 566), "Valores de referencia (AISC / CIRSOC 301-304): verificar siempre", 18, ORANGE, True, "mm", kb)
    d.text((W / 2, 592), "con el proyecto, el cálculo y el pliego de la obra.", 18, WHITE, False, "mm", kb)
    caption(d, CAP8, sec, dur)

SCENES = [(s_title, 5, ["Estructura de perfil reticulado para galpones y naves industriales: anclajes, plomos y niveles."]),
          (s_truss, 11, CAP2), (s_nave, 11, CAP3), (s_anclajes, 14, CAP4),
          (s_plomo, 12, CAP5), (s_niveles, 12, CAP6), (s_secuencia, 11, CAP7), (s_checklist, 10, CAP8)]

def starts():
    t, out = 0, []
    for f, dur, cap in SCENES:
        out.append(t); t += dur
    return out, t

def render(i):
    st, total = starts()
    t = i / FPS
    for k, (f, dur, cap) in enumerate(SCENES):
        if t < st[k] + dur or k == len(SCENES) - 1:
            break
    sec = min(t - st[k], dur - 1e-3)
    d = D()
    f(d, sec, dur)
    # fundido de salida/entrada
    fade = min(cl(sec / 0.4), cl((dur - sec) / 0.4))
    im = d.out()
    if fade < 1:
        im = Image.blend(Image.new("RGB", (W, H), BG), im, fade)
    return im.tobytes()

def fmt(t):
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h:02d}:{m:02d}:{int(s):02d},{int((s % 1) * 1000):03d}"

def write_text():
    st, total = starts()
    srt, md, n = [], ["# Guion de locución — Estructura de perfil reticulado en naves industriales\n"], 1
    titles = ["Título", "1. El perfil reticulado", "2. La nave", "3. Anclajes", "4. Plomos", "5. Niveles", "6. Secuencia de montaje", "7. Checklist"]
    for k, (f, dur, cap) in enumerate(SCENES):
        md.append(f"\n## {titles[k]}  ({int(st[k])}–{int(st[k] + dur)} s)\n")
        for j, s in enumerate(cap):
            a = st[k] + j * dur / len(cap); b = st[k] + (j + 1) * dur / len(cap)
            srt.append(f"{n}\n{fmt(a)} --> {fmt(b - 0.05)}\n{s}\n"); n += 1
            md.append(f"- {s}")
    open(os.path.join(OUT, "nave_reticulado.srt"), "w", encoding="utf-8").write("\n".join(srt))
    open(os.path.join(OUT, "guion_locucion.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    return total

if __name__ == "__main__":
    total = write_text()
    nfr = int(total * FPS)
    if len(sys.argv) > 1:   # modo prueba: python generar_video.py 12.5 -> PNG de ese segundo
        t = float(sys.argv[1]); i = int(t * FPS)
        Image.frombytes("RGB", (W, H), render(i)).save(sys.argv[2] if len(sys.argv) > 2 else "frame.png")
        sys.exit()
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                           "-preset", "medium", "-movflags", "+faststart", os.path.join(OUT, "nave_reticulado.mp4")],
                          stdin=subprocess.PIPE)
    with Pool() as p:
        for n, b in enumerate(p.imap(render, range(nfr), chunksize=8)):
            ff.stdin.write(b)
            if n % 240 == 0: print(f"{n}/{nfr}", flush=True)
    ff.stdin.close(); ff.wait()
    print("listo", total, "s")
