"""Turns one shot description (dict) into a picture."""
import random, math
from PIL import Image
from . import draw as D

SHOT_TYPES = ["me", "big", "draw", "crowd", "diagram", "map", "compare", "timeline", "list"]
TYPE_ALIAS = {"narrator": "me", "text": "big", "bigtext": "big", "scene": "draw", "process": "diagram",
              "vs": "compare", "comparison": "compare", "steps": "diagram", "people": "crowd", "image": "draw",
              "ai": "draw", "bullets": "list"}


def norm_type(t):
    t = (t or "me").lower().strip()
    t = TYPE_ALIAS.get(t, t)
    return t if t in SHOT_TYPES else "me"


def _seed(shot):
    return abs(hash(str(sorted((k, str(v)) for k, v in shot.items() if k not in ("dur", "words"))))) % 100000


_SPR = None   # when a list: floating elements are collected here instead of drawn
SKY = ("sun", "moon", "cloud", "star", "bird", "lightning")
FLOAT_OK = True


def _sprite(name, x, y, size, anim, mark=None):
    """Draw now, or hand over as a floating sprite when the renderer asked for them."""
    if _SPR is not None and FLOAT_OK:
        _SPR.append(dict(name=name, x=x, y=y, size=size, anim=anim, mark=mark))
        return True
    return False


def render(shot, W=1920, H=1080, K=2, blink=False, mouth=0.0, bob=0.0, out_scale=1.0, ai_image=None, sprites=None):
    """Return (RGB image of size W*out_scale x H*out_scale, focus(x,y in 0..1), zoom_hint).
    If `sprites` is a list, floating props are NOT drawn but appended to it (logical coords)."""
    global _SPR
    _SPR = sprites
    try:
        return _render(shot, W, H, K, blink, mouth, bob, out_scale, ai_image)
    finally:
        _SPR = None


def _render(shot, W, H, K, blink, mouth, bob, out_scale, ai_image):
    t = norm_type(shot.get("type"))
    img = D.new_canvas(W, H, K)
    seed = shot.get("seed", _seed(shot))
    pen = D.Pen(img, K, seed=seed)
    focus, zoom = (0.5, 0.45), 1.0
    st = dict(blink=blink, mouth=mouth, bob=bob)
    if t == "me":
        focus = _me(pen, shot, W, H, st)
    elif t == "big":
        _big(pen, shot, W, H)
    elif t == "draw":
        if ai_image is not None:
            img = _ai_with_overlays(ai_image, shot, W, H, K)
            pen = D.Pen(img, K, seed=seed)
            _overlays(pen, shot, W, H, D.ground_y("white", H), [])
        else:
            focus = _scene(pen, shot, W, H, st)
    elif t == "crowd":
        _crowd(pen, shot, W, H, st)
    elif t == "diagram":
        _diagram(pen, shot, W, H)
    elif t == "map":
        focus, zoom = D.draw_map(pen, W, H, shot.get("region", "world"), shot.get("label"), shot.get("prop"))
    elif t == "compare":
        _compare(pen, shot, W, H, st)
    elif t == "timeline":
        _timeline(pen, shot, W, H)
    elif t == "list":
        _list(pen, shot, W, H)
    out = img.resize((int(W * out_scale), int(H * out_scale)), Image.LANCZOS)
    return out, focus, zoom


# ---------------------------------------------------------------------
def _me(pen, s, W, H, st):
    text = (s.get("text") or "").strip()
    prop = s.get("prop")
    mark = "x" if s.get("cross") else ("tick" if s.get("tick") else None)
    top = H * .06
    if text:
        top = D.hand_caption(pen, W, H * .145, text, maxw=W * .78, size=int(H * .085)) + H * .01
    feet = H * .93
    avail = feet - top
    Hh = min(H * .62, avail * .86)  # figure is ~1.14x taller than Hh (head on top)
    if prop:
        cx = W * .38
        D.draw_person(pen, cx, feet, Hh, s.get("pose", "point"), s.get("face", "neutral"), **st,
                      flip=False, lw=H * .0075, shadow=True)
        ps = min(H * .3, Hh * .55)
        px, py = W * .66, feet - Hh * .45
        if not _sprite(prop, px, py, ps, "float", mark):
            D.draw_prop(pen, prop, px, py, ps, lw=H * .0055)
            if mark:
                D.draw_prop(pen, mark, px, py, ps * 1.05)
        return (0.5, (top / H + .93) / 2)
    D.draw_person(pen, W / 2, feet, Hh, s.get("pose", "stand"), s.get("face", "neutral"), **st, lw=H * .0075, shadow=True)
    if mark:
        D.draw_prop(pen, mark, W * .72, feet - Hh * .5, H * .22)
    return (0.5, (top / H + .93) / 2)


