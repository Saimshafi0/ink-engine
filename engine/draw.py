"""InkEngine - Mode A drawing library (pure PIL, no AI).

Everything is drawn in a logical 1920x1080 space (or any size) and
supersampled by K for smooth, slightly wobbly "hand drawn" lines.
"""
import math, random, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(os.path.dirname(HERE), "assets", "fonts")

INK = (28, 26, 24)
CREAM = (243, 235, 211)
WHITE = (255, 255, 255)
YELLOW = (255, 225, 53)
RED = (214, 58, 47)
GREEN = (62, 160, 82)
C = dict(  # muted earthy palette
    sand=(228, 204, 152), sand2=(209, 180, 125), olive=(134, 146, 86), leaf=(112, 156, 92),
    leaf2=(80, 124, 74), dleaf=(58, 96, 60), bark=(128, 88, 58), brown=(150, 104, 66),
    clay=(196, 112, 76), clay2=(170, 92, 62), stone=(166, 160, 150), stone2=(130, 125, 118),
    sky=(196, 222, 230), sky2=(170, 206, 222), sea=(96, 160, 186), sea2=(70, 132, 164),
    snow=(242, 246, 250), ice=(206, 226, 238), night=(38, 46, 72), night2=(56, 66, 98),
    gold=(234, 186, 64), gold2=(200, 150, 40), fire=(240, 132, 48), fire2=(252, 202, 76),
    grass=(150, 178, 98), grass2=(128, 160, 84), wall=(232, 214, 178), roof=(160, 100, 64),
    cave=(110, 96, 86), cave2=(84, 72, 66), pink=(232, 132, 140), purple=(140, 110, 170),
    grey=(200, 200, 196), paper=(246, 236, 206), fur=(150, 112, 80), fur2=(120, 88, 62),
    mammoth=(140, 100, 72), city=(206, 200, 192), city2=(176, 170, 164), beer=(236, 170, 52),
    blue=(86, 136, 200),
)

_font_cache = {}


def font(name, size, weight=None):
    key = (name, int(size), weight)
    if key not in _font_cache:
        path = os.path.join(FONTS, {"oswald": "Oswald.ttf", "bangers": "Bangers-Regular.ttf",
                                    "hand": "PatrickHand-Regular.ttf",
                                    "lucky": "LuckiestGuy-Regular.ttf"}[name])
        try:
            f = ImageFont.truetype(path, int(size))
            if name == "oswald":
                try:
                    f.set_variation_by_name(weight or "Bold")
                except Exception:
                    pass
        except Exception:
            f = ImageFont.load_default()
        _font_cache[key] = f
    return _font_cache[key]


class Pen:
    """Draws in logical coords; k = supersample factor."""

    def __init__(self, img, k=2, seed=1, wobble=1.0):
        self.img = img
        self.d = ImageDraw.Draw(img)
        self.k = k
        self.rng = random.Random(seed)
        self.wob = wobble

    # ---------- primitives ----------
    def _jit(self, pts, amp):
        """Subdivide polyline and add smooth perpendicular wobble."""
        out = []
        ph = self.rng.uniform(0, 6.28)
        fr = self.rng.uniform(0.012, 0.022)
        acc = 0.0
        for i in range(len(pts) - 1):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            L = math.hypot(x1 - x0, y1 - y0)
            n = max(1, int(L / 14))
            nx, ny = (-(y1 - y0) / L, (x1 - x0) / L) if L > 0 else (0, 0)
            for j in range(n):
                t = j / n
                s = acc + L * t
                o = amp * (math.sin(s * fr + ph) * 0.7 + math.sin(s * fr * 2.7 + ph * 1.3) * 0.3)
                out.append((x0 + (x1 - x0) * t + nx * o, y0 + (y1 - y0) * t + ny * o))
            acc += L
        out.append(pts[-1])
        return out

    def line(self, pts, w=5, color=INK, wob=None):
        amp = (1.3 if wob is None else wob) * self.wob
        p = self._jit(pts, amp) if amp > 0 else pts
        k = self.k
        P = [(x * k, y * k) for x, y in p]
        W = max(1, int(w * k))
        self.d.line(P, fill=color, width=W, joint="curve")
        r = W / 2
        for x, y in (P[0], P[-1]):
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=color)

    def poly(self, pts, fill=None, w=5, color=INK, wob=None):
        amp = (1.3 if wob is None else wob) * self.wob
        closed = list(pts) + [pts[0]]
        p = self._jit(closed, amp) if amp > 0 else closed
        k = self.k
        P = [(x * k, y * k) for x, y in p]
        if fill is not None:
            self.d.polygon(P, fill=fill)
        if w:
            W = max(1, int(w * k))
            self.d.line(P + [P[1]] if len(P) > 1 else P, fill=color, width=W, joint="curve")

    def ell_pts(self, cx, cy, rx, ry, n=None, a0=0, a1=360, wob=True):
        n = n or max(24, int((rx + ry) / 3))
        ph1, ph2 = self.rng.uniform(0, 6.3), self.rng.uniform(0, 6.3)
        pts = []
        for i in range(n + 1):
            a = math.radians(a0 + (a1 - a0) * i / n)
            f = 1 + ((0.012 * math.sin(3 * a + ph1) + 0.008 * math.sin(5 * a + ph2)) if wob else 0) * self.wob
            pts.append((cx + rx * f * math.cos(a), cy + ry * f * math.sin(a)))
        return pts

    def ellipse(self, cx, cy, rx, ry, fill=None, w=5, color=INK):
        pts = self.ell_pts(cx, cy, rx, ry)[:-1]
        self.poly(pts, fill=fill, w=w, color=color, wob=0)

    def circle(self, cx, cy, r, fill=None, w=5, color=INK):
        self.ellipse(cx, cy, r, r, fill, w, color)

    def dot(self, cx, cy, r, color=INK):
        k = self.k
        self.d.ellipse([(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k], fill=color)

    def arc(self, cx, cy, rx, ry, a0, a1, w=5, color=INK):
        self.line(self.ell_pts(cx, cy, rx, ry, n=20, a0=a0, a1=a1, wob=False), w, color, wob=0.4)

    def rect(self, x0, y0, x1, y1, fill=None, w=5, color=INK):
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill, w, color)

    def rrect(self, x0, y0, x1, y1, r, fill=None, w=5, color=INK):
        pts = []
        for cx, cy, a in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
            for i in range(7):
                aa = math.radians(a + 90 * i / 6)
                pts.append((cx + r * math.cos(aa), cy + r * math.sin(aa)))
        self.poly(pts, fill, w, color, wob=0.6)

    def bez(self, p0, p1, p2, n=16):
        return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                 (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
                for t in (i / n for i in range(n + 1))]

    def text(self, x, y, s, size, fname="hand", color=INK, anchor="mm", stroke=0, stroke_color=INK, weight=None):
        k = self.k
        f = font(fname, size * k, weight)
        self.d.text((x * k, y * k), s, font=f, fill=color, anchor=anchor,
                    stroke_width=int(stroke * k), stroke_fill=stroke_color)

    def text_w(self, s, size, fname="hand", weight=None):
        f = font(fname, size * self.k, weight)
        b = f.getbbox(s)
        return (b[2] - b[0]) / self.k


def new_canvas(w, h, k=2, color=WHITE):
    return Image.new("RGB", (int(w * k), int(h * k)), color)


def finish(img, w, h):
    return img.resize((int(w), int(h)), Image.LANCZOS)


# =====================================================================
#  CHARACTER
# =====================================================================
# Arm points relative to the shoulder, leg points relative to the hip,
# in units of head radius r. y grows downward. "R" = viewer's right.
POSES = {
    "stand":     dict(L=[(-.35, .75), (-.45, 1.45)], R=[(.35, .75), (.45, 1.45)], LL=[(-.25, .8), (-.32, 1.6)], RL=[(.25, .8), (.32, 1.6)]),
    "wave":      dict(L=[(-.35, .75), (-.45, 1.45)], R=[(1.0, .0), (1.4, -.85)], LL=[(-.25, .8), (-.32, 1.6)], RL=[(.25, .8), (.32, 1.6)]),
    "shrug":     dict(L=[(-.75, .55), (-1.35, .05)], R=[(.75, .55), (1.35, .05)], LL=[(-.25, .8), (-.32, 1.6)], RL=[(.25, .8), (.32, 1.6)], open_hands=True),
    "point_up":  dict(L=[(-.35, .75), (-.45, 1.45)], R=[(1.0, -.05), (1.35, -.95)], LL=[(-.25, .8), (-.32, 1.6)], RL=[(.25, .8), (.32, 1.6)], finger="R_up"),
    "point":     dict(L=[(-.35, .75), (-.45, 1.45)], R=[(.8, .25), (1.6, .05)], LL=[(-.25, .8), (-.32, 1.6)], RL=[(.25, .8), (.32, 1.6)], finger="R_side"),
    "point_left": dict(L=[(-.8, .25), (-1.6, .05)], R=[(.35, .75), (.45, 1.45)], LL=[(-.25, .8), (-.32, 1.6)], RL=[(.25, .8), (.32, 1.6)], finger="L_side"),
    "think":     dict(L=[(-.35, .75), (-.45, 1.45)], R=[(.85, .65), (.32, -.2)], LL=[(-.25, .8), (-.32, 1.6)], RL=[(.25, .8), (.32, 1.6)], chin=True),
    "crossed":   dict(L=[(-.6, .55), (.5, .6)], R=[(.6, .62), (-.5, .52)], LL=[(-.25, .8), (-.32, 1.6)], RL=[(.25, .8), (.32, 1.6)]),
    "facepalm":  dict(L=[(-.35, .75), (-.45, 1.45)], R=[(1.4, -.6), (.5, -1.95)], LL=[(-.25, .8), (-.32, 1.6)], RL=[(.25, .8), (.32, 1.6)], front=True),
    "hips":      dict(L=[(-.75, .45), (-.3, 1.0)], R=[(.75, .45), (.3, 1.0)], LL=[(-.3, .8), (-.45, 1.6)], RL=[(.3, .8), (.45, 1.6)]),
    "celebrate": dict(L=[(-.8, -.3), (-1.2, -1.2)], R=[(.8, -.3), (1.2, -1.2)], LL=[(-.3, .8), (-.45, 1.6)], RL=[(.3, .8), (.45, 1.6)]),
    "scared":    dict(L=[(-1.0, .35), (-1.25, -.55)], R=[(1.0, .35), (1.25, -.55)], LL=[(-.35, .75), (-.25, 1.6)], RL=[(.35, .75), (.25, 1.6)]),
    "walk":      dict(L=[(-.25, .75), (.25, 1.35)], R=[(.2, .75), (-.35, 1.3)], LL=[(.35, .75), (.75, 1.45)], RL=[(-.3, .8), (-.55, 1.5)]),
    "run":       dict(L=[(.55, .55), (.95, .1)], R=[(-.6, .6), (-1.0, .3)], LL=[(.7, .55), (.65, 1.4)], RL=[(-.45, .75), (-1.1, 1.15)], lean=.25),
    "sit":       dict(L=[(-.4, .7), (-.15, 1.1)], R=[(.4, .7), (.15, 1.1)], LL=[(.8, .05), (.85, .85)], RL=[(.65, .1), (.6, .9)], sit=True),
    "trade":     dict(L=[(-.35, .75), (-.45, 1.45)], R=[(.75, .5), (1.45, .35)], LL=[(-.25, .8), (-.32, 1.6)], RL=[(.25, .8), (.32, 1.6)], holds="R"),
    "give":      dict(L=[(-.75, .5), (-1.45, .35)], R=[(.35, .75), (.45, 1.45)], LL=[(-.25, .8), (-.32, 1.6)], RL=[(.25, .8), (.32, 1.6)], holds="L"),
    "carry":     dict(L=[(-.85, -.9), (-.45, -2.3)], R=[(.85, -.9), (.45, -2.3)], LL=[(-.25, .8), (-.32, 1.6)], RL=[(.25, .8), (.32, 1.6)], holds="top"),
    "hold":      dict(L=[(-.35, .75), (-.45, 1.45)], R=[(.7, .7), (1.1, .35)], LL=[(-.25, .8), (-.32, 1.6)], RL=[(.25, .8), (.32, 1.6)], holds="R"),
    "dance":     dict(L=[(-.7, .0), (-.6, -.8)], R=[(.75, .45), (1.3, .7)], LL=[(-.4, .7), (-.2, 1.6)], RL=[(.5, .55), (.9, 1.1)]),
    "explain":   dict(L=[(-.35, .75), (-.45, 1.45)], R=[(.7, .6), (1.3, .25)], LL=[(-.25, .8), (-.32, 1.6)], RL=[(.25, .8), (.32, 1.6)], open_hands=True),
    "throw":     dict(L=[(-.6, .3), (-1.2, .05)], R=[(.65, -.2), (.4, -1.0)], LL=[(-.4, .75), (-.65, 1.55)], RL=[(.35, .8), (.45, 1.6)], holds="R"),
    "dig":       dict(L=[(.5, .5), (1.0, .9)], R=[(.6, .45), (1.15, .6)], LL=[(-.3, .75), (-.5, 1.6)], RL=[(.3, .8), (.4, 1.6)], lean=.15),
    "lie":       dict(L=[(-.35, .75), (-.45, 1.45)], R=[(.35, .75), (.45, 1.45)], LL=[(-.12, .8), (-.12, 1.6)], RL=[(.12, .8), (.12, 1.6)], lie=True),
}
FACES = ["neutral", "happy", "smug", "thinking", "confused", "shocked", "sad", "scared", "angry",
         "sweating", "laugh", "unimpressed", "disgusted", "sleepy", "excited", "worried"]
POSE_ALIAS = {"point_right": "point", "arms_crossed": "crossed", "cross": "crossed", "hands_on_hips": "hips",
              "happy": "celebrate", "cheer": "celebrate", "idle": "stand", "neutral": "stand",
              "thinking": "think", "talk": "explain", "present": "explain", "hunt": "throw",
              "sleep": "lie", "farm": "dig", "work": "dig", "eat": "hold", "drink": "hold", "afraid": "scared"}
FACE_ALIAS = {"surprised": "shocked", "confused": "confused", "curious": "thinking", "smirk": "smug",
              "joy": "happy", "fear": "scared", "mad": "angry", "bored": "unimpressed", "tired": "sleepy",
              "nervous": "worried", "proud": "smug", "gross": "disgusted", "think": "thinking"}


