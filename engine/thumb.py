"""YouTube thumbnails v2 (1280x720): bold, high-contrast, made to be clicked.

Look: saturated sunburst background, characters/props as "stickers" with a thick
white border and drop shadow, one BIG emotional hero, 2-4 word shocking text
(yellow + white, thick black outline), optional red arrow and red X / green tick.

Spec (script "thumbnails": [ {...}, {...}, {...} ]):
  text      "DRUNK APES?"                      2-4 words, the hook
  title     "Humans Were Drinking Before They Were Human"   (paired video title)
  color     green|orange|yellow|red|blue|purple|dark|pink|teal
  hero      person | ape | drunk_ape | <any prop / animal name>
  face, pose, wear, hold      (for a person hero)
  above     <prop>  big prop above the hero's head (e.g. a bowl of beer)
  bg_prop   <prop>  big prop behind the hero (pyramid, cave, house...)
  props     [<prop>, <prop>]  right side, max 2
  marks     ["x", "tick"]     red X / green tick on those props
  sidekick  {"pose": "point_left", "face": "shocked"}  small person bottom-right
  arrow     true              red arrow from the text to the important thing
  effects   ["stars", "hearts", "sweat", "question", "stink", "money"]
Old style ({"text","face","pose","bg","props","mark"}) still works.
"""
import math, re, random
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from . import draw as D

W, H, K = 1280, 720, 2

COLORS = {
    "green": ((60, 135, 55), (88, 165, 75)), "orange": ((242, 150, 40), (250, 182, 70)),
    "yellow": ((246, 196, 40), (252, 216, 90)), "red": ((196, 52, 44), (222, 82, 66)),
    "blue": ((40, 110, 190), (66, 140, 214)), "purple": ((104, 64, 160), (130, 90, 186)),
    "dark": ((58, 52, 50), (84, 74, 68)), "pink": ((222, 92, 140), (240, 126, 166)),
    "teal": ((30, 140, 140), (54, 170, 166)),
}
BG_TO_COLOR = {"cave": "dark", "night": "purple", "desert": "orange", "market": "orange", "jungle": "green",
               "grass": "green", "village": "yellow", "snow": "blue", "sea": "blue", "river": "teal",
               "city": "blue", "lab": "teal", "mountains": "blue", "white": "yellow"}


# ------------------------------------------------------------------ helpers
def _sunburst(c1, c2, cx=.3, cy=.6, n=18):
    img = Image.new("RGB", (W * K, H * K), c1)
    d = ImageDraw.Draw(img)
    X, Y, R = cx * W * K, cy * H * K, 4000
    for i in range(n):
        a0 = 2 * math.pi * i / n
        a1 = a0 + math.pi / n
        d.polygon([(X, Y), (X + R * math.cos(a0), Y + R * math.sin(a0)), (X + R * math.cos(a1), Y + R * math.sin(a1))], fill=c2)
    v = Image.new("L", img.size, 0)
    ImageDraw.Draw(v).ellipse([-W * K * .3, -H * K * .4, W * K * 1.3, H * K * 1.4], fill=255)
    v = v.filter(ImageFilter.GaussianBlur(160))
    img = Image.composite(img, Image.blend(img, Image.new("RGB", img.size, (0, 0, 0)), .35), v)
    return img.convert("RGBA")


def _layer():
    L = Image.new("RGBA", (W * K, H * K), (0, 0, 0, 0))
    return L, D.Pen(L, K, seed=3, wobble=.6)