def _big(pen, s, W, H):
    text = (s.get("text") or "").strip() or "..."
    sub = (s.get("sub") or "").strip()
    size, lines = D.fit_text(pen, text.upper(), "oswald", W * .86, H * (.5 if sub else .62), int(H * .26), weight="Bold", line_gap=1.08)
    total = len(lines) * size * 1.08 + (H * .1 if sub else 0)
    y = H / 2 - total / 2 + size * .54
    color = D.INK
    for l in lines:
        pen.text(W / 2, y, l, size, "oswald", color, weight="Bold")
        y += size * 1.08
    if sub:
        pen.text(W / 2, y + H * .02, sub.upper(), int(H * .055), "hand", (90, 90, 90))
    if s.get("underline", True) and len(lines) <= 2:
        uw = min(W * .7, max(D.Pen.text_w(pen, l, size, "oswald", "Bold") for l in lines))
        uy = y - size * .5 + H * .03
        if not sub:
            pen.line([(W / 2 - uw / 2, uy), (W / 2 + uw / 2, uy + 6)], H * .012, D.YELLOW, wob=2)


def _spread(n, x0, x1):
    if n <= 0:
        return []
    if n == 1:
        return [(x0 + x1) / 2]
    return [x0 + (x1 - x0) * i / (n - 1) for i in range(n)]


def _scene(pen, s, W, H, st):
    rnd = random.Random(s.get("seed", 3))
    gy = D.draw_bg(pen, s.get("bg", "white"), W, H, seed=rnd.randint(0, 99))
    people = s.get("people") or []
    if isinstance(people, dict):
        people = [people]
    if isinstance(people, int):
        people = [{} for _ in range(people)]
    props = s.get("props") or []
    if isinstance(props, str):
        props = [props]
    people = people[:6]
    props = props[:5]
    np_, npr = len(people), len(props)
    PH = H * (.5 if np_ <= 2 else .4 if np_ <= 4 else .32)
    if np_ == 1 and D.norm_bg(s.get("bg")) == "white":
        PH = H * .62
    centers = []
    # layout: people in the middle, props around
    if np_ and npr:
        pxs = _spread(np_, W * (.24 if np_ > 1 else .38), W * (.48 if np_ > 1 else .38))
        rxs = _spread(npr, W * .66, W * .88) if npr > 1 else [W * .7]
        if npr >= 3:
            rxs = [W * .14] + _spread(npr - 1, W * .7, W * .88)
    elif np_:
        pxs = _spread(np_, W * .25, W * .75) if np_ > 1 else [W * .5]
        rxs = []
    else:
        pxs = []
        rxs = _spread(npr, W * .25, W * .75) if npr > 1 else ([W * .5] if npr else [])
    for i, x in enumerate(pxs):
        p = people[i] if isinstance(people[i], dict) else {"pose": str(people[i])}
        flip = p.get("flip", x > W * .55 and np_ > 1)
        hold = p.get("hold")
        info = D.draw_person(pen, x, gy + H * .02, PH, p.get("pose", "stand"), p.get("face", "neutral"),
                             flip=flip, lw=H * .0062, holding=hold, outfit=_outfit(p.get("wear")), **st)
        centers.append(info["head"][:2])
    PS = H * (.3 if npr <= 2 else .22)
    if not np_ and npr <= 2:
        PS = H * (.46 if npr == 1 else .36)
    prop_pos = []
    for i, x in enumerate(rxs):
        name = props[i]
        big = D.prop_name(name) in ("cave", "hut", "house", "pyramid", "mountain", "tent", "tree", "palm", "mammoth", "boat", "camel", "horse")
        sz = PS * (1.7 if big else 1.0)
        y = gy - sz * (.42 if big else .32)
        pn = D.prop_name(name)
        anim = None
        if pn in SKY:
            sz = PS * .8
            y = H * .2
            x = W * (.55 + .12 * (i % 3))
            anim = "drift"
        elif not np_ and not big and npr <= 2:
            y = H * .55
            anim = "float"
        elif pn in ("fire", "campfire", "torch"):
            anim = "flicker"
        elif pn in getattr(D, "ANIMALS", ()):
            anim = "idle"
        if (s.get("cross") or s.get("tick")) and i == 0:
            anim = None
        if not (anim and _sprite(name, x, y, sz, anim)):
            D.draw_prop(pen, name, x, y, sz, lw=H * .0055)
        prop_pos.append((x, y, sz))
    _overlays(pen, s, W, H, gy, centers, prop_pos)
    if centers:
        fx = sum(c[0] for c in centers) / len(centers) / W
        return (min(.7, max(.3, fx)), .5)
    return (.5, .5)