def norm_pose(p):
    p = (p or "stand").lower().strip()
    p = POSE_ALIAS.get(p, p)
    return p if p in POSES else "stand"


def norm_face(f):
    f = (f or "neutral").lower().strip()
    f = FACE_ALIAS.get(f, f)
    return f if f in FACES else "neutral"


def draw_face(pen, cx, cy, r, face, blink=False, mouth=0.0, flip=False, lw=5):
    s = -1 if flip else 1
    ex, ey = 0.36 * r, -0.08 * r
    er = 0.085 * r
    look = {"thinking": (.05 * r, -.1 * r), "confused": (0, 0)}.get(face, (0, 0))
    W = lw * 0.85

    def eyes(rr=er, dx=0, dy=0):
        for side in (-1, 1):
            pen.dot(cx + side * ex + dx, cy + ey + dy, rr)

    def closed_eyes(curve=False):
        for side in (-1, 1):
            x = cx + side * ex
            if curve:
                pen.arc(x, cy + ey + .04 * r, .12 * r, .1 * r, 200, 340, W)
            else:
                pen.line([(x - .11 * r, cy + ey), (x + .11 * r, cy + ey)], W, wob=0.2)

    def brow(side, y_in, y_out, lift=0):
        x = cx + side * ex
        pen.line([(x - side * .14 * r, cy + ey - y_in * r - lift), (x + side * .16 * r, cy + ey - y_out * r - lift)], W, wob=0.2)

    def lids():
        for side in (-1, 1):
            x = cx + side * ex
            pen.line([(x - .15 * r, cy + ey - .02 * r), (x + .15 * r, cy + ey - .02 * r)], W, wob=0.2)

    my = cy + 0.42 * r
    talk = mouth > 0.3

    # ---- eyes / brows
    if face in ("laugh", "excited") and not blink:
        if face == "laugh":
            closed_eyes(curve=True)
        else:
            eyes(er * 1.25)
    elif blink or face == "sleepy":
        closed_eyes()
    elif face in ("shocked", "scared"):
        for side in (-1, 1):
            pen.circle(cx + side * ex, cy + ey, .17 * r, fill=WHITE, w=W * .8)
            pen.dot(cx + side * ex, cy + ey, er * .9)
    elif face in ("smug", "unimpressed"):
        for side in (-1, 1):
            pen.dot(cx + side * ex, cy + ey + .03 * r, er)
        lids()
    elif face == "disgusted":
        for side in (-1, 1):
            x = cx + side * ex
            pen.line([(x - .11 * r, cy + ey - .05 * r), (x + .11 * r * side * side, cy + ey + .02 * r)], W, wob=.2)
    else:
        eyes(dx=look[0], dy=look[1])

    if face == "smug":
        brow(s, .22, .38)
        brow(-s, .2, .2)
    elif face == "thinking":
        brow(s, .2, .36)
        brow(-s, .2, .2)
    elif face == "confused":
        brow(s, .22, .38)
        brow(-s, .3, .18)
    elif face in ("shocked",):
        brow(1, .38, .42)
        brow(-1, .38, .42)
    elif face in ("sad", "worried", "scared", "sweating"):
        brow(1, .32, .2)
        brow(-1, .32, .2)
    elif face == "angry":
        brow(1, .14, .3)
        brow(-1, .14, .3)
    elif face == "unimpressed":
        brow(1, .2, .2)
        brow(-1, .2, .2)
    elif face in ("happy", "excited", "laugh"):
        brow(1, .3, .26)
        brow(-1, .3, .26)

    # ---- mouth
    mw = .26 * r
    if face in ("shocked", "scared"):
        h = .16 * r if face == "shocked" else .1 * r
        pen.ellipse(cx, my + .02 * r, .11 * r if face == "shocked" else .18 * r, h + mouth * .03 * r, fill=INK, w=W * .5)
    elif face in ("laugh", "excited"):
        pts = pen.ell_pts(cx, my - .06 * r, mw * 1.05, .26 * r, n=16, a0=0, a1=180, wob=False)
        pen.poly(pts, fill=INK, w=W * .6)
        pen.ellipse(cx, my + .1 * r, .1 * r, .05 * r, fill=C["pink"], w=0)
    elif face == "happy":
        if talk:
            pts = pen.ell_pts(cx, my - .04 * r, mw * .85, .17 * r, n=14, a0=0, a1=180, wob=False)
            pen.poly(pts, fill=INK, w=W * .6)
        else:
            pen.arc(cx, my - .1 * r, mw, .16 * r, 20, 160, W)
    elif face == "smug":
        pen.line(pen.bez((cx - s * mw * .9, my + .04 * r), (cx, my + .08 * r), (cx + s * mw, my - .1 * r)), W, wob=.2)
    elif face in ("sad",):
        pen.arc(cx, my + .12 * r, mw * .8, .13 * r, 205, 335, W)
    elif face == "angry":
        pen.arc(cx, my + .12 * r, mw * .8, .1 * r, 210, 330, W)
    elif face in ("confused", "disgusted", "worried", "sweating"):
        pts = [(cx - mw * .8 + i * mw * 1.6 / 8, my + (.035 * r if i % 2 else -.03 * r)) for i in range(9)]
        pen.line(pts, W, wob=.2)
    elif face == "thinking":
        pen.line([(cx - s * .02 * r, my + .02 * r), (cx + s * mw * .7, my - .03 * r)], W, wob=.2)
    elif face == "sleepy":
        pen.ellipse(cx, my + .02 * r, .08 * r, .06 * r, fill=INK, w=0)
    else:  # neutral / unimpressed
        if talk:
            pen.ellipse(cx, my + .01 * r, mw * .55, .07 * r + mouth * .05 * r, fill=INK, w=0)
        else:
            pen.line([(cx - mw * .7, my), (cx + mw * .7, my)], W, wob=.2)
    if talk and face not in ("neutral", "unimpressed", "happy", "shocked", "scared", "laugh", "excited"):
        pen.ellipse(cx, my + .1 * r, .07 * r, .04 * r + mouth * .03 * r, fill=INK, w=0)

    # ---- extras
    if face in ("sweating", "scared", "worried"):
        sx, sy = cx + s * .95 * r, cy - .35 * r
        pts = [(sx, sy - .22 * r)] + pen.ell_pts(sx, sy, .09 * r, .1 * r, n=10, a0=-30, a1=210, wob=False)
        pen.poly(pts, fill=C["sky2"], w=W * .7)
    if face in ("happy", "laugh", "excited"):
        for side in (-1, 1):
            pen.ellipse(cx + side * .6 * r, cy + .25 * r, .1 * r, .055 * r, fill=(240, 180, 160), w=0)
    if face == "sleepy":
        pen.text(cx + s * 1.2 * r, cy - 1.0 * r, "z", int(.5 * r), "hand")
        pen.text(cx + s * 1.5 * r, cy - 1.35 * r, "Z", int(.6 * r), "hand")


def draw_person(pen, x, feet_y, H, pose="stand", face="neutral", blink=False, mouth=0.0,
                flip=False, lw=None, holding=None, bob=0.0, skin=CREAM, outfit=None, shadow=False):
    """Draw one stick person. x = centre, feet_y = ground line, H = total height."""
    pose_n = norm_pose(pose)
    face = norm_face(face)
    P = POSES[pose_n]
    r = H * 0.25
    lw = lw or max(2.4, H * 0.013)
    s = -1 if flip else 1
    lean = P.get("lean", 0) * s

    if P.get("lie"):
        # lying on the ground, head on the left
        cy = feet_y - r * .9
        hx = x - H * .35
        pen.line([(hx + r, cy + r * .2), (x + H * .25, cy + r * .2)], lw)
        pen.line([(x + H * .25, cy + r * .2), (x + H * .55, cy + r * .1)], lw)
        pen.line([(x + H * .25, cy + r * .2), (x + H * .55, cy + r * .4)], lw)
        pen.circle(hx, cy, r, fill=skin, w=lw)
        draw_face(pen, hx, cy, r, face, blink=True if face == "sleepy" else blink, mouth=mouth, lw=lw)
        return dict(head=(hx, cy, r))

    if shadow:
        pen.ellipse(x, feet_y + H * .012, H * .17, H * .022, fill=(232, 230, 224) if shadow is True else shadow, w=0)
    sit = P.get("sit")
    leg_len = 1.3 * r
    hip_y = feet_y - (leg_len * .55 if sit else leg_len) - bob * .2
    body_len = 1.15 * r
    sh_y = hip_y - body_len
    hip_x = x
    sh_x = x + lean * r * 1.2
    head_cx = sh_x + lean * r * .5
    head_cy = sh_y - r * 1.12 - bob

    def pt(base, rel):
        return (base[0] + rel[0] * r * s, base[1] + rel[1] * r)

    hip = (hip_x, hip_y)
    sho = (sh_x, sh_y + r * .12)
    # legs
    for key in ("LL", "RL"):
        e, f = P[key]
        pts = [hip, pt(hip, e), pt(hip, f)]
        pen.line(pts, lw)
        fx, fy = pts[-1]
        pen.line([(fx, fy), (fx + (.18 * r if (f[0] * s) >= 0 else -.18 * r), fy)], lw * .95, wob=.2)
    if sit:
        pen.rrect(x - r * .9, hip_y + r * .05, x + r * 1.0, feet_y, 6, fill=C["stone"], w=lw * .8)
    # body
    if outfit:
        pts = [(sh_x - r * .38, sh_y + r * .15), (sh_x + r * .38, sh_y + r * .15), (hip_x + r * .5, hip_y + r * .25), (hip_x - r * .5, hip_y + r * .25)]
        pen.poly(pts, fill=outfit, w=lw * .9)
    pen.line([(head_cx, head_cy + r * .95), (sh_x, sh_y), hip], lw)

    def arm(key, front=False):
        e, f = P[key]
        pts = [sho, pt(sho, e), pt(sho, f)]
        pen.line(pts, lw)
        hx, hy = pts[-1]
        fing = P.get("finger", "")
        side = key
        if fing.startswith(side + "_"):
            pen.dot(hx, hy, r * .13)
            if fing.endswith("up"):
                pen.line([(hx, hy), (hx + s * r * .05, hy - r * .32)], lw * .9, wob=.1)
            else:
                d = 1 if side == "R" else -1
                pen.line([(hx, hy), (hx + s * d * r * .32, hy - r * .02)], lw * .9, wob=.1)
        else:
            pen.circle(hx, hy, r * .13, fill=skin, w=lw * .8)
        return (hx, hy)

    hands = {}
    if not P.get("front"):
        hands["L"] = arm("L")
        hands["R"] = arm("R")
    pen.circle(head_cx, head_cy, r, fill=skin, w=lw)
    draw_face(pen, head_cx, head_cy, r, face, blink, mouth, flip, lw)
    if P.get("front"):
        hands["L"] = arm("L")
        hands["R"] = arm("R")
    if holding:
        hk = P.get("holds", "R")
        if hk == "top":
            hx = (hands["L"][0] + hands["R"][0]) / 2
            hy = min(hands["L"][1], hands["R"][1]) - r * .45
        else:
            hx, hy = hands.get(hk, hands["R"])
        draw_prop(pen, holding, hx, hy - r * .1, r * 1.0)
    return dict(head=(head_cx, head_cy, r), hands=hands)


# =====================================================================
#  PROPS  (centre x,y ; s = rough size/height)
# =====================================================================
def _fire(p, x, y, s, lw):
    for i, dx in enumerate((-.32, .3)):
        p.line([(x + dx * s - .18 * s, y + .42 * s), (x - dx * s * .5, y + .3 * s)], lw * 1.6, C["bark"], wob=.3)
        p.line([(x + dx * s - .18 * s, y + .42 * s), (x - dx * s * .5, y + .3 * s)], lw * .5, INK, wob=.3)
    outer = [(x - .32 * s, y + .3 * s), (x - .38 * s, y), (x - .18 * s, y - .12 * s), (x - .12 * s, y - .45 * s),
             (x + .05 * s, y - .2 * s), (x + .18 * s, y - .5 * s), (x + .36 * s, y - .05 * s), (x + .3 * s, y + .3 * s)]
    p.poly(outer, fill=C["fire"], w=lw)
    inner = [(x - .16 * s, y + .3 * s), (x - .18 * s, y + .08 * s), (x - .05 * s, y - .1 * s), (x + .05 * s, y + .02 * s),
             (x + .14 * s, y - .12 * s), (x + .18 * s, y + .3 * s)]
    p.poly(inner, fill=C["fire2"], w=0)


def _spear(p, x, y, s, lw):
    p.line([(x - .1 * s, y + .5 * s), (x + .08 * s, y - .35 * s)], lw * 1.2, C["bark"], wob=.3)
    p.line([(x - .1 * s, y + .5 * s), (x + .08 * s, y - .35 * s)], lw * .4, INK, wob=.2)
    p.poly([(x + .03 * s, y - .33 * s), (x + .13 * s, y - .58 * s), (x + .15 * s, y - .32 * s)], fill=C["stone"], w=lw)


def _rock(p, x, y, s, lw):
    p.poly([(x - .45 * s, y + .3 * s), (x - .38 * s, y - .05 * s), (x - .12 * s, y - .25 * s), (x + .2 * s, y - .22 * s),
            (x + .44 * s, y + .02 * s), (x + .46 * s, y + .3 * s)], fill=C["stone"], w=lw)
    p.line([(x - .1 * s, y - .05 * s), (x + .05 * s, y + .1 * s)], lw * .6, wob=.2)


def _cave(p, x, y, s, lw):
    p.poly([(x - .6 * s, y + .4 * s), (x - .5 * s, y - .1 * s), (x - .2 * s, y - .42 * s), (x + .25 * s, y - .44 * s),
            (x + .55 * s, y - .1 * s), (x + .62 * s, y + .4 * s)], fill=C["stone2"], w=lw)
    pts = p.ell_pts(x, y + .4 * s, .28 * s, .48 * s, n=20, a0=180, a1=360, wob=False)
    p.poly(pts, fill=C["cave2"], w=lw)