def _sticker(base, L, border=14, shadow=True):
    a = L.split()[3]
    if a.getbbox() is None:
        return
    small = a.resize((a.size[0] // 4, a.size[1] // 4), Image.BILINEAR)
    k = max(3, (border // 2) | 1)
    grown = small.filter(ImageFilter.MaxFilter(k)).resize(a.size, Image.BILINEAR)
    grown = grown.point(lambda x: 255 if x > 60 else int(x * 4.2))
    if shadow:
        sh = Image.new("RGBA", L.size, (0, 0, 0, 0))
        sh.putalpha(grown.point(lambda x: int(x * .45)))
        sh = sh.filter(ImageFilter.GaussianBlur(14))
        base.paste(sh, (18, 22), sh)
    white = Image.new("RGBA", L.size, (255, 255, 255, 0))
    white.putalpha(grown)
    base.paste(white, (0, 0), white)
    base.paste(L, (0, 0), L)


def split_text(text):
    words = text.upper().split()
    n = len(words)
    if n <= 1:
        return [text.upper()]
    if n == 2:
        return words
    if words[0][0].isdigit() and n >= 3:
        rest = words[1:]
        if len(rest) == 2:
            return [words[0], rest[0], rest[1]] if len(" ".join(rest)) > 10 else [words[0], " ".join(rest)]
        return [words[0], " ".join(rest[:-1]), rest[-1]]
    if n == 3:
        return [" ".join(words[:2]), words[2]] if len(words[0] + words[1]) <= 9 else [words[0], " ".join(words[1:])]
    if n == 4:
        if len(words[2] + words[3]) > 11:
            return [" ".join(words[:2]), words[2], words[3]]
        return [" ".join(words[:2]), " ".join(words[2:])]
    lines, cur = [], ""
    for w in words:
        if len(cur + " " + w) > 11 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    return lines[:3]


def _text(base, text, box, draw=True):
    """box = (x_right, y_top, max_w, max_h) in 1x pixels. Returns bbox of text (1x)."""
    lines = split_text(text)
    xr, yt, mw, mh = box
    size = 230
    while size > 50:
        f = D.font("bangers", size * K)
        widths = [f.getlength(l) / K for l in lines]
        if max(widths) <= mw and len(lines) * size * .92 <= mh:
            break
        size -= 5
    f = D.font("bangers", size * K)
    if not draw:
        wmax = max(f.getlength(l) / K for l in lines)
        return (xr - wmax, yt, xr, yt + len(lines) * size * .92)
    cols = [D.YELLOW, (255, 255, 255), D.YELLOW]
    T = Image.new("RGBA", base.size, (0, 0, 0, 0))
    td = ImageDraw.Draw(T)
    for i, l in enumerate(lines):
        td.text((xr * K + 12, (yt + i * size * .92) * K + 16), l, font=f, fill=(0, 0, 0, 170), anchor="ra",
                stroke_width=int(12 * K), stroke_fill=(0, 0, 0, 170))
    T = T.filter(ImageFilter.GaussianBlur(6))
    td = ImageDraw.Draw(T)
    for i, l in enumerate(lines):
        td.text((xr * K, (yt + i * size * .92) * K), l, font=f, fill=cols[i % 3], anchor="ra",
                stroke_width=int(11 * K), stroke_fill=D.INK)
    base.paste(T, (0, 0), T)
    wmax = max(f.getlength(l) / K for l in lines)
    return (xr - wmax, yt, xr, yt + len(lines) * size * .92)


def _arrow(p, x0, y0, x1, y1, w=15):
    p.line([(x0, y0), (x1, y1)], w, D.RED, wob=2)
    a = math.atan2(y1 - y0, x1 - x0)
    for d_ in (2.5, -2.5):
        p.line([(x1, y1), (x1 + 46 * math.cos(a + d_), y1 + 46 * math.sin(a + d_))], w, D.RED, wob=1)


def _effects(p, effects, hx, hy, r):
    rnd = random.Random(5)
    for e in effects or []:
        e = str(e).lower()
        if e == "stars":
            for ang in (-150, -100, -40):
                a = math.radians(ang)
                D.draw_prop(p, "star", hx + r * 1.25 * math.cos(a), hy + r * 1.25 * math.sin(a), 60, lw=4)
        elif e == "hearts":
            for ang in (-140, -60, -20):
                a = math.radians(ang)
                D.draw_prop(p, "heart", hx + r * 1.3 * math.cos(a), hy + r * 1.3 * math.sin(a), 70, lw=5)
        elif e == "sweat":
            for dx, dy in ((1.05, -.5), (1.25, -.1)):
                D.draw_prop(p, "drop", hx + r * dx, hy + r * dy, 60, lw=4)
        elif e == "question":
            D.draw_prop(p, "question", hx - r * 1.25, hy - r * 1.0, 140, lw=6)
        elif e == "exclaim":
            D.draw_prop(p, "exclaim", hx - r * 1.25, hy - r * 1.0, 140, lw=6)
        elif e == "stink":
            for dx in (-35, 0, 35):
                p.line([(hx + r * 1.2 + dx, hy - r * .2), (hx + r * 1.2 + dx + 18, hy - r * .55), (hx + r * 1.2 + dx, hy - r * .9)], 7, (110, 140, 50), wob=1)
        elif e == "money":
            for ang in (-150, -90, -30):
                a = math.radians(ang)
                D.draw_prop(p, "coin", hx + r * 1.3 * math.cos(a), hy + r * 1.3 * math.sin(a), 80, lw=5)


# ------------------------------------------------------------------ main
def normalize(spec, idx=0, fallback_text="WAIT, WHAT?"):
    s = dict(spec or {})
    s["text"] = (s.get("text") or fallback_text).strip()
    col = s.get("color") or BG_TO_COLOR.get(D.norm_bg(s.get("bg")) if s.get("bg") else "", None)
    s["color"] = col if col in COLORS else ["green", "orange", "dark"][idx % 3]
    s.setdefault("hero", "person")
    s.setdefault("face", ["shocked", "smug", "confused"][idx % 3])
    s.setdefault("pose", ["scared", "point_up", "shrug"][idx % 3])
    props = s.get("props") or []
    if isinstance(props, str):
        props = [props]
    marks = s.get("marks") or []
    if s.get("mark") and not marks:
        marks = [s["mark"]]
    s["props"], s["marks"] = props[:2], marks[:2]
    if s.get("effects") is None and str(s.get("hero", "person")).lower() not in ("person", "me", "man", "woman", "human"):
        s["effects"] = []
    if s.get("effects") is None:
        s["effects"] = {"laugh": ["stars"], "excited": ["stars"], "scared": ["sweat"], "sweating": ["sweat"],
                        "confused": ["question"], "shocked": [] if s.get("arrow") else ["exclaim"],
                        "disgusted": ["stink"]}.get(s["face"], [])
    return s


def make_pro(spec, idx=0, ai_image=None):
    s = normalize(spec, idx)
    c1, c2 = COLORS[s["color"]]
    base = _sunburst(c1, c2)
    if ai_image is not None:
        a = ai_image.convert("RGB").resize((W * K, H * K), Image.LANCZOS)
        base = Image.blend(base.convert("RGB"), a, .85).convert("RGBA")
    hx_center = W * .28
    has_side = bool(s.get("sidekick")) and len(s["props"]) <= 1
    # background prop behind hero
    if s.get("bg_prop"):
        L, p = _layer()
        D.draw_prop(p, s["bg_prop"], W * .2, H * .72, 420, lw=8)
        _sticker(base, L, border=8, shadow=False)
    # hero
    L, p = _layer()
    hero = str(s["hero"]).lower()
    target = None
    head = (hx_center, H * .35, 150)
    if hero in ("person", "me", "man", "woman", "human"):
        above = s.get("above")
        PH = 600 if above else 680
        feet = 930 if above else 960
        info = D.draw_person(p, hx_center, feet, PH, s["pose"], s["face"], lw=12, outfit=_outfit(s.get("wear")),
                             hat=s.get("hat"), beard=s.get("beard"))
        hx, hy, r = info["head"]
        head = (hx, hy, r)
        if s.get("hold"):
            hands = info.get("hands", {})
            hx2, hy2 = min(hands.values(), key=lambda q: q[1]) if hands else (hx + r, hy + r)
            D.draw_prop(p, s["hold"], hx2 + 20, hy2 - 60, 230, lw=9)
            target = (hx2 + 20, hy2 - 60)
        if above:
            bx, by = hx, max(175, hy - r - 130)
            D.draw_prop(p, above, bx, by, 330, lw=10)
            target = (bx + 175, by)
    elif hero in ("ape", "drunk_ape", "monkey_big", "chimp"):
        D._ape(p, hx_center, H * .62, 700, 11, "drunk" if (hero == "drunk_ape" or s["face"] in ("laugh", "sleepy")) else "happy")
        head = (hx_center, H * .62 - 700 * .2, 700 * .22)
        if s.get("hold"):
            D.draw_prop(p, s["hold"], hx_center + 235, H * .66, 240, lw=9)
            target = (hx_center + 235, H * .58)
    else:
        D.draw_prop(p, hero, hx_center, H * .58, 520, lw=11)
        head = (hx_center + 80, H * .4, 150)
        target = (hx_center + 270, H * .22)
    _effects(p, s["effects"], *head)
    _sticker(base, L)
    # right side props
    props = s["props"]
    if props:
        L, p = _layer()
        pos = ([(W * .62, H * .74)] if len(props) == 1 and has_side else
               [(W * .74, H * .72)] if len(props) == 1 else [(W * .63, H * .75), (W * .83, H * .75)])
        sz = (280 if not has_side else 230) if len(props) == 1 else 180
        for i, pr in enumerate(props):
            x, y = pos[i]
            D.draw_prop(p, pr, x, y, sz, lw=8)
            if i < len(s["marks"]) and s["marks"][i]:
                m = "x" if s["marks"][i] in ("x", "cross", "no", "bad") else "tick"
                D.draw_prop(p, m, x + (0 if m == "x" else sz * .3), y - (0 if m == "x" else sz * .3), sz * (1.05 if m == "x" else .6))
        _sticker(base, L, border=10)
        if target is None and s.get("arrow"):
            target = (pos[0][0], pos[0][1] - sz * .1)
            s["_stop"] = sz * .5
    if has_side:
        L, p = _layer()
        sk = s["sidekick"] if isinstance(s["sidekick"], dict) else {}
        D.draw_person(p, W * .87, 905, 430, sk.get("pose", "point_left"), sk.get("face", "shocked"), lw=10,
                      outfit=_outfit(sk.get("wear")))
        _sticker(base, L)
    # text
    tbox = (W * .975, H * .04, W * (.55 if (props or has_side) else .6), H * (.52 if (props or has_side) else .62))
    tb = _text(base, s["text"], tbox, draw=False)
    if s.get("arrow"):
        L, p = _layer()
        tx, ty = tb[0] + 30, tb[3] + 10
        if target and target[0] > tx - 60:
            # target sits under/right of the text: come in diagonally from the left instead
            tx, ty = max(60, target[0] - 300), max(60, target[1] - 190)
            if math.hypot(target[0] - head[0], target[1] - head[1]) < head[2] * 1.4:
                tx, ty = tb[0] + 30, tb[3] + 10
        if target:
            gx, gy = target
            stop = s.get("_stop", 70)
        else:
            gx, gy = head[0], head[1]
            stop = head[2] * 1.15
        dist = math.hypot(gx - tx, gy - ty)
        if dist > stop + 120:
            ex, ey = gx + (tx - gx) * stop / dist, gy + (ty - gy) * stop / dist
            _arrow(p, tx, ty, ex, ey)
        _sticker(base, L, border=6, shadow=False)
    _text(base, s["text"], tbox)
    img = base.convert("RGB").resize((W, H), Image.LANCZOS)
    img = ImageEnhance.Color(img).enhance(1.15)
    img = ImageEnhance.Contrast(img).enhance(1.05)
    return img


def _outfit(w):
    return {"fur": D.C["fur"], "robe": D.C["paper"], "white": D.WHITE, "toga": D.WHITE, "rich": D.C["purple"],
            "red": D.C["clay"], "blue": D.C["blue"], "green": D.C["leaf"], "gold": D.C["gold"], "pink": D.C["pink"], "purple": D.C["purple"], "dress": D.C["pink"], "yellow": D.YELLOW}.get((w or "").lower())


# ------------------------------------------------------------------ auto ideas
KEYWORD_PROPS = [
    (r"beer|ale|brew", "beer"), (r"wine|grape", "wine"), (r"alcohol|drunk|drink", "beer"), (r"money|coin|pay|tax|rich", "coin"),
    (r"toilet|poop|bathroom", "toilet"), (r"teeth|tooth|dentist", "tooth"), (r"soap|clean|wash|bath", "soap"),
    (r"doctor|medicine|sick|disease|surgery", "medicine"), (r"love|partner|dating|marri|romance", "heart"),
    (r"food|eat|meal|breakfast|dinner", "meat"), (r"bread", "bread"), (r"fire|cook", "fire"), (r"sleep|bed|night", "bed"),
    (r"time|clock|calendar|day", "sundial"), (r"egypt|pyramid", "pyramid"), (r"rome|roman|sword|war|fight", "sword"),
    (r"king|queen|emperor", "crown"), (r"cave|stone age|caveman", "cave"), (r"hunt|mammoth", "mammoth"),
    (r"cat", "cat"), (r"dog", "dog"), (r"horse", "horse"), (r"fish|sea", "fish"), (r"music|song|dance|fun|party", "drum"),
    (r"death|dead|grave|burial", "skull"), (r"write|book|letter|message", "scroll"), (r"travel|boat|ship", "boat"),
    (r"cloth|wear|fashion", "needle"), (r"hair|razor|shave", "axe"), (r"water", "water"), (r"farm|wheat|grain", "wheat"),
]


def guess_props(text):
    t = (text or "").lower()
    out = []
    for rx, prop in KEYWORD_PROPS:
        if re.search(rx, t) and prop not in out:
            out.append(prop)
    return out or ["question"]


def auto_specs(data):
    """Three high-CTR thumbnail ideas (Phase 3: stronger defaults + effects)."""
    title = data.get("title", "")
    blob = title + " " + " ".join(sc.get("chapter", "") for sc in data.get("scenes", []))
    props = guess_props(blob)
    p1 = props[0]
    p2 = props[1] if len(props) > 1 else "question"
    text = data.get("thumbnail_text")
    if not text or len(text) > 22 or text.upper() in ("WAIT, WHAT?", "WAIT WHAT?", "WHAT?"):
        words = [w for w in re.sub(r"[^A-Za-z0-9 ]", " ", title).split() if len(w) > 2]
        if words:
            text = " ".join(words[:3]).upper()
            if len(text) > 18:
                text = " ".join(words[:2]).upper()
        else:
            text = "WAIT, WHAT?"
    seo = data.get("seo") or {}
    titles = (seo.get("titles") or []) + [title] * 3
    return [
        dict(text=text, title=titles[0], color="green", hero="person", pose="scared", face="shocked",
             props=[p1], marks=["x"], arrow=True, effects=["question"]),
        dict(text=text, title=titles[1], color="orange", hero="person", pose="point_up", face="smug", hold=p1,
             props=[p2], marks=["tick"], effects=["stars"]),
        dict(text=text, title=titles[2], color="dark", hero="person", pose="shrug", face="confused",
             props=[p1], sidekick={"pose": "point_left", "face": "shocked"}, arrow=True, effects=["sweat"]),
    ]


def phone_preview(img):
    return img.resize((168, 94), Image.LANCZOS)


# backwards compatible wrapper
def make_thumbnail(text, bg="desert", face="shocked", pose="scared", props=("coin",), mark=None,
                   side_text="right", seed=1, ai_image=None):
    return make_pro(dict(text=text, bg=bg, face=face, pose=pose, props=list(props or []), mark=mark), seed % 3, ai_image)