def _outfit(w):
    return {"fur": D.C["fur"], "skin": D.C["fur"], "robe": D.C["paper"], "white": D.WHITE, "red": D.C["clay"],
            "blue": D.C["blue"], "green": D.C["leaf"], "toga": D.WHITE, "rich": D.C["purple"], "gold": D.C["gold"]}.get((w or "").lower())


def _overlays(pen, s, W, H, gy, centers, prop_pos=()):
    if s.get("think") and centers:
        hx, hy = centers[0]
        bx, by = hx + H * .2, max(H * .2, hy - H * .25)
        if not _sprite("__think__:" + str(s["think"]), bx, by, H * .32, "float"):
            D.draw_prop(pen, "thought", bx, by, H * .32)
            D.draw_prop(pen, s["think"], bx + H * .02, by - H * .05, H * .14)
    if s.get("cross") or s.get("tick"):
        mark = "x" if s.get("cross") else "tick"
        if prop_pos:
            x, y, sz = prop_pos[0]
            D.draw_prop(pen, mark, x, y, sz * .9)
        else:
            D.draw_prop(pen, mark, W * .5, H * .45, H * .45)
    if s.get("label"):
        if prop_pos:
            ax, ay, sz = prop_pos[-1]
            ay -= sz * .45
        elif centers:
            ax, ay = centers[0]
            ay -= H * .08
        else:
            ax, ay = W * .5, H * .5
        tx = min(max(ax, W * .16), W * .84)
        D.label_arrow(pen, tx, H * .12, ax, ay, str(s["label"]), size=int(H * .045))
    if s.get("text"):
        tw = pen.text_w(s["text"].upper(), H * .065, "hand")
        if not s.get("label"):
            pen.rrect(W / 2 - tw / 2 - 30, H * .05, W / 2 + tw / 2 + 30, H * .15, 18, fill=D.WHITE, w=H * .004)
            pen.text(W / 2, H * .1, s["text"].upper(), int(H * .065), "hand")