def _hut(p, x, y, s, lw):
    p.rect(x - .38 * s, y - .05 * s, x + .38 * s, y + .45 * s, fill=C["wall"], w=lw)
    p.poly([(x - .52 * s, y), (x, y - .5 * s), (x + .52 * s, y)], fill=C["sand2"], w=lw)
    for i in range(4):
        xx = x - .3 * s + i * .2 * s
        p.line([(xx, y - .02 * s), (xx + .12 * s, y - .28 * s + abs(i - 1.5) * .05 * s)], lw * .5, wob=.2)
    p.poly([(x - .1 * s, y + .45 * s), (x - .1 * s, y + .15 * s), (x + .1 * s, y + .15 * s), (x + .1 * s, y + .45 * s)], fill=C["bark"], w=lw)


def _house(p, x, y, s, lw):
    p.rect(x - .4 * s, y - .05 * s, x + .4 * s, y + .45 * s, fill=C["wall"], w=lw)
    p.poly([(x - .5 * s, y), (x, y - .45 * s), (x + .5 * s, y)], fill=C["roof"], w=lw)
    p.rect(x - .08 * s, y + .2 * s, x + .08 * s, y + .45 * s, fill=C["bark"], w=lw)
    p.rect(x + .17 * s, y + .08 * s, x + .32 * s, y + .22 * s, fill=C["sky"], w=lw * .8)


def _pot(p, x, y, s, lw):
    pts = [(x - .12 * s, y - .4 * s), (x - .14 * s, y - .3 * s), (x - .35 * s, y - .05 * s), (x - .32 * s, y + .3 * s),
           (x - .18 * s, y + .42 * s), (x + .18 * s, y + .42 * s), (x + .32 * s, y + .3 * s), (x + .35 * s, y - .05 * s),
           (x + .14 * s, y - .3 * s), (x + .12 * s, y - .4 * s)]
    p.poly(pts, fill=C["clay"], w=lw)
    p.line([(x - .3 * s, y + .05 * s), (x + .3 * s, y + .05 * s)], lw * .6, wob=.3)
    p.line([(x - .28 * s, y + .16 * s), (x + .28 * s, y + .16 * s)], lw * .6, wob=.3)


def _beer(p, x, y, s, lw):
    p.rect(x - .25 * s, y - .25 * s, x + .2 * s, y + .45 * s, fill=C["beer"], w=lw)
    p.arc(x + .22 * s, y + .1 * s, .14 * s, .15 * s, -90, 90, lw)
    for cx, cy, rr in ((-.18, -.27, .1), (-.03, -.32, .12), (.13, -.27, .1)):
        p.circle(x + cx * s, y + cy * s, rr * s, fill=WHITE, w=lw * .8)
    p.rect(x - .25 * s, y - .25 * s, x + .2 * s, y - .2 * s, fill=WHITE, w=0)


def _coin(p, x, y, s, lw):
    p.circle(x, y, .32 * s, fill=C["gold"], w=lw)
    p.circle(x, y, .22 * s, fill=None, w=lw * .5)
    p.text(x, y + .02 * s, "$", int(.32 * s), "oswald", INK)


def _goldbar(p, x, y, s, lw):
    p.poly([(x - .45 * s, y + .2 * s), (x - .3 * s, y - .15 * s), (x + .3 * s, y - .15 * s), (x + .45 * s, y + .2 * s)], fill=C["gold"], w=lw)
    p.line([(x - .1 * s, y - .05 * s), (x + .15 * s, y - .05 * s)], lw * .5, (255, 240, 180))


def _tree(p, x, y, s, lw):
    p.poly([(x - .07 * s, y + .5 * s), (x - .05 * s, y), (x + .05 * s, y), (x + .07 * s, y + .5 * s)], fill=C["bark"], w=lw)
    for cx, cy, rr in ((-.18, -.05, .2), (.18, -.05, .2), (0, -.22, .25), (0, -.02, .2)):
        p.circle(x + cx * s, y + cy * s, rr * s, fill=C["leaf"], w=lw)
    p.circle(x - .05 * s, y - .1 * s, .14 * s, fill=C["leaf"], w=0)


def _palm(p, x, y, s, lw):
    p.line(p.bez((x, y + .5 * s), (x - .05 * s, y), (x + .08 * s, y - .32 * s)), lw * 3.2, C["bark"])
    p.line(p.bez((x, y + .5 * s), (x - .05 * s, y), (x + .08 * s, y - .32 * s)), lw * .5, INK)
    top = (x + .08 * s, y - .32 * s)
    for ang in (-160, -120, -60, -20, 200):
        a = math.radians(ang)
        tip = (top[0] + .42 * s * math.cos(a), top[1] + .3 * s * math.sin(a) + .12 * s)
        mid = (top[0] + .25 * s * math.cos(a), top[1] - .12 * s)
        pts = p.bez(top, mid, tip, 8)
        back = [(px, py + .06 * s * math.sin(math.pi * i / 8)) for i, (px, py) in enumerate(pts)]
        p.poly(pts + back[::-1], fill=C["leaf2"], w=lw * .8)


def _sun(p, x, y, s, lw):
    for i in range(10):
        a = math.radians(i * 36)
        p.line([(x + .32 * s * math.cos(a), y + .32 * s * math.sin(a)), (x + .46 * s * math.cos(a), y + .46 * s * math.sin(a))], lw, wob=.1)
    p.circle(x, y, .25 * s, fill=C["fire2"], w=lw)


def _moon(p, x, y, s, lw):
    outer = p.ell_pts(x, y, .35 * s, .35 * s, n=24, a0=60, a1=300, wob=False)
    inner = p.ell_pts(x + .15 * s, y, .27 * s, .3 * s, n=24, a0=300, a1=60, wob=False)
    p.poly(outer + inner[::-1][::-1], fill=(246, 232, 170), w=lw)


def _mountain(p, x, y, s, lw):
    p.poly([(x - .6 * s, y + .4 * s), (x - .05 * s, y - .45 * s), (x + .6 * s, y + .4 * s)], fill=C["stone2"], w=lw)
    p.poly([(x - .2 * s, y - .22 * s), (x - .05 * s, y - .45 * s), (x + .13 * s, y - .17 * s), (x + .03 * s, y - .1 * s), (x - .07 * s, y - .18 * s)], fill=WHITE, w=lw * .7)


def _river(p, x, y, s, lw):
    left = p.bez((x - .2 * s, y - .5 * s), (x - .45 * s, y), (x - .1 * s, y + .5 * s))
    right = p.bez((x + .2 * s, y + .5 * s), (x - .05 * s, y), (x + .1 * s, y - .5 * s))
    p.poly(left + right, fill=C["sea"], w=lw)


def _boat(p, x, y, s, lw):
    p.poly([(x - .5 * s, y + .05 * s), (x + .5 * s, y + .05 * s), (x + .32 * s, y + .3 * s), (x - .32 * s, y + .3 * s)], fill=C["bark"], w=lw)
    p.line([(x, y + .05 * s), (x, y - .55 * s)], lw)
    p.poly([(x + .03 * s, y - .5 * s), (x + .38 * s, y - .02 * s), (x + .03 * s, y - .02 * s)], fill=C["paper"], w=lw)


def _quad(p, x, y, s, lw, body, head_dx, color, neck=.0, legs=.3, tail=True):
    """generic 4-legged animal (facing right)."""
    bx, by, rx, ry = x, y, .38 * s * body, .2 * s
    for dx in (-.25, -.12, .12, .25):
        p.line([(bx + dx * s * body, by + .1 * s), (bx + dx * s * body, by + (.15 + legs) * s)], lw * 1.1)
    p.ellipse(bx, by, rx, ry, fill=color, w=lw)
    hx, hy = bx + rx + head_dx * s, by - .2 * s - neck * s
    p.line([(bx + rx * .7, by - .05 * s), (hx, hy)], lw * 2.5, color)
    p.line([(bx + rx * .7, by - .05 * s), (hx, hy)], lw * .4)
    p.ellipse(hx, hy, .13 * s, .1 * s, fill=color, w=lw)
    p.dot(hx + .04 * s, hy - .02 * s, .02 * s)
    if tail:
        p.line([(bx - rx, by - .05 * s), (bx - rx - .1 * s, by + .08 * s)], lw)
    return hx, hy


def _deer(p, x, y, s, lw):
    hx, hy = _quad(p, x, y, s, lw, .9, .05, C["fur"], neck=.12)
    for d in (-1, 1):
        p.line([(hx - .02 * s, hy - .08 * s), (hx + d * .08 * s - .05 * s, hy - .3 * s), (hx + d * .15 * s, hy - .38 * s)], lw * .8)


def _goat(p, x, y, s, lw):
    hx, hy = _quad(p, x, y, s, lw, .8, .02, C["grey"], neck=.05, legs=.25)
    p.arc(hx - .08 * s, hy - .1 * s, .1 * s, .1 * s, 180, 330, lw)
    p.line([(hx + .05 * s, hy + .08 * s), (hx + .04 * s, hy + .18 * s)], lw * .8)


def _cow(p, x, y, s, lw):
    hx, hy = _quad(p, x, y, s, lw, 1.0, .02, WHITE, neck=-.05, legs=.25)
    p.ellipse(x - .1 * s, y - .03 * s, .1 * s, .07 * s, fill=INK, w=0)
    p.line([(hx - .08 * s, hy - .08 * s), (hx - .14 * s, hy - .18 * s)], lw)


def _wolf(p, x, y, s, lw):
    hx, hy = _quad(p, x, y, s, lw, .85, .05, C["stone2"], neck=.0, legs=.27)
    p.poly([(hx - .07 * s, hy - .06 * s), (hx - .04 * s, hy - .2 * s), (hx + .02 * s, hy - .07 * s)], fill=C["stone2"], w=lw * .8)
    p.poly([(hx + .08 * s, hy - .04 * s), (hx + .22 * s, hy + .02 * s), (hx + .08 * s, hy + .07 * s)], fill=C["stone2"], w=lw * .8)


def _camel(p, x, y, s, lw):
    hx, hy = _quad(p, x, y, s, lw, .95, .12, C["sand2"], neck=.18, legs=.38)
    p.ellipse(x - .05 * s, y - .22 * s, .14 * s, .14 * s, fill=C["sand2"], w=lw)
    p.ellipse(x - .05 * s, y - .1 * s, .14 * s, .06 * s, fill=C["sand2"], w=0)


def _mammoth(p, x, y, s, lw):
    for dx in (-.24, -.1, .12, .26):
        p.rect(x + dx * s - .05 * s, y + .05 * s, x + dx * s + .05 * s, y + .42 * s, fill=C["mammoth"], w=lw)
    p.ellipse(x, y - .05 * s, .42 * s, .3 * s, fill=C["mammoth"], w=lw)
    p.circle(x + .38 * s, y - .12 * s, .2 * s, fill=C["mammoth"], w=lw)
    p.line(p.bez((x + .52 * s, y - .05 * s), (x + .62 * s, y + .2 * s), (x + .5 * s, y + .35 * s)), lw * 3, C["mammoth"])
    p.line(p.bez((x + .52 * s, y - .05 * s), (x + .62 * s, y + .2 * s), (x + .5 * s, y + .35 * s)), lw * .5)
    p.line(p.bez((x + .42 * s, y + .02 * s), (x + .62 * s, y + .12 * s), (x + .7 * s, y - .08 * s)), lw * 1.8, WHITE)
    p.dot(x + .42 * s, y - .18 * s, .025 * s)
    p.arc(x + .3 * s, y - .1 * s, .08 * s, .1 * s, 90, 270, lw * .7)


def _monkey(p, x, y, s, lw):
    p.line(p.bez((x - .15 * s, y + .25 * s), (x - .45 * s, y + .2 * s), (x - .4 * s, y - .1 * s)), lw)
    p.ellipse(x, y + .15 * s, .2 * s, .25 * s, fill=C["fur"], w=lw)
    for d in (-1, 1):
        p.circle(x + d * .22 * s, y - .25 * s, .07 * s, fill=C["fur"], w=lw)
    p.circle(x, y - .22 * s, .2 * s, fill=C["fur"], w=lw)
    p.ellipse(x, y - .17 * s, .14 * s, .12 * s, fill=CREAM, w=lw * .6)
    for d in (-1, 1):
        p.dot(x + d * .06 * s, y - .25 * s, .022 * s)
    p.arc(x, y - .15 * s, .05 * s, .03 * s, 20, 160, lw * .6)


def _fish(p, x, y, s, lw):
    p.poly([(x + .28 * s, y), (x + .48 * s, y - .15 * s), (x + .48 * s, y + .15 * s)], fill=C["sea"], w=lw)
    p.ellipse(x, y, .32 * s, .16 * s, fill=C["sea"], w=lw)
    p.dot(x - .18 * s, y - .03 * s, .03 * s)


def _bone(p, x, y, s, lw):
    p.line([(x - .3 * s, y + .12 * s), (x + .3 * s, y - .12 * s)], lw * 4, INK, wob=0)
    for (cx, cy) in ((-.32, .12), (.32, -.12)):
        for d in (-1, 1):
            p.circle(x + cx * s + d * .06 * s, y + cy * s + d * .06 * s, .08 * s, fill=WHITE, w=lw)
    p.line([(x - .3 * s, y + .12 * s), (x + .3 * s, y - .12 * s)], lw * 2.2, WHITE, wob=0)


def _skull(p, x, y, s, lw):
    p.circle(x, y - .05 * s, .3 * s, fill=WHITE, w=lw)
    p.rect(x - .15 * s, y + .15 * s, x + .15 * s, y + .35 * s, fill=WHITE, w=lw)
    p.circle(x, y - .05 * s, .28 * s, fill=WHITE, w=0)
    for d in (-1, 1):
        p.ellipse(x + d * .11 * s, y - .02 * s, .07 * s, .08 * s, fill=INK, w=0)
    for i in range(3):
        p.line([(x - .07 * s + i * .07 * s, y + .22 * s), (x - .07 * s + i * .07 * s, y + .34 * s)], lw * .6, wob=0)


def _apple(p, x, y, s, lw):
    p.circle(x, y + .05 * s, .3 * s, fill=RED, w=lw)
    p.line([(x, y - .22 * s), (x + .03 * s, y - .38 * s)], lw)
    p.poly([(x + .03 * s, y - .3 * s), (x + .2 * s, y - .38 * s), (x + .12 * s, y - .25 * s)], fill=C["leaf"], w=lw * .7)


def _wheat(p, x, y, s, lw):
    for dx, lean in ((-.12, -.1), (0, 0), (.12, .1)):
        bx, by = x + dx * s, y + .5 * s
        tx, ty = x + dx * s + lean * s, y - .2 * s
        p.line([(bx, by), (tx, ty)], lw * .8, C["bark"])
        for j in range(4):
            yy = ty + j * .09 * s - .1 * s
            xx = tx - lean * j * .05 * s
            p.ellipse(xx - .04 * s, yy, .04 * s, .065 * s, fill=C["gold"], w=lw * .6)
            p.ellipse(xx + .04 * s, yy, .04 * s, .065 * s, fill=C["gold"], w=lw * .6)


def _bread(p, x, y, s, lw):
    pts = p.ell_pts(x, y + .1 * s, .42 * s, .32 * s, n=20, a0=180, a1=360, wob=False)
    p.poly(pts, fill=C["sand2"], w=lw)
    for i in range(3):
        xx = x - .18 * s + i * .18 * s
        p.line([(xx - .05 * s, y - .02 * s), (xx + .05 * s, y - .12 * s)], lw * .7)


def _pyramid(p, x, y, s, lw):
    p.poly([(x - .6 * s, y + .4 * s), (x, y - .45 * s), (x + .6 * s, y + .4 * s)], fill=C["sand"], w=lw)
    p.poly([(x, y - .45 * s), (x + .6 * s, y + .4 * s), (x + .15 * s, y + .4 * s)], fill=C["sand2"], w=lw)
    for i in range(1, 4):
        yy = y - .45 * s + i * .21 * s
        p.line([(x - .6 * s * i * .21 / .85 * 1.0, yy), (x + .15 * s * i / 4, yy)], lw * .5, wob=.3)


def _scroll(p, x, y, s, lw):
    p.rect(x - .32 * s, y - .3 * s, x + .32 * s, y + .3 * s, fill=C["paper"], w=lw)
    for yy in (-.3, .3):
        p.ellipse(x - .32 * s, y + yy * s, .07 * s, .07 * s, fill=C["paper"], w=lw)
        p.ellipse(x + .32 * s, y + yy * s, .07 * s, .07 * s, fill=C["paper"], w=lw)
        p.line([(x - .32 * s, y + yy * s - .07 * s), (x + .32 * s, y + yy * s - .07 * s)], lw)
    for i in range(4):
        p.line([(x - .2 * s, y - .15 * s + i * .1 * s), (x + (.2 - .08 * (i == 3)) * s, y - .15 * s + i * .1 * s)], lw * .5, wob=.5)


def _book(p, x, y, s, lw):
    p.poly([(x, y - .25 * s), (x - .42 * s, y - .32 * s), (x - .42 * s, y + .28 * s), (x, y + .35 * s)], fill=WHITE, w=lw)
    p.poly([(x, y - .25 * s), (x + .42 * s, y - .32 * s), (x + .42 * s, y + .28 * s), (x, y + .35 * s)], fill=WHITE, w=lw)
    for i in range(3):
        for d in (-1, 1):
            p.line([(x + d * .08 * s, y - .12 * s + i * .12 * s), (x + d * .32 * s, y - .16 * s + i * .12 * s)], lw * .45, wob=.3)


def _question(p, x, y, s, lw):
    p.text(x, y, "?", int(s * 1.0), "bangers", C["blue"], stroke=lw * .9)


def _exclaim(p, x, y, s, lw):
    p.text(x, y, "!", int(s * 1.0), "bangers", RED, stroke=lw * .9)


def _x(p, x, y, s, lw):
    for a, b in (((-.4, -.4), (.4, .4)), ((.4, -.4), (-.4, .4))):
        p.line([(x + a[0] * s, y + a[1] * s), (x + b[0] * s, y + b[1] * s)], max(lw * 3, s * .1), RED, wob=1.5)


def _tick(p, x, y, s, lw):
    p.line([(x - .38 * s, y), (x - .1 * s, y + .3 * s), (x + .42 * s, y - .38 * s)], max(lw * 3, s * .1), GREEN, wob=1.5)


def _arrow(p, x, y, s, lw):
    p.line([(x - .45 * s, y), (x + .38 * s, y)], lw * 1.3)
    p.line([(x + .18 * s, y - .18 * s), (x + .42 * s, y), (x + .18 * s, y + .18 * s)], lw * 1.3)


def _thought(p, x, y, s, lw):
    for cx, cy, rr in ((-.18, -.05, .22), (.15, -.1, .25), (0, -.25, .22), (.02, .08, .2)):
        p.circle(x + cx * s, y + cy * s, rr * s, fill=WHITE, w=lw)
    for cx, cy, rr in ((-.18, -.05, .2), (.15, -.1, .23), (0, -.25, .2), (.02, .08, .18)):
        p.circle(x + cx * s, y + cy * s, rr * s, fill=WHITE, w=0)
    p.circle(x - .3 * s, y + .3 * s, .06 * s, fill=WHITE, w=lw)
    p.circle(x - .4 * s, y + .42 * s, .035 * s, fill=WHITE, w=lw)


def _speech(p, x, y, s, lw):
    pts = p.ell_pts(x, y - .05 * s, .45 * s, .3 * s, n=30, a0=110, a1=470, wob=False)
    pts.insert(0, (x - .3 * s, y + .38 * s))
    p.poly(pts, fill=WHITE, w=lw)


def _heart(p, x, y, s, lw):
    pts = []
    for i in range(40):
        t = 2 * math.pi * i / 40
        hx = 16 * math.sin(t) ** 3
        hy = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x + hx * s / 36, y - hy * s / 36))
    p.poly(pts, fill=RED, w=lw)


def _lightning(p, x, y, s, lw):
    p.poly([(x + .05 * s, y - .5 * s), (x - .25 * s, y + .05 * s), (x - .02 * s, y + .05 * s), (x - .12 * s, y + .5 * s),
            (x + .25 * s, y - .1 * s), (x + .02 * s, y - .1 * s), (x + .15 * s, y - .5 * s)], fill=C["fire2"], w=lw)


def _cloud(p, x, y, s, lw):
    for cx, cy, rr in ((-.25, .05, .18), (0, -.08, .26), (.25, .05, .18)):
        p.circle(x + cx * s, y + cy * s, rr * s, fill=WHITE, w=lw)
    p.rect(x - .25 * s, y + .02 * s, x + .25 * s, y + .22 * s, fill=WHITE, w=0)
    p.line([(x - .26 * s, y + .23 * s), (x + .26 * s, y + .23 * s)], lw)
    for cx, cy, rr in ((-.25, .05, .16), (0, -.08, .24), (.25, .05, .16)):
        p.circle(x + cx * s, y + cy * s, rr * s, fill=WHITE, w=0)


def _star(p, x, y, s, lw):
    pts = []
    for i in range(10):
        a = math.radians(-90 + i * 36)
        rr = .42 * s if i % 2 == 0 else .18 * s
        pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
    p.poly(pts, fill=C["gold"], w=lw)


def _bag(p, x, y, s, lw):
    p.poly([(x - .12 * s, y - .25 * s), (x - .38 * s, y + .1 * s), (x - .3 * s, y + .4 * s), (x + .3 * s, y + .4 * s),
            (x + .38 * s, y + .1 * s), (x + .12 * s, y - .25 * s)], fill=C["sand2"], w=lw)
    p.poly([(x - .12 * s, y - .25 * s), (x - .2 * s, y - .38 * s), (x + .2 * s, y - .38 * s), (x + .12 * s, y - .25 * s)], fill=C["sand2"], w=lw)
    p.text(x, y + .1 * s, "$", int(.38 * s), "oswald", INK)


def _clock(p, x, y, s, lw):
    p.circle(x, y, .4 * s, fill=WHITE, w=lw * 1.2)
    p.line([(x, y), (x, y - .26 * s)], lw)
    p.line([(x, y), (x + .18 * s, y + .05 * s)], lw)
    for i in range(12):
        a = math.radians(i * 30)
        p.dot(x + .32 * s * math.cos(a), y + .32 * s * math.sin(a), .02 * s)


def _sundial(p, x, y, s, lw):
    p.ellipse(x, y + .2 * s, .45 * s, .15 * s, fill=C["stone"], w=lw)
    p.poly([(x - .05 * s, y + .2 * s), (x - .05 * s, y - .35 * s), (x + .25 * s, y + .2 * s)], fill=C["stone2"], w=lw)
    p.poly([(x + .25 * s, y + .2 * s), (x + .45 * s, y + .25 * s), (x + .3 * s, y + .28 * s)], fill=(90, 86, 80), w=0)


def _tooth(p, x, y, s, lw):
    p.poly([(x - .28 * s, y - .25 * s), (x - .1 * s, y - .35 * s), (x, y - .28 * s), (x + .1 * s, y - .35 * s), (x + .28 * s, y - .25 * s),
            (x + .25 * s, y + .05 * s), (x + .15 * s, y + .4 * s), (x + .05 * s, y + .1 * s), (x - .05 * s, y + .1 * s),
            (x - .15 * s, y + .4 * s), (x - .25 * s, y + .05 * s)], fill=WHITE, w=lw)


def _stick(p, x, y, s, lw):
    p.line([(x - .35 * s, y + .3 * s), (x + .3 * s, y - .3 * s)], lw * 1.8, C["bark"])
    p.line([(x - .35 * s, y + .3 * s), (x + .3 * s, y - .3 * s)], lw * .4, INK)
    for i in range(4):
        p.line([(x + .2 * s + i * .03 * s, y - .25 * s + i * .03 * s), (x + .3 * s + i * .03 * s, y - .35 * s + i * .03 * s)], lw * .5)


def _torch(p, x, y, s, lw):
    p.line([(x, y + .5 * s), (x, y - .05 * s)], lw * 2, C["bark"])
    p.line([(x, y + .5 * s), (x, y - .05 * s)], lw * .4)
    _fire(p, x, y - .25 * s, s * .5, lw)


def _axe(p, x, y, s, lw):
    p.line([(x - .1 * s, y + .5 * s), (x + .05 * s, y - .4 * s)], lw * 1.8, C["bark"])
    p.line([(x - .1 * s, y + .5 * s), (x + .05 * s, y - .4 * s)], lw * .4)
    p.poly([(x + .03 * s, y - .38 * s), (x + .3 * s, y - .45 * s), (x + .35 * s, y - .15 * s), (x + .01 * s, y - .22 * s)], fill=C["stone"], w=lw)


def _shell(p, x, y, s, lw):
    pts = p.ell_pts(x, y, .35 * s, .3 * s, n=20, a0=180, a1=360, wob=False) + [(x + .1 * s, y + .3 * s), (x - .1 * s, y + .3 * s)]
    p.poly(pts, fill=C["pink"], w=lw)
    for i in range(-2, 3):
        p.line([(x, y + .25 * s), (x + i * .14 * s, y - .25 * s + abs(i) * .06 * s)], lw * .5, wob=.2)