def _ai_with_overlays(ai_img, s, W, H, K):
    im = ai_img.convert("RGB")
    sw, sh = im.size
    tr = W / H
    if sw / sh > tr:
        nw = int(sh * tr)
        im = im.crop(((sw - nw) // 2, 0, (sw - nw) // 2 + nw, sh))
    else:
        nh = int(sw / tr)
        im = im.crop((0, (sh - nh) // 2, sw, (sh - nh) // 2 + nh))
    return im.resize((W * K, H * K), Image.LANCZOS)


def _crowd(pen, s, W, H, st):
    rnd = random.Random(s.get("seed", 7))
    gy = D.draw_bg(pen, s.get("bg", "white"), W, H, seed=3)
    n = max(3, min(int(s.get("count", 9)), 24))
    poses = s.get("poses") or [s.get("pose", "stand")]
    faces = s.get("faces") or [s.get("face", "neutral")]
    rows = 1 if n <= 7 else 2
    per = math.ceil(n / rows)
    k = 0
    for r in range(rows):
        y = gy - r * H * .1 + H * .02
        size = H * (.3 - r * .04) if rows == 2 else H * .36
        xs = _spread(per, W * .1, W * .9)
        for x in (xs if r == 0 else [x + W * .05 for x in xs[:-1]]):
            if k >= n:
                break
            D.draw_person(pen, x + rnd.uniform(-20, 20), y if r == 0 else y - H * .02, size * rnd.uniform(.92, 1.05),
                          poses[k % len(poses)], faces[k % len(faces)], flip=rnd.random() < .5, lw=H * .0042,
                          holding=s.get("hold"))
            k += 1
    _overlays(pen, s, W, H, gy, [])


def _diagram(pen, s, W, H):
    steps = s.get("steps") or []
    norm = []
    for st in steps[:5]:
        if isinstance(st, (list, tuple)):
            norm.append((st[0] if st else "question", st[1] if len(st) > 1 else ""))
        elif isinstance(st, dict):
            norm.append((st.get("prop", "question"), st.get("text", "")))
        else:
            norm.append(("question", str(st)))
    if not norm:
        norm = [("question", "?")]
    top = H * .1
    if s.get("title"):
        top = D.hand_caption(pen, W, H * .12, s["title"], size=int(H * .075))
    n = len(norm)
    gap_ = min(W * .3, W * .72 / max(1, n - 1))
    xs = [W / 2 + (i - (n - 1) / 2) * gap_ for i in range(n)]
    cy = (top + H * .78) / 2 + H * .02
    ps = min(H * .28, W / (n * 1.9))
    lw = H * .0045
    for i, (prop, cap) in enumerate(norm):
        x = xs[i]
        pen.circle(x, cy, ps * .78, fill=(248, 244, 232), w=lw)
        D.draw_prop(pen, prop, x, cy, ps * .95, lw=lw)
        if cap:
            size, lines = D.fit_text(pen, str(cap).upper(), "hand", W / n * .9, H * .14, int(H * .06))
            for j, l in enumerate(lines):
                pen.text(x, cy + ps * .78 + H * .06 + j * size * 1.02, l, size, "hand")
        if i < n - 1:
            x0, x1 = x + ps * .9, xs[i + 1] - ps * .9
            if x1 - x0 > 20:
                pen.line([(x0, cy), (x1, cy)], lw * 1.4)
                pen.line([(x1 - H * .025, cy - H * .025), (x1, cy), (x1 - H * .025, cy + H * .025)], lw * 1.4)


def _compare(pen, s, W, H, st):
    L, R = s.get("left") or {}, s.get("right") or {}
    lw = H * .005
    pen.line([(W / 2, H * .08), (W / 2, H * .92)], lw, (200, 200, 196), wob=1)
    for side, d in ((-1, L), (1, R)):
        cx = W / 2 + side * W * .25
        if d.get("title"):
            pen.text(cx, H * .12, str(d["title"]).upper(), int(H * .075), "oswald", weight="Bold")
        if d.get("person") or d.get("pose") or d.get("face"):
            D.draw_person(pen, cx - W * .06, H * .86, H * .5, d.get("pose", "stand"), d.get("face", "neutral"), lw=lw, **st)
            if d.get("prop"):
                D.draw_prop(pen, d["prop"], cx + W * .12, H * .62, H * .2)
        elif d.get("prop"):
            D.draw_prop(pen, d["prop"], cx, H * .5, H * .38)
        if d.get("text"):
            pen.text(cx, H * .85, str(d["text"]).upper(), int(H * .06), "hand")
        if d.get("mark"):
            D.draw_prop(pen, "x" if d["mark"] in ("x", "cross", "bad") else "tick", cx + W * .15, H * .3, H * .16)
    if s.get("vs", True):
        pen.circle(W / 2, H * .5, H * .07, fill=D.YELLOW, w=lw)
        pen.text(W / 2, H * .5, "VS", int(H * .06), "oswald", weight="Bold")


def _timeline(pen, s, W, H):
    pts = s.get("points") or []
    if s.get("title"):
        D.hand_caption(pen, W, H * .12, s["title"], size=int(H * .075))
    y = H * .6
    lw = H * .006
    pen.line([(W * .06, y), (W * .94, y)], lw)
    pen.line([(W * .92, y - H * .025), (W * .945, y), (W * .92, y + H * .025)], lw)
    xs = _spread(len(pts[:6]), W * .14, W * .84) if len(pts) > 1 else [W / 2]
    for i, p in enumerate(pts[:6]):
        label, prop = (p[0], p[1] if len(p) > 1 else None) if isinstance(p, (list, tuple)) else (str(p), None)
        x = xs[i]
        pen.circle(x, y, H * .018, fill=D.YELLOW, w=lw * .8)
        if prop:
            D.draw_prop(pen, prop, x, y - H * .16, H * .16)
        size, lines = D.fit_text(pen, str(label).upper(), "oswald", W / max(2, len(pts)) * .9, H * .14, int(H * .05), weight="Medium")
        for j, l in enumerate(lines):
            pen.text(x, y + H * .08 + j * size * 1.05, l, size, "oswald", weight="Medium")


def _list(pen, s, W, H):
    items = s.get("items") or []
    items = items[:5]
    top = H * .1
    if s.get("title"):
        top = D.hand_caption(pen, W, H * .12, s["title"], size=int(H * .085)) + H * .03
    n = max(1, len(items))
    step = min(H * .2, (H * .94 - top) / n)
    fsize = int(step * .48)
    texts = []
    for it in items:
        if isinstance(it, (list, tuple)):
            texts.append((it[0], str(it[1]) if len(it) > 1 else ""))
        else:
            texts.append((None, str(it)))
    maxw = max([pen.text_w(t.upper(), fsize, "hand") for _, t in texts] + [1])
    while maxw > W * .66 and fsize > 20:
        fsize = int(fsize * .9)
        maxw = max(pen.text_w(t.upper(), fsize, "hand") for _, t in texts)
    block = step * .9 + maxw
    x0 = (W - block) / 2
    y0 = top + ((H * .94 - top) - n * step) / 2
    for i, (prop, txt) in enumerate(texts):
        yy = y0 + i * step + step / 2
        if prop:
            D.draw_prop(pen, prop, x0 + step * .35, yy, step * .72)
        else:
            pen.circle(x0 + step * .35, yy, step * .12, fill=D.YELLOW, w=H * .004)
        pen.text(x0 + step * .9, yy, txt.upper(), fsize, "hand", anchor="lm")