def _salt(p, x, y, s, lw):
    p.poly([(x - .4 * s, y + .35 * s), (x - .15 * s, y - .25 * s), (x + .15 * s, y - .25 * s), (x + .4 * s, y + .35 * s)], fill=WHITE, w=lw)
    for i in range(6):
        p.dot(x + (i % 3 - 1) * .12 * s, y + (i // 3) * .15 * s, .025 * s, C["stone2"])


def _meat(p, x, y, s, lw):
    p.line([(x + .1 * s, y), (x + .42 * s, y - .18 * s)], lw * 2.8, INK, wob=0)
    p.line([(x + .1 * s, y), (x + .42 * s, y - .18 * s)], lw * 1.4, WHITE, wob=0)
    p.circle(x + .45 * s, y - .22 * s, .06 * s, fill=WHITE, w=lw)
    p.circle(x + .4 * s, y - .25 * s, .05 * s, fill=WHITE, w=lw)
    p.ellipse(x - .1 * s, y + .08 * s, .3 * s, .22 * s, fill=C["clay2"], w=lw)


def _toilet(p, x, y, s, lw):
    p.rect(x - .15 * s, y - .45 * s, x + .25 * s, y - .05 * s, fill=WHITE, w=lw)
    p.ellipse(x, y, .4 * s, .1 * s, fill=WHITE, w=lw)
    p.poly([(x - .3 * s, y + .05 * s), (x - .15 * s, y + .45 * s), (x + .15 * s, y + .45 * s), (x + .3 * s, y + .05 * s)], fill=WHITE, w=lw)


def _brush(p, x, y, s, lw):
    p.rrect(x - .45 * s, y - .04 * s, x + .3 * s, y + .06 * s, 4, fill=C["blue"], w=lw)
    p.rect(x + .1 * s, y - .16 * s, x + .3 * s, y - .04 * s, fill=WHITE, w=lw * .8)


def _leaf(p, x, y, s, lw):
    pts = p.bez((x - .4 * s, y + .3 * s), (x - .3 * s, y - .4 * s), (x + .4 * s, y - .3 * s), 10)
    pts2 = p.bez((x + .4 * s, y - .3 * s), (x + .3 * s, y + .35 * s), (x - .4 * s, y + .3 * s), 10)
    p.poly(pts + pts2, fill=C["leaf"], w=lw)
    p.line([(x - .4 * s, y + .3 * s), (x + .25 * s, y - .2 * s)], lw * .6)


def _mushroom(p, x, y, s, lw):
    p.rect(x - .1 * s, y - .05 * s, x + .1 * s, y + .4 * s, fill=CREAM, w=lw)
    pts = p.ell_pts(x, y, .38 * s, .35 * s, n=20, a0=180, a1=360, wob=False)
    p.poly(pts, fill=RED, w=lw)
    for cx, cy in ((-.15, -.12), (.12, -.2), (.2, -.06)):
        p.circle(x + cx * s, y + cy * s, .05 * s, fill=WHITE, w=0)


def _berries(p, x, y, s, lw):
    p.line([(x, y - .4 * s), (x, y - .1 * s)], lw)
    for cx, cy in ((-.15, 0), (.15, 0), (0, -.1), (-.08, .18), (.1, .17)):
        p.circle(x + cx * s, y + cy * s, .12 * s, fill=C["purple"], w=lw * .8)


def _bed(p, x, y, s, lw):
    p.rect(x - .5 * s, y, x + .5 * s, y + .2 * s, fill=C["bark"], w=lw)
    p.rect(x - .48 * s, y - .12 * s, x + .48 * s, y, fill=C["sand"], w=lw)
    p.ellipse(x - .35 * s, y - .15 * s, .12 * s, .07 * s, fill=WHITE, w=lw)


def _jar(p, x, y, s, lw):
    p.rrect(x - .28 * s, y - .25 * s, x + .28 * s, y + .4 * s, 10, fill=C["sky"], w=lw)
    p.rect(x - .22 * s, y - .38 * s, x + .22 * s, y - .25 * s, fill=C["bark"], w=lw)
    p.rect(x - .2 * s, y + .05 * s, x + .2 * s, y + .35 * s, fill=C["fire"], w=0)


def _phone(p, x, y, s, lw):
    p.rrect(x - .22 * s, y - .42 * s, x + .22 * s, y + .42 * s, 8, fill=INK, w=lw)
    p.rect(x - .17 * s, y - .34 * s, x + .17 * s, y + .3 * s, fill=C["sky"], w=0)


def _chart_up(p, x, y, s, lw):
    p.line([(x - .4 * s, y - .4 * s), (x - .4 * s, y + .4 * s), (x + .45 * s, y + .4 * s)], lw)
    p.line([(x - .35 * s, y + .25 * s), (x - .1 * s, y + .05 * s), (x + .1 * s, y + .15 * s), (x + .4 * s, y - .3 * s)], lw * 1.5, GREEN)


def _chart_down(p, x, y, s, lw):
    p.line([(x - .4 * s, y - .4 * s), (x - .4 * s, y + .4 * s), (x + .45 * s, y + .4 * s)], lw)
    p.line([(x - .35 * s, y - .3 * s), (x - .1 * s, y - .05 * s), (x + .1 * s, y - .15 * s), (x + .4 * s, y + .3 * s)], lw * 1.5, RED)


def _crown(p, x, y, s, lw):
    p.poly([(x - .4 * s, y + .25 * s), (x - .4 * s, y - .2 * s), (x - .2 * s, y + .02 * s), (x, y - .3 * s),
            (x + .2 * s, y + .02 * s), (x + .4 * s, y - .2 * s), (x + .4 * s, y + .25 * s)], fill=C["gold"], w=lw)


def _sword(p, x, y, s, lw):
    p.poly([(x - .04 * s, y + .2 * s), (x - .04 * s, y - .5 * s), (x, y - .58 * s), (x + .04 * s, y - .5 * s), (x + .04 * s, y + .2 * s)], fill=C["grey"], w=lw)
    p.line([(x - .18 * s, y + .2 * s), (x + .18 * s, y + .2 * s)], lw * 1.6)
    p.line([(x, y + .2 * s), (x, y + .45 * s)], lw * 1.8, C["bark"])


def _bottle(p, x, y, s, lw):
    p.poly([(x - .06 * s, y - .45 * s), (x - .06 * s, y - .2 * s), (x - .2 * s, y - .05 * s), (x - .2 * s, y + .45 * s),
            (x + .2 * s, y + .45 * s), (x + .2 * s, y - .05 * s), (x + .06 * s, y - .2 * s), (x + .06 * s, y - .45 * s)], fill=C["leaf2"], w=lw)
    p.rect(x - .2 * s, y + .05 * s, x + .2 * s, y + .25 * s, fill=C["paper"], w=lw * .7)


def _snake(p, x, y, s, lw):
    pts = [(x - .45 * s + i * .9 * s / 30, y + .1 * s * math.sin(i / 30 * 2 * math.pi * 1.5)) for i in range(31)]
    p.line(pts, lw * 4.5, C["leaf2"], wob=0)
    p.line(pts, lw * .5, INK, wob=0)
    p.ellipse(x + .47 * s, y + .05 * s, .09 * s, .07 * s, fill=C["leaf2"], w=lw)
    p.dot(x + .5 * s, y + .03 * s, .015 * s)


def _horse(p, x, y, s, lw):
    hx, hy = _quad(p, x, y, s, lw, 1.0, .1, C["bark"], neck=.12, legs=.38)
    p.line([(hx - .08 * s, hy - .05 * s), (x + .25 * s, y - .15 * s)], lw * 1.2, INK)


def _bird(p, x, y, s, lw):
    col = (110, 170, 220)
    p.poly([(x - .3 * s, y), (x - .5 * s, y - .12 * s), (x - .48 * s, y + .1 * s)], fill=col, w=lw)
    p.ellipse(x, y + .02 * s, .32 * s, .22 * s, fill=col, w=lw)
    p.ellipse(x + .02 * s, y + .1 * s, .18 * s, .1 * s, fill=(236, 240, 244), w=0)
    p.circle(x + .26 * s, y - .14 * s, .15 * s, fill=col, w=lw)
    p.poly([(x + .39 * s, y - .17 * s), (x + .52 * s, y - .12 * s), (x + .39 * s, y - .08 * s)], fill=C["gold"], w=lw * .7)
    _eye(p, x + .29 * s, y - .17 * s, .04 * s)
    p.poly([(x - .15 * s, y - .05 * s), (x + .05 * s, y - .32 * s), (x + .12 * s, y - .02 * s)], fill=(90, 150, 205), w=lw * .9)
    for dx in (-.03, .07):
        p.line([(x + dx * s, y + .22 * s), (x + dx * s, y + .32 * s)], lw * .9, C["gold2"], wob=0)


def _wheel(p, x, y, s, lw):
    p.circle(x, y, .4 * s, fill=C["bark"], w=lw)
    p.circle(x, y, .3 * s, fill=WHITE, w=lw)
    for i in range(4):
        a = math.radians(i * 45)
        p.line([(x - .3 * s * math.cos(a), y - .3 * s * math.sin(a)), (x + .3 * s * math.cos(a), y + .3 * s * math.sin(a))], lw * .8, wob=0)
    p.circle(x, y, .06 * s, fill=C["bark"], w=lw)


def _tent(p, x, y, s, lw):
    p.poly([(x - .55 * s, y + .4 * s), (x, y - .45 * s), (x + .55 * s, y + .4 * s)], fill=C["fur"], w=lw)
    p.poly([(x - .15 * s, y + .4 * s), (x, y - .05 * s), (x + .15 * s, y + .4 * s)], fill=C["cave2"], w=lw)
    for d in (-1, 1):
        p.line([(x, y - .45 * s), (x + d * .12 * s, y - .6 * s)], lw)


def _drum(p, x, y, s, lw):
    p.rect(x - .3 * s, y - .15 * s, x + .3 * s, y + .35 * s, fill=C["clay"], w=lw)
    p.ellipse(x, y - .15 * s, .3 * s, .1 * s, fill=CREAM, w=lw)
    for i in range(4):
        p.line([(x - .3 * s + i * .2 * s, y - .05 * s), (x - .2 * s + i * .2 * s, y + .3 * s)], lw * .5, wob=.2)


def _needle(p, x, y, s, lw):
    p.line([(x - .4 * s, y + .3 * s), (x + .4 * s, y - .3 * s)], lw * 1.5, C["grey"], wob=0)
    p.circle(x + .32 * s, y - .24 * s, .04 * s, fill=WHITE, w=lw * .6)
    p.line(p.bez((x + .32 * s, y - .24 * s), (x + .5 * s, y + .1 * s), (x + .1 * s, y + .3 * s)), lw * .7, RED)


def _ice(p, x, y, s, lw):
    p.poly([(x - .35 * s, y + .3 * s), (x - .3 * s, y - .25 * s), (x + .25 * s, y - .3 * s), (x + .35 * s, y + .25 * s)], fill=C["ice"], w=lw)
    p.line([(x - .15 * s, y - .15 * s), (x + .1 * s, y - .18 * s)], lw * .7, WHITE)


def _person_prop(p, x, y, s, lw):
    draw_person(p, x, y + .5 * s, s, "stand", "neutral")


PROPS = {
    "fire": _fire, "campfire": _fire, "spear": _spear, "rock": _rock, "stone": _rock, "cave": _cave, "hut": _hut,
    "house": _house, "pot": _pot, "clay_pot": _pot, "beer": _beer, "beer_mug": _beer, "mug": _beer, "coin": _coin,
    "coins": _coin, "money": _coin, "gold": _goldbar, "gold_bar": _goldbar, "goldbar": _goldbar, "tree": _tree,
    "palm": _palm, "sun": _sun, "moon": _moon, "mountain": _mountain, "river": _river, "boat": _boat, "camel": _camel,
    "mammoth": _mammoth, "deer": _deer, "wolf": _wolf, "dog": _wolf, "monkey": _monkey, "bone": _bone, "skull": _skull,
    "apple": _apple, "fruit": _apple, "wheat": _wheat, "grain": _wheat, "bread": _bread, "pyramid": _pyramid,
    "scroll": _scroll, "book": _book, "question": _question, "question_mark": _question, "x": _x, "red_x": _x,
    "cross": _x, "tick": _tick, "green_tick": _tick, "check": _tick, "arrow": _arrow, "thought": _thought,
    "thought_bubble": _thought, "speech": _speech, "speech_bubble": _speech, "heart": _heart, "lightning": _lightning,
    "cloud": _cloud, "star": _star, "bag": _bag, "money_bag": _bag, "clock": _clock, "sundial": _sundial,
    "tooth": _tooth, "teeth": _tooth, "stick": _stick, "chew_stick": _stick, "torch": _torch, "axe": _axe,
    "hand_axe": _axe, "tool": _axe, "shell": _shell, "salt": _salt, "meat": _meat, "toilet": _toilet,
    "toothbrush": _brush, "brush": _brush, "leaf": _leaf, "mushroom": _mushroom, "berries": _berries, "bed": _bed,
    "jar": _jar, "honey": _jar, "phone": _phone, "chart_up": _chart_up, "chart_down": _chart_down, "crown": _crown,
    "king": _crown, "sword": _sword, "bottle": _bottle, "wine": _bottle, "snake": _snake, "horse": _horse,
    "bird": _bird, "wheel": _wheel, "tent": _tent, "drum": _drum, "music": _drum, "needle": _needle,
    "goat": _goat, "sheep": _goat, "cow": _cow, "fish": _fish, "ice": _ice, "exclaim": _exclaim, "!": _exclaim,
    "?": _question, "person": _person_prop,
}


def _pig(p, x, y, s, lw):
    for dx in (-.22, -.1, .1, .22):
        p.line([(x + dx * s, y + .12 * s), (x + dx * s, y + .32 * s)], lw * 1.3)
    p.ellipse(x, y, .36 * s, .22 * s, fill=C["pink"], w=lw)
    p.circle(x + .34 * s, y - .06 * s, .15 * s, fill=C["pink"], w=lw)
    p.ellipse(x + .47 * s, y - .03 * s, .05 * s, .06 * s, fill=(220, 110, 120), w=lw * .7)
    p.dot(x + .36 * s, y - .12 * s, .022 * s)
    p.poly([(x + .26 * s, y - .17 * s), (x + .3 * s, y - .3 * s), (x + .36 * s, y - .19 * s)], fill=C["pink"], w=lw * .7)
    p.arc(x - .4 * s, y - .05 * s, .06 * s, .06 * s, 90, 400, lw * .8)


def _sponge(p, x, y, s, lw):
    p.line([(x - .35 * s, y + .4 * s), (x + .15 * s, y - .15 * s)], lw * 1.8, C["bark"])
    p.line([(x - .35 * s, y + .4 * s), (x + .15 * s, y - .15 * s)], lw * .4)
    p.ellipse(x + .22 * s, y - .25 * s, .17 * s, .13 * s, fill=C["gold"], w=lw)
    for cx, cy in ((.17, -.28), (.27, -.22), (.22, -.32)):
        p.dot(x + cx * s, y + cy * s, .02 * s, C["gold2"])


def _chamberpot(p, x, y, s, lw):
    p.poly([(x - .32 * s, y - .15 * s), (x - .26 * s, y + .3 * s), (x + .26 * s, y + .3 * s), (x + .32 * s, y - .15 * s)], fill=WHITE, w=lw)
    p.ellipse(x, y - .15 * s, .34 * s, .07 * s, fill=WHITE, w=lw)
    p.arc(x + .36 * s, y + .05 * s, .1 * s, .12 * s, -90, 90, lw)


def _drop(p, x, y, s, lw):
    pts = [(x, y - .4 * s)] + p.ell_pts(x, y + .1 * s, .25 * s, .27 * s, n=16, a0=-20, a1=200, wob=False)
    p.poly(pts, fill=C["sky2"], w=lw)


def _stink(p, x, y, s, lw):
    for dx in (-.2, 0, .2):
        pts = [(x + dx * s + .06 * s * math.sin(i / 3), y + .4 * s - i * .08 * s) for i in range(11)]
        p.line(pts, lw * 1.2, C["olive"], wob=0)


def _pipe(p, x, y, s, lw):
    p.rect(x - .45 * s, y - .08 * s, x + .2 * s, y + .08 * s, fill=C["clay"], w=lw)
    p.rect(x + .08 * s, y - .08 * s, x + .2 * s, y + .4 * s, fill=C["clay"], w=lw)
    p.rect(x - .5 * s, y - .12 * s, x - .4 * s, y + .12 * s, fill=C["clay2"], w=lw)


def _demon(p, x, y, s, lw):
    p.circle(x, y, .3 * s, fill=(140, 170, 110), w=lw)
    for d in (-1, 1):
        p.poly([(x + d * .15 * s, y - .24 * s), (x + d * .25 * s, y - .48 * s), (x + d * .26 * s, y - .18 * s)], fill=(140, 170, 110), w=lw)
        p.circle(x + d * .1 * s, y - .04 * s, .06 * s, fill=WHITE, w=lw * .6)
        p.dot(x + d * .1 * s, y - .03 * s, .025 * s)
    p.line([(x - .12 * s, y + .14 * s), (x - .04 * s, y + .1 * s), (x + .04 * s, y + .14 * s), (x + .12 * s, y + .1 * s)], lw)


def _poop(p, x, y, s, lw):
    col = (128, 88, 52)
    for cy, rx, ry in ((.25, .38, .14), (.08, .3, .13), (-.08, .2, .11)):
        p.ellipse(x, y + cy * s, rx * s, ry * s, fill=col, w=lw)
    p.poly([(x - .08 * s, y - .14 * s), (x + .02 * s, y - .32 * s), (x + .08 * s, y - .14 * s)], fill=col, w=lw)
    for d in (-1, 1):
        p.circle(x + d * .09 * s, y + .08 * s, .045 * s, fill=WHITE, w=lw * .5)
        p.dot(x + d * .09 * s, y + .09 * s, .02 * s)


PROPS.update({"poop": _poop, "coprolite": _poop, "pig": _pig, "sponge": _sponge, "sponge_stick": _sponge, "chamber_pot": _chamberpot,
              "chamberpot": _chamberpot, "drop": _drop, "water": _drop, "stink": _stink, "smell": _stink,
              "pipe": _pipe, "drain": _pipe, "demon": _demon, "monster": _demon})


# ---------------- more animals (all face right, x,y = centre, s = size) ----------------
def _eye(p, x, y, r):
    p.circle(x, y, r, fill=WHITE, w=max(1.5, r * .35))
    p.dot(x + r * .2, y, r * .55)


def _cat(p, x, y, s, lw):
    col = (232, 160, 80)
    p.line(p.bez((x - .3 * s, y + .2 * s), (x - .55 * s, y), (x - .45 * s, y - .3 * s)), lw * 3, col)
    p.line(p.bez((x - .3 * s, y + .2 * s), (x - .55 * s, y), (x - .45 * s, y - .3 * s)), lw * .5)
    p.ellipse(x - .05 * s, y + .18 * s, .3 * s, .24 * s, fill=col, w=lw)
    for dx in (-.2, .1):
        p.ellipse(x + dx * s, y + .4 * s, .07 * s, .05 * s, fill=col, w=lw * .8)
    hx, hy = x + .22 * s, y - .12 * s
    for d in (-1, 1):
        p.poly([(hx + d * .2 * s, hy - .05 * s), (hx + d * .2 * s, hy - .32 * s), (hx + d * .04 * s, hy - .16 * s)], fill=col, w=lw)
    p.circle(hx, hy, .22 * s, fill=col, w=lw)
    _eye(p, hx - .08 * s, hy - .03 * s, .05 * s)
    _eye(p, hx + .08 * s, hy - .03 * s, .05 * s)
    p.dot(hx, hy + .07 * s, .025 * s, C["pink"])
    for d in (-1, 1):
        p.line([(hx + d * .08 * s, hy + .1 * s), (hx + d * .3 * s, hy + .08 * s)], lw * .5, wob=0)


def _dog(p, x, y, s, lw):
    col = (196, 150, 100)
    for dx in (-.25, -.12, .12, .25):
        p.line([(x + dx * s, y + .1 * s), (x + dx * s, y + .38 * s)], lw * 1.6)
    p.line(p.bez((x - .32 * s, y - .02 * s), (x - .5 * s, y - .15 * s), (x - .45 * s, y - .3 * s)), lw * 1.6)
    p.ellipse(x, y, .36 * s, .18 * s, fill=col, w=lw)
    hx, hy = x + .36 * s, y - .2 * s
    p.circle(hx, hy, .17 * s, fill=col, w=lw)
    p.ellipse(hx + .16 * s, hy + .05 * s, .1 * s, .07 * s, fill=col, w=lw)
    p.dot(hx + .25 * s, hy + .03 * s, .03 * s)
    p.ellipse(hx - .1 * s, hy + .02 * s, .06 * s, .14 * s, fill=(120, 84, 54), w=lw * .8)
    _eye(p, hx + .04 * s, hy - .05 * s, .045 * s)
    p.line([(hx + .2 * s, hy + .12 * s), (hx + .2 * s, hy + .2 * s)], lw * 1.4, C["pink"], wob=0)


def _lion(p, x, y, s, lw):
    body = (226, 176, 92)
    mane = (176, 104, 48)
    for dx in (-.25, -.12, .12, .25):
        p.rect(x + dx * s - .04 * s, y + .05 * s, x + dx * s + .04 * s, y + .38 * s, fill=body, w=lw * .8)
    p.line(p.bez((x - .36 * s, y), (x - .55 * s, y - .1 * s), (x - .5 * s, y - .3 * s)), lw * 1.2)
    p.circle(x - .5 * s, y - .3 * s, .05 * s, fill=mane, w=lw * .6)
    p.ellipse(x, y, .38 * s, .2 * s, fill=body, w=lw)
    hx, hy = x + .32 * s, y - .2 * s
    pts = []
    for i in range(24):
        a = 2 * math.pi * i / 24
        r = .3 * s if i % 2 == 0 else .24 * s
        pts.append((hx + r * math.cos(a), hy + r * math.sin(a)))
    p.poly(pts, fill=mane, w=lw)
    p.circle(hx, hy, .17 * s, fill=body, w=lw)
    _eye(p, hx - .06 * s, hy - .04 * s, .04 * s)
    _eye(p, hx + .07 * s, hy - .04 * s, .04 * s)
    p.ellipse(hx + .01 * s, hy + .06 * s, .05 * s, .035 * s, fill=(120, 70, 50), w=0)


def _elephant(p, x, y, s, lw):
    col = (160, 164, 172)
    for dx in (-.22, -.08, .1, .24):
        p.rect(x + dx * s - .06 * s, y + .05 * s, x + dx * s + .06 * s, y + .42 * s, fill=col, w=lw)
    p.ellipse(x, y - .05 * s, .42 * s, .28 * s, fill=col, w=lw)
    hx, hy = x + .38 * s, y - .15 * s
    p.ellipse(hx - .1 * s, hy, .16 * s, .22 * s, fill=(176, 180, 188), w=lw)
    p.circle(hx, hy, .17 * s, fill=col, w=lw)
    p.line(p.bez((hx + .12 * s, hy + .05 * s), (hx + .25 * s, hy + .3 * s), (hx + .38 * s, hy + .28 * s)), lw * 3.2, col)
    p.line(p.bez((hx + .12 * s, hy + .05 * s), (hx + .25 * s, hy + .3 * s), (hx + .38 * s, hy + .28 * s)), lw * .5)
    _eye(p, hx + .05 * s, hy - .05 * s, .035 * s)
    p.line([(hx + .1 * s, hy + .08 * s), (hx + .2 * s, hy + .14 * s)], lw * 1.6, WHITE, wob=0)


def _owl(p, x, y, s, lw):
    col = (150, 110, 80)
    p.ellipse(x, y + .05 * s, .28 * s, .38 * s, fill=col, w=lw)
    p.ellipse(x, y + .15 * s, .18 * s, .22 * s, fill=(226, 200, 160), w=lw * .6)
    for d in (-1, 1):
        p.poly([(x + d * .2 * s, y - .25 * s), (x + d * .26 * s, y - .42 * s), (x + d * .08 * s, y - .3 * s)], fill=col, w=lw)
        p.circle(x + d * .11 * s, y - .14 * s, .1 * s, fill=WHITE, w=lw * .8)
        p.dot(x + d * .11 * s, y - .14 * s, .05 * s)
    p.poly([(x - .04 * s, y - .06 * s), (x + .04 * s, y - .06 * s), (x, y + .02 * s)], fill=C["gold"], w=lw * .6)
    for d in (-1, 1):
        p.line([(x + d * .08 * s, y + .42 * s), (x + d * .08 * s, y + .48 * s)], lw * 1.2, C["gold2"], wob=0)


def _chicken(p, x, y, s, lw):
    p.line([(x - .05 * s, y + .25 * s), (x - .05 * s, y + .45 * s)], lw * 1.2, C["gold2"])
    p.line([(x + .08 * s, y + .25 * s), (x + .08 * s, y + .45 * s)], lw * 1.2, C["gold2"])
    p.poly([(x - .32 * s, y - .05 * s), (x - .45 * s, y - .22 * s), (x - .4 * s, y + .05 * s)], fill=WHITE, w=lw)
    p.ellipse(x, y + .05 * s, .32 * s, .24 * s, fill=WHITE, w=lw)
    hx, hy = x + .25 * s, y - .2 * s
    p.circle(hx, hy, .13 * s, fill=WHITE, w=lw)
    for cx in (-.05, .02, .09):
        p.circle(hx + cx * s, hy - .14 * s, .045 * s, fill=RED, w=lw * .6)
    p.poly([(hx + .11 * s, hy - .02 * s), (hx + .22 * s, hy + .02 * s), (hx + .11 * s, hy + .05 * s)], fill=C["gold"], w=lw * .7)
    p.ellipse(hx + .08 * s, hy + .1 * s, .03 * s, .05 * s, fill=RED, w=0)
    _eye(p, hx + .03 * s, hy - .03 * s, .035 * s)


def _bear(p, x, y, s, lw):
    col = (120, 82, 56)
    for dx in (-.24, -.1, .1, .24):
        p.rect(x + dx * s - .07 * s, y + .05 * s, x + dx * s + .07 * s, y + .38 * s, fill=col, w=lw)
    p.ellipse(x, y - .02 * s, .42 * s, .26 * s, fill=col, w=lw)
    hx, hy = x + .38 * s, y - .18 * s
    for d in (-1, 1):
        p.circle(hx + d * .12 * s, hy - .14 * s, .06 * s, fill=col, w=lw)
    p.circle(hx, hy, .18 * s, fill=col, w=lw)
    p.ellipse(hx + .08 * s, hy + .06 * s, .09 * s, .07 * s, fill=(200, 160, 120), w=lw * .6)
    p.dot(hx + .13 * s, hy + .04 * s, .03 * s)
    _eye(p, hx + .02 * s, hy - .05 * s, .035 * s)


def _rabbit(p, x, y, s, lw):
    col = (236, 232, 226)
    p.circle(x - .28 * s, y + .08 * s, .07 * s, fill=WHITE, w=lw)
    p.ellipse(x - .05 * s, y + .12 * s, .26 * s, .2 * s, fill=col, w=lw)
    hx, hy = x + .18 * s, y - .08 * s
    for dx in (-.05, .05):
        p.ellipse(hx + dx * s, hy - .26 * s, .045 * s, .16 * s, fill=col, w=lw)
        p.ellipse(hx + dx * s, hy - .26 * s, .02 * s, .11 * s, fill=C["pink"], w=0)
    p.circle(hx, hy, .13 * s, fill=col, w=lw)
    _eye(p, hx + .04 * s, hy - .02 * s, .035 * s)
    p.dot(hx + .12 * s, hy + .04 * s, .022 * s, C["pink"])


def _frog(p, x, y, s, lw):
    col = (110, 180, 90)
    p.ellipse(x, y + .1 * s, .32 * s, .22 * s, fill=col, w=lw)
    for d in (-1, 1):
        p.circle(x + d * .14 * s, y - .12 * s, .1 * s, fill=col, w=lw)
        _eye(p, x + d * .14 * s, y - .13 * s, .055 * s)
    p.arc(x, y + .08 * s, .18 * s, .08 * s, 15, 165, lw)
    for d in (-1, 1):
        p.ellipse(x + d * .3 * s, y + .3 * s, .12 * s, .05 * s, fill=col, w=lw * .8)


def _crocodile(p, x, y, s, lw):
    col = (96, 140, 80)
    pts = [(x - .55 * s, y + .05 * s), (x - .2 * s, y - .1 * s), (x + .3 * s, y - .1 * s), (x + .55 * s, y - .02 * s),
           (x + .55 * s, y + .08 * s), (x + .25 * s, y + .12 * s), (x - .2 * s, y + .14 * s)]
    p.poly(pts, fill=col, w=lw)
    for i in range(5):
        xx = x - .25 * s + i * .1 * s
        p.poly([(xx, y - .1 * s), (xx + .04 * s, y - .17 * s), (xx + .08 * s, y - .1 * s)], fill=col, w=lw * .6)
    for i in range(4):
        xx = x + .3 * s + i * .06 * s
        p.poly([(xx, y + .04 * s), (xx + .02 * s, y + .0 * s), (xx + .04 * s, y + .04 * s)], fill=WHITE, w=0)
    _eye(p, x + .3 * s, y - .13 * s, .04 * s)
    for dx in (-.15, .15):
        p.line([(x + dx * s, y + .12 * s), (x + dx * s - .04 * s, y + .22 * s)], lw * 1.6, col)


def _ape(p, x, y, s, lw, face="happy"):
    """Big cartoon ape, head centre at upper part. s = overall height."""
    fur = (122, 84, 54)
    fc = (236, 214, 180)
    r = s * .22
    hx, hy = x, y - s * .2
    p.ellipse(x, y + s * .22, r * 1.1, r * 1.3, fill=fur, w=lw)
    p.ellipse(x, y + s * .25, r * .62, r * .82, fill=fc, w=lw * .7)
    for d in (-1, 1):
        p.circle(hx + d * r * 1.02, hy, r * .33, fill=fur, w=lw)
        p.circle(hx + d * r * 1.02, hy, r * .18, fill=fc, w=0)
    p.circle(hx, hy, r, fill=fur, w=lw)
    p.ellipse(hx - r * .28, hy - r * .12, r * .42, r * .38, fill=fc, w=0)
    p.ellipse(hx + r * .28, hy - r * .12, r * .42, r * .38, fill=fc, w=0)
    p.ellipse(hx, hy + r * .38, r * .62, r * .42, fill=fc, w=0)
    if face == "drunk":
        for d in (-1, 1):
            cx, cy = hx + d * r * .3, hy - r * .12
            pts = [(cx + r * .2 * t / 12 * math.cos(t * d), cy + r * .2 * t / 12 * math.sin(t * d)) for t in [i * .3 for i in range(42)]]
            p.line(pts, lw * .55, INK, wob=0)
        for d in (-1, 1):
            p.ellipse(hx + d * r * .58, hy + r * .2, r * .13, r * .07, fill=(225, 120, 120), w=0)
    else:
        for d in (-1, 1):
            _eye(p, hx + d * r * .3, hy - r * .12, r * .13)
    p.dot(hx - r * .08, hy + r * .22, r * .035)
    p.dot(hx + r * .08, hy + r * .22, r * .035)
    pts = p.ell_pts(hx, hy + r * .36, r * .42, r * .3, n=18, a0=0, a1=180, wob=False)
    p.poly(pts, fill=INK, w=lw * .6)
    p.ellipse(hx, hy + r * .55, r * .16, r * .07, fill=C["pink"], w=0)


def _ape_prop(p, x, y, s, lw):
    _ape(p, x, y, s, lw, "happy")


def _drunk_ape(p, x, y, s, lw):
    _ape(p, x, y, s, lw, "drunk")


def _flower(p, x, y, s, lw):
    p.line([(x, y + .45 * s), (x, y)], lw * 1.2, C["leaf2"])
    for i in range(6):
        a = math.radians(i * 60)
        p.circle(x + .14 * s * math.cos(a), y - .1 * s + .14 * s * math.sin(a), .1 * s, fill=C["pink"], w=lw * .8)
    p.circle(x, y - .1 * s, .08 * s, fill=C["gold"], w=lw * .8)


def _ring(p, x, y, s, lw):
    p.circle(x, y + .08 * s, .25 * s, fill=None, w=lw * 2.4, color=C["gold"])
    p.circle(x, y + .08 * s, .25 * s, fill=None, w=lw * .5)
    p.poly([(x - .1 * s, y - .17 * s), (x, y - .32 * s), (x + .1 * s, y - .17 * s), (x, y - .1 * s)], fill=C["sky"], w=lw * .8)


def _soap(p, x, y, s, lw):
    p.rrect(x - .35 * s, y - .15 * s, x + .35 * s, y + .2 * s, 10, fill=(170, 210, 230), w=lw)
    for cx, cy, r in ((-.2, -.3, .09), (.05, -.38, .12), (.25, -.28, .08)):
        p.circle(x + cx * s, y + cy * s, r * s, fill=WHITE, w=lw * .6)


def _medicine(p, x, y, s, lw):
    p.rrect(x - .3 * s, y - .25 * s, x + .3 * s, y + .3 * s, 8, fill=WHITE, w=lw)
    p.rect(x - .06 * s, y - .12 * s, x + .06 * s, y + .18 * s, fill=RED, w=0)
    p.rect(x - .18 * s, y - .0 * s, x + .18 * s, y + .06 * s, fill=RED, w=0)


def _beer_bowl(p, x, y, s, lw):
    p.ellipse(x, y + .05 * s, .5 * s, .18 * s, fill=C["stone2"], w=lw)
    pts = p.ell_pts(x, y + .05 * s, .5 * s, .3 * s, n=24, a0=0, a1=180, wob=False)
    p.poly(pts, fill=C["stone"], w=lw)
    p.ellipse(x, y + .05 * s, .45 * s, .14 * s, fill=C["beer"], w=lw * .8)
    for cx, cy, r in ((-.3, 0, .1), (-.14, -.04, .12), (.03, -.05, .13), (.2, -.03, .12), (.34, .01, .09)):
        p.circle(x + cx * s, y + cy * s, r * s, fill=WHITE, w=lw * .7)


PROPS.update({"beer_bowl": _beer_bowl, "bowl": _beer_bowl, "cat": _cat, "kitten": _cat, "dog": _dog, "puppy": _dog, "lion": _lion, "elephant": _elephant,
              "owl": _owl, "chicken": _chicken, "hen": _chicken, "rooster": _chicken, "bear": _bear,
              "rabbit": _rabbit, "bunny": _rabbit, "frog": _frog, "crocodile": _crocodile, "alligator": _crocodile,
              "ape": _ape_prop, "chimp": _ape_prop, "chimpanzee": _ape_prop, "gorilla": _ape_prop,
              "drunk_ape": _drunk_ape, "flower": _flower, "ring": _ring, "soap": _soap, "medicine": _medicine,
              "doctor": _medicine})
ANIMALS = {"cat", "dog", "lion", "elephant", "owl", "chicken", "bear", "rabbit", "frog", "crocodile", "ape",
           "monkey", "goat", "cow", "pig", "horse", "camel", "mammoth", "deer", "wolf", "fish", "bird", "snake"}


def _louse(p, x, y, s, lw):
    col = (196, 164, 120)
    for d in (-1, 1):
        for k, dy in enumerate((-.1, .02, .14)):
            p.line([(x + d * .12 * s, y + dy * s), (x + d * .32 * s, y + dy * s - .06 * s), (x + d * .4 * s, y + dy * s + .06 * s)], lw * .8)
    p.ellipse(x, y + .1 * s, .17 * s, .26 * s, fill=col, w=lw)
    p.ellipse(x, y - .2 * s, .12 * s, .1 * s, fill=col, w=lw)
    for d in (-1, 1):
        p.line([(x + d * .05 * s, y - .28 * s), (x + d * .14 * s, y - .42 * s)], lw * .7)
        _eye(p, x + d * .05 * s, y - .21 * s, .035 * s)
    for i in range(3):
        p.line([(x - .1 * s, y + (.02 + i * .1) * s), (x + .1 * s, y + (.02 + i * .1) * s)], lw * .5, (150, 120, 84), wob=0)


def _snail(p, x, y, s, lw):
    p.poly([(x - .45 * s, y + .3 * s), (x + .35 * s, y + .3 * s), (x + .45 * s, y + .1 * s), (x + .3 * s, y + .12 * s), (x - .4 * s, y + .2 * s)], fill=(214, 190, 160), w=lw)
    for d in (.32, .4):
        p.line([(x + d * s, y + .12 * s), (x + (d + .05) * s, y - .08 * s)], lw * .7)
        p.dot(x + (d + .05) * s, y - .08 * s, .025 * s)
    p.circle(x - .05 * s, y - .02 * s, .3 * s, fill=C["purple"], w=lw)
    pts = [(x - .05 * s + .25 * s * t / 14 * math.cos(t), y - .02 * s + .25 * s * t / 14 * math.sin(t)) for t in [i * .3 for i in range(48)]]
    p.line(pts, lw * .7, INK, wob=0)


def _shoe(p, x, y, s, lw):
    col = (150, 104, 66)
    p.poly([(x - .4 * s, y + .2 * s), (x - .38 * s, y - .15 * s), (x - .15 * s, y - .18 * s), (x - .05 * s, y),
            (x + .35 * s, y + .05 * s), (x + .45 * s, y + .2 * s)], fill=col, w=lw)
    p.line([(x - .42 * s, y + .22 * s), (x + .47 * s, y + .22 * s)], lw * 1.6)
    for i in range(3):
        p.line([(x - .25 * s + i * .08 * s, y - .12 * s), (x - .18 * s + i * .08 * s, y - .02 * s)], lw * .6, C["sand"])


def _beads(p, x, y, s, lw):
    pts = p.ell_pts(x, y, .38 * s, .28 * s, n=14, a0=0, a1=360, wob=False)
    p.line(pts, lw * .5, C["bark"], wob=0)
    for i, (bx, by) in enumerate(pts[:-1]):
        p.circle(bx, by, .06 * s, fill=(240, 232, 214) if i % 2 else C["gold"], w=lw * .6)


def _fur_coat(p, x, y, s, lw):
    col = C["fur"]
    p.poly([(x - .15 * s, y - .4 * s), (x + .15 * s, y - .4 * s), (x + .38 * s, y + .4 * s), (x - .38 * s, y + .4 * s)], fill=col, w=lw)
    for i in range(7):
        xx = x - .34 * s + i * .113 * s
        p.poly([(xx, y + .4 * s), (xx + .056 * s, y + .5 * s), (xx + .113 * s, y + .4 * s)], fill=col, w=lw * .6)
    p.line([(x, y - .4 * s), (x, y + .4 * s)], lw * .6, C["fur2"])


def _dress(p, x, y, s, lw):
    col = (236, 226, 200)
    p.poly([(x - .12 * s, y - .42 * s), (x + .12 * s, y - .42 * s), (x + .22 * s, y - .3 * s), (x + .42 * s, y - .2 * s),
            (x + .3 * s, y - .05 * s), (x + .2 * s, y - .12 * s), (x + .3 * s, y + .45 * s), (x - .3 * s, y + .45 * s),
            (x - .2 * s, y - .12 * s), (x - .3 * s, y - .05 * s), (x - .42 * s, y - .2 * s), (x - .22 * s, y - .3 * s)], fill=col, w=lw)
    for i in range(4):
        p.line([(x - .15 * s + i * .1 * s, y - .25 * s), (x - .18 * s + i * .1 * s, y - .05 * s)], lw * .45, (170, 160, 140), wob=.2)


def _toga(p, x, y, s, lw):
    p.poly([(x - .3 * s, y - .35 * s), (x + .25 * s, y - .4 * s), (x + .35 * s, y + .45 * s), (x - .35 * s, y + .45 * s)], fill=WHITE, w=lw)
    p.line(p.bez((x - .3 * s, y - .3 * s), (x + .1 * s, y), (x + .3 * s, y + .4 * s)), lw * .7, C["purple"], wob=0)


def _magnifier(p, x, y, s, lw):
    p.line([(x + .15 * s, y + .15 * s), (x + .42 * s, y + .42 * s)], lw * 2.4, C["bark"], wob=0)
    p.circle(x - .05 * s, y - .05 * s, .28 * s, fill=(220, 238, 246), w=lw * 1.4)


PROPS.update({"louse": _louse, "lice": _louse, "bug": _louse, "flea": _louse, "snail": _snail, "murex": _snail,
              "shoe": _shoe, "sandal": _shoe, "beads": _beads, "necklace": _beads, "fur_coat": _fur_coat,
              "coat": _fur_coat, "clothes": _fur_coat, "dress": _dress, "shirt": _dress, "toga": _toga,
              "magnifier": _magnifier, "magnifying_glass": _magnifier})
ANIMALS = ANIMALS | {"louse", "snail"}


def prop_name(n):
    n = (n or "").lower().strip().replace(" ", "_").replace("-", "_")
    if n in PROPS:
        return n
    if n.endswith("s") and n[:-1] in PROPS:
        return n[:-1]
    return None


def draw_prop(pen, name, x, y, s, lw=None):
    n = prop_name(name)
    lw = lw or max(2.2, s * 0.028)
    if n is None:
        # unknown prop -> a small labelled box so nothing crashes
        pen.rrect(x - .45 * s, y - .25 * s, x + .45 * s, y + .25 * s, 10, fill=C["paper"], w=lw)
        pen.text(x, y, str(name)[:10].upper(), int(s * .2), "hand")
        return
    PROPS[n](pen, x, y, s, lw)


# =====================================================================
#  BACKGROUNDS  (w x h logical)
# =====================================================================
BGS = ["white", "jungle", "desert", "snow", "cave", "night", "village", "sea", "city", "grass", "market", "lab", "river", "mountains"]
BG_ALIAS = {"forest": "jungle", "savanna": "grass", "plains": "grass", "field": "grass", "farm": "grass",
            "egypt": "desert", "beach": "sea", "ocean": "sea", "campfire": "night", "town": "village",
            "ice": "snow", "ice_age": "snow", "indoor": "cave", "temple": "market", "street": "city", "home": "village"}


def norm_bg(b):
    b = (b or "white").lower().strip()
    b = BG_ALIAS.get(b, b)
    return b if b in BGS else "white"


def ground_y(bg, h):
    return h * {"white": .86, "cave": .84, "sea": .8, "lab": .84}.get(bg, .8)


def draw_bg(pen, bg, w, h, seed=0):
    bg = norm_bg(bg)
    rnd = random.Random(seed)
    lw = h * .0045
    gy = ground_y(bg, h)
    k = pen.k
    full = [0, 0, w * k, h * k]

    def fill(c):
        pen.d.rectangle(full, fill=c)

    def ground(c, y=gy):
        pen.poly([(-20, y), (w * .3, y - h * .01), (w * .7, y + h * .008), (w + 20, y), (w + 20, h + 20), (-20, h + 20)], fill=c, w=lw)

    def hills(c, base, amp, n=3):
        pts = [(-20, h + 20), (-20, base)]
        for i in range(n * 8 + 1):
            xx = w * i / (n * 8)
            pts.append((xx, base - amp * (0.5 + 0.5 * math.sin(i / 8 * math.pi * 2 / 1.0 + seed))))
        pts += [(w + 20, base), (w + 20, h + 20)]
        pen.poly(pts, fill=c, w=lw)

    if bg == "white":
        fill(WHITE)
        pen.line([(w * .08, gy), (w * .92, gy)], lw * .8, (215, 215, 210), wob=1)
    elif bg == "jungle":
        fill(C["sky"])
        hills(C["leaf2"], gy - h * .12, h * .06, 2)
        for i in range(7):
            _tree(pen, w * (i + .5) / 7 + rnd.uniform(-30, 30), gy - h * .18, h * .45, lw)
        ground(C["grass2"])
        for i in range(10):
            xx = rnd.uniform(0, w)
            pen.poly([(xx - 30, gy + 10), (xx, gy - 30), (xx + 30, gy + 10)], fill=C["leaf"], w=lw * .7)
    elif bg == "desert":
        fill((236, 220, 188))
        _sun(pen, w * .82, h * .18, h * .22, lw)
        hills(C["sand2"], gy - h * .05, h * .05, 1)
        ground(C["sand"])
        for i in range(3):
            xx = rnd.uniform(w * .05, w * .95)
            pen.line([(xx, gy + h * .07), (xx + 60, gy + h * .065)], lw * .6, C["sand2"])
    elif bg == "snow":
        fill((214, 228, 238))
        _mountain(pen, w * .25, gy - h * .25, h * .6, lw)
        _mountain(pen, w * .7, gy - h * .2, h * .5, lw)
        ground(C["snow"])
        for i in range(40):
            pen.dot(rnd.uniform(0, w), rnd.uniform(0, gy), rnd.uniform(3, 6), WHITE)
    elif bg == "cave":
        fill(C["cave2"])
        pen.poly([(w * .1, h * .15), (w * .5, h * .05), (w * .9, h * .15), (w * .95, gy), (w * .05, gy)], fill=C["cave"], w=lw)
        for i in range(6):
            xx = w * (i + .5) / 6
            pen.poly([(xx - 30, h * .1), (xx, h * .1 + rnd.uniform(60, 130)), (xx + 30, h * .1)], fill=C["cave2"], w=lw * .8)
        ground(C["stone2"])
        # cave painting
        _deer(pen, w * .8, h * .38, h * .16, lw * .6)
    elif bg == "night":
        fill(C["night"])
        _moon(pen, w * .82, h * .17, h * .2, lw)
        for i in range(30):
            pen.dot(rnd.uniform(0, w), rnd.uniform(0, h * .55), rnd.uniform(2, 4), (250, 240, 200))
        hills(C["night2"], gy - h * .06, h * .05, 2)
        ground((48, 58, 60))
    elif bg == "village":
        fill(C["sky"])
        _cloud(pen, w * .2, h * .15, h * .16, lw)
        _cloud(pen, w * .72, h * .12, h * .12, lw)
        hills(C["grass"], gy - h * .1, h * .05, 2)
        for i, xx in enumerate((.1, .28, .75, .92)):
            _hut(pen, w * xx, gy - h * .2, h * .32, lw)
        ground(C["sand"])
    elif bg == "sea":
        fill(C["sky"])
        _sun(pen, w * .15, h * .15, h * .18, lw)
        pen.poly([(-20, h * .5), (w + 20, h * .5), (w + 20, h + 20), (-20, h + 20)], fill=C["sea"], w=lw)
        for i in range(12):
            xx, yy = rnd.uniform(0, w), rnd.uniform(h * .55, h * .78)
            pen.arc(xx, yy, 28, 10, 200, 340, lw * .7, C["sea2"])
        ground(C["sand"], h * .82)
    elif bg == "city":
        fill(C["sky"])
        for i in range(9):
            bw = w / 9
            bh = h * rnd.uniform(.25, .5)
            x0 = i * bw
            pen.rect(x0 + 6, gy - bh, x0 + bw - 6, gy, fill=C["city"] if i % 2 else C["city2"], w=lw)
            for r_ in range(int(bh / 70)):
                for c_ in range(2):
                    pen.rect(x0 + 25 + c_ * bw * .4, gy - bh + 25 + r_ * 70, x0 + 25 + c_ * bw * .4 + bw * .2, gy - bh + 55 + r_ * 70, fill=C["sky2"], w=lw * .5)
        ground((150, 150, 148))
    elif bg == "grass":
        fill(C["sky"])
        _cloud(pen, w * .3, h * .16, h * .14, lw)
        _sun(pen, w * .85, h * .15, h * .17, lw)
        hills(C["grass"], gy - h * .08, h * .06, 2)
        _tree(pen, w * .1, gy - h * .2, h * .45, lw)
        ground(C["grass2"])
    elif bg == "market":
        fill((240, 226, 196))
        pen.rect(-10, h * .2, w + 10, gy, fill=C["wall"], w=lw)
        for i in range(4):
            x0 = w * (i * .25 + .02)
            pen.rect(x0, gy - h * .25, x0 + w * .2, gy, fill=C["sand2"], w=lw)
            stripes = 5
            for j in range(stripes):
                xx = x0 + j * w * .2 / stripes
                pen.rect(xx, gy - h * .38, xx + w * .2 / stripes, gy - h * .3, fill=C["clay"] if j % 2 else WHITE, w=lw * .6)
            _pot(pen, x0 + w * .06, gy - h * .3, h * .08, lw * .7)
            _bread(pen, x0 + w * .14, gy - h * .28, h * .07, lw * .7)
        ground(C["sand"])
    elif bg == "lab":
        fill((236, 242, 244))
        pen.line([(0, h * .55), (w, h * .55)], lw * .6, (200, 210, 214))
        pen.rect(w * .05, gy - h * .18, w * .95, gy, fill=(220, 226, 230), w=lw)
        for i in range(5):
            _bottle(pen, w * (.15 + i * .17), gy - h * .25, h * .12, lw * .7)
        ground((210, 214, 216))
    elif bg == "river":
        fill(C["sky"])
        hills(C["grass"], gy - h * .1, h * .06, 2)
        ground(C["grass2"])
        pen.poly([(w * .35, gy), (w * .55, gy), (w * .75, h + 20), (w * .2, h + 20)], fill=C["sea"], w=lw)
        _tree(pen, w * .12, gy - h * .2, h * .45, lw)
    elif bg == "mountains":
        fill(C["sky"])
        _mountain(pen, w * .3, gy - h * .25, h * .65, lw)
        _mountain(pen, w * .72, gy - h * .2, h * .55, lw)
        ground(C["grass2"])
    return gy


# =====================================================================
#  MAP  (equirectangular, rough hand-made continents)
# =====================================================================
LAND = [
    [(-168, 66), (-160, 71), (-140, 70), (-120, 72), (-95, 72), (-80, 73), (-65, 62), (-56, 52), (-66, 45), (-70, 41), (-76, 35), (-81, 31), (-80, 25), (-84, 30), (-90, 29), (-97, 26), (-97, 21), (-92, 18), (-87, 21), (-88, 15), (-83, 9), (-78, 8), (-86, 12), (-92, 14), (-105, 20), (-110, 24), (-112, 31), (-117, 32), (-124, 40), (-124, 48), (-130, 55), (-140, 60), (-152, 58), (-165, 60)],
    [(-55, 60), (-45, 60), (-20, 70), (-20, 80), (-40, 83), (-65, 80), (-72, 77), (-55, 68)],
    [(-80, 8), (-75, 11), (-62, 11), (-50, 2), (-35, -5), (-38, -13), (-41, -22), (-48, -27), (-58, -35), (-63, -42), (-68, -52), (-72, -53), (-75, -45), (-72, -30), (-71, -18), (-77, -12), (-81, -5), (-80, 1)],
    [(-10, 36), (-9, 43), (-2, 44), (-4, 48), (2, 51), (8, 54), (8, 57), (5, 59), (5, 62), (14, 68), (25, 71), (40, 68), (60, 70), (80, 73), (100, 77), (115, 74), (140, 72), (160, 70), (180, 68), (180, 65), (170, 60), (162, 58), (156, 51), (142, 58), (140, 55), (135, 43), (129, 35), (122, 40), (120, 32), (122, 25), (114, 22), (108, 21), (106, 10), (100, 13), (104, 1), (98, 8), (98, 16), (92, 22), (88, 22), (80, 15), (77, 8), (73, 17), (68, 24), (62, 25), (57, 26), (56, 23), (59, 22), (52, 16), (43, 12), (39, 20), (34, 28), (33, 31), (35, 36), (28, 37), (26, 40), (23, 36), (21, 40), (19, 42), (13, 45), (16, 41), (18, 40), (12, 38), (8, 44), (3, 43), (-3, 37)],
    [(-17, 21), (-17, 15), (-12, 8), (-5, 5), (5, 5), (9, 4), (10, -2), (12, -5), (14, -12), (12, -18), (15, -27), (18, -34), (25, -34), (32, -29), (35, -24), (40, -15), (40, -10), (39, -5), (42, 0), (51, 11), (43, 12), (38, 18), (33, 28), (32, 31), (20, 32), (11, 33), (10, 37), (-1, 35), (-6, 36), (-10, 30), (-13, 27)],
    [(114, -22), (114, -34), (118, -35), (130, -32), (138, -35), (146, -39), (150, -37), (153, -28), (153, -25), (145, -15), (142, -11), (136, -12), (130, -12), (125, -15), (122, -18)],
    [(-5, 50), (1, 51), (1, 53), (-2, 56), (-3, 58.5), (-6, 58), (-5, 55), (-3, 54), (-5, 52)],
    [(130, 31), (132, 34), (136, 35), (141, 36), (142, 40), (141, 45), (140, 41), (135, 34)],
    [(44, -25), (47, -25), (50, -15), (49, -12), (44, -17)],
    [(109, 1), (117, 7), (119, 1), (116, -4), (110, -3)],
    [(95, 5), (106, -6), (102, -4), (98, 2)],
    [(167, -46), (174, -41), (178, -38), (173, -35), (172, -41), (166, -46)],
]
REGIONS = {
    "world": (20, 20, 1.0), "mesopotamia": (44, 33, 2.4), "sumer": (46, 31, 2.6), "babylon": (44, 32.5, 2.6),
    "iraq": (44, 33, 2.4), "egypt": (31, 27, 2.4), "nile": (31, 26, 2.4), "africa": (20, 5, 1.5),
    "east africa": (37, 0, 2.0), "kenya": (37, 0, 2.2), "ethiopia": (39, 9, 2.2), "south africa": (25, -29, 2.2),
    "europe": (15, 50, 2.0), "greece": (22, 39, 2.8), "rome": (12, 42, 2.8), "italy": (12, 42, 2.6),
    "britain": (-2, 54, 2.8), "england": (-1, 52, 2.8), "france": (2, 46, 2.6), "spain": (-4, 40, 2.6),
    "germany": (10, 51, 2.6), "scandinavia": (15, 63, 2.2), "levant": (35, 32, 2.8), "israel": (35, 31.5, 2.8),
    "turkey": (33, 39, 2.6), "anatolia": (33, 39, 2.6), "persia": (53, 32, 2.4), "iran": (53, 32, 2.4), "morocco": (-7, 32, 2.6), "denisova": (85, 51, 2.4), "altai": (85, 51, 2.4), "alps": (11, 46.8, 2.8), "oregon": (-121, 43.5, 2.6), "kenya": (37, 0, 2.2), "indonesia": (120, -2, 2.0),
    "arabia": (45, 23, 2.2), "india": (78, 22, 2.2), "indus": (69, 27, 2.4), "pakistan": (69, 29, 2.4),
    "china": (105, 35, 2.0), "japan": (138, 36, 2.6), "mongolia": (103, 47, 2.2), "siberia": (100, 62, 1.8),
    "russia": (90, 60, 1.6), "indonesia": (115, -2, 2.0), "australia": (134, -25, 2.0),
    "americas": (-90, 15, 1.3), "north america": (-100, 45, 1.6), "usa": (-98, 39, 2.0), "america": (-98, 39, 2.0),
    "canada": (-100, 58, 1.8), "alaska": (-150, 64, 2.2), "bering": (-170, 65, 2.2), "mexico": (-100, 22, 2.4),
    "maya": (-89, 18, 2.6), "aztec": (-99, 19.5, 2.6), "peru": (-75, -10, 2.4), "inca": (-72, -13, 2.4),
    "south america": (-60, -15, 1.6), "georgia": (43.5, 42, 2.6), "armenia": (45, 40.2, 2.8), "caucasus": (44, 42, 2.4),
    "guinea": (-10, 10.5, 2.4), "west africa": (-5, 10, 2.0), "nubia": (32, 19, 2.4), "sudan": (32, 16, 2.2), "iran": (53, 32, 2.4), "brazil": (-50, -10, 2.0), "asia": (90, 40, 1.4), "middle east": (45, 30, 2.0),
}


def region_lookup(name):
    n = (name or "world").lower().strip()
    if n in REGIONS:
        return REGIONS[n]
    for k_, v in REGIONS.items():
        if k_ in n or n in k_:
            return v
    return REGIONS["world"]


def draw_map(pen, w, h, region="world", label=None, prop=None):
    """Draws a world map; returns focus point (x,y) in pixels and suggested zoom."""
    pen.d.rectangle([0, 0, w * pen.k, h * pen.k], fill=(204, 228, 236))
    lw = h * .0035
    mx0, my0, mx1, my1 = w * .03, h * .06, w * .97, h * .94

    def P(lon, lat):
        return (mx0 + (lon + 180) / 360 * (mx1 - mx0), my0 + (82 - lat) / (82 + 58) * (my1 - my0))

    for poly in LAND:
        pen.poly([P(*q) for q in poly], fill=(232, 216, 176), w=lw, wob=.6)
    lon, lat, zoom = region_lookup(region)
    fx, fy = P(lon, lat)
    if (region or "world").lower() != "world":
        rr = h * .06 / max(1, zoom * .6)
        pen.circle(fx, fy, rr, fill=RED, w=lw)
        pen.circle(fx, fy, rr * 2.2, fill=None, w=lw, color=RED)
    if prop:
        draw_prop(pen, prop, fx + h * .06, fy - h * .06, h * .12 / max(1, zoom * .5))
    if label:
        size = h * .07 / max(1, zoom * .55)
        tw = pen.text_w(label.upper(), size, "oswald")
        lx = min(max(fx + size * 1.5, tw / 2 + 20), w - tw / 2 - 20)
        ly = max(fy - size * 2.2, size)
        pen.rrect(lx - tw / 2 - size * .4, ly - size * .7, lx + tw / 2 + size * .4, ly + size * .7, size * .25, fill=WHITE, w=lw)
        pen.text(lx, ly, label.upper(), size, "oswald")
        pen.line([(lx - tw / 4, ly + size * .7), (fx + size * .3, fy - size * .3)], lw)
    return (fx / w, fy / h), zoom


# =====================================================================
#  TEXT HELPERS
# =====================================================================
def wrap(pen, text, size, fname, maxw, weight=None):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if pen.text_w(t, size, fname, weight) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def fit_text(pen, text, fname, maxw, maxh, start, minsize=20, weight=None, line_gap=1.05):
    size = start
    while size > minsize:
        lines = wrap(pen, text, size, fname, maxw, weight)
        if len(lines) * size * line_gap <= maxh and all(pen.text_w(l, size, fname, weight) <= maxw for l in lines):
            return size, lines
        size = int(size * .92)
    return minsize, wrap(pen, text, minsize, fname, maxw, weight)


def hand_caption(pen, w, y, text, maxw=None, size=None):
    maxw = maxw or w * .8
    size, lines = fit_text(pen, text.upper(), "hand", maxw, (size or w * .05) * 2.3, size or int(w * .05))
    for i, l in enumerate(lines):
        pen.text(w / 2, y + i * size * 1.05, l, size, "hand", INK, stroke=size * .02)
    return y + len(lines) * size * 1.05


def label_arrow(pen, tx, ty, ax, ay, text, size=40):
    lw = size * .1
    tw = pen.text_w(text.upper(), size, "oswald")
    pen.rrect(tx - tw / 2 - size * .45, ty - size * .72, tx + tw / 2 + size * .45, ty + size * .72, size * .2, fill=WHITE, w=lw)
    pen.text(tx, ty, text.upper(), size, "oswald")
    sx, sy = tx, ty + (size * .75 if ay > ty else -size * .75)
    pen.line([(sx, sy), (ax, ay)], lw)
    a = math.atan2(ay - sy, ax - sx)
    for d in (2.6, -2.6):
        pen.line([(ax, ay), (ax + size * .45 * math.cos(a + d), ay + size * .45 * math.sin(a + d))], lw)
