"""Video renderer: shots -> frames -> mp4 segments (in parallel) -> final video."""
import os, math, json, subprocess, shutil, time, random, hashlib
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw
from . import shots as S
from . import draw as D

FPS = 30
OVERSCAN = 1.08


def ffmpeg_bin():
    from .ff import ffmpeg
    return ffmpeg()


def _clamp_box(cx, cy, cw, ch, W, H):
    cw = min(cw, W)
    ch = min(ch, H)
    x0 = min(max(0.0, cx - cw / 2), W - cw)
    y0 = min(max(0.0, cy - ch / 2), H - ch)
    return (max(0, x0), max(0, y0), min(W, x0 + cw), min(H, y0 + ch))


def ease(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def animate_flags(shot):
    t = S.norm_type(shot.get("type"))
    if shot.get("_ai"):
        return False, False
    if t == "me":
        return True, True
    if t == "draw" and shot.get("people"):
        return True, False
    if t == "compare" and any(isinstance(shot.get(k), dict) and (shot[k].get("pose") or shot[k].get("face")) for k in ("left", "right")):
        return True, False
    return False, False


OUTDOOR = ("jungle", "desert", "grass", "village", "sea", "river", "mountains", "snow", "ancient")


def _sprite_image(spec, H, scale):
    """Render one floating element to an RGBA image. Returns (img, cx, cy) in output pixels."""
    size = spec["size"]
    B = size * 1.7
    k = 2
    im = Image.new("RGBA", (max(4, int(B * k)), max(4, int(B * k))), (0, 0, 0, 0))
    pen = D.Pen(im, k, seed=7)
    c = B / 2
    name = spec["name"]
    if name.startswith("__think__:"):
        D.draw_prop(pen, "thought", c, c, size)
        D.draw_prop(pen, name.split(":", 1)[1], c + size * .06, c - size * .16, size * .44)
    else:
        D.draw_prop(pen, name, c, c, size, lw=H * .0055)
        if spec.get("mark"):
            D.draw_prop(pen, spec["mark"], c, c, size * 1.05)
    out = max(2, int(B * scale))
    im = im.resize((out, out), Image.LANCZOS)
    return im


def _bird_imgs(px):
    imgs = []
    for up in (True, False):
        k = 3
        im = Image.new("RGBA", (int(px * 2.4 * k), int(px * 1.2 * k)), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        w, h = im.size
        cx, cy = w / 2, h / 2
        s = px * k
        pts = ([(cx - s, cy), (cx - s * .5, cy - s * .45), (cx, cy), (cx + s * .5, cy - s * .45), (cx + s, cy)] if up else
               [(cx - s, cy - s * .12), (cx - s * .5, cy + s * .06), (cx, cy), (cx + s * .5, cy + s * .06), (cx + s, cy - s * .12)])
        d.line(pts, fill=D.INK, width=max(2, int(s * .14)), joint="curve")
        imgs.append(im.resize((int(px * 2.4), int(px * 1.2)), Image.LANCZOS))
    return imgs


class ShotSource:
    """Lazily renders the variants (blink / mouth / bob) of one shot, plus its moving parts."""

    def __init__(self, shot, W, H, ai_path=None, native=False, seed=1):
        self.shot, self.W, self.H = shot, W, H
        self.cache = {}
        self.ai = None
        if ai_path and os.path.exists(ai_path):
            try:
                self.ai = Image.open(ai_path).convert("RGB")
                self.ai.load()
            except Exception:
                self.ai = None
        self.focus, self.zoom_hint = (.5, .5), 1.0
        self.native = native
        self.specs = None
        self.sprites = []
        self.birds = []
        self.snow = None
        self.rnd = random.Random(seed)

    def get(self, blink=False, mouth=0, bob=0):
        key = (blink, mouth, bob)
        if key not in self.cache:
            if len(self.cache) > 8:
                self.cache.pop(next(iter(self.cache)))
            first = self.specs is None
            specs = [] if first else []
            img, f, z = S.render(self.shot, self.W, self.H, K=2, blink=blink, mouth=0.8 if mouth else 0.0,
                                 bob=bob * self.H * .004, out_scale=OVERSCAN, ai_image=self.ai, sprites=specs)
            self.focus, self.zoom_hint = f, z
            self.cache[key] = img
            if first:
                self.specs = specs
                self._prepare()
        return self.cache[key]

    def _prepare(self):
        sc = OVERSCAN
        for i, sp in enumerate(self.specs):
            try:
                im = _sprite_image(sp, self.H, sc)
            except Exception:
                continue
            alt = None
            if sp["anim"] == "flicker":
                w, h = im.size
                alt = Image.new("RGBA", im.size, (0, 0, 0, 0))
                tall = im.resize((w, int(h * 1.07)), Image.BILINEAR)
                alt.paste(tall, (0, h - tall.size[1]), tall)
            self.sprites.append(dict(img=im, alt=alt, x=sp["x"] * sc, y=sp["y"] * sc, anim=sp["anim"],
                                     ph=self.rnd.uniform(0, 6.28), start=3 + 5 * i))
        t = S.norm_type(self.shot.get("type"))
        bg = D.norm_bg(self.shot.get("bg"))
        if self.ai is None and t in ("draw", "crowd") and bg in OUTDOOR and self.shot.get("birds", True):
            n = self.rnd.choice((1, 2, 2, 3))
            imgs = _bird_imgs(self.H * .026 * sc)
            for k in range(n):
                self.birds.append(dict(imgs=imgs, x0=self.rnd.uniform(-.05, .55) * self.W * sc,
                                       y0=self.rnd.uniform(.08, .26) * self.H * sc,
                                       v=self.rnd.uniform(.05, .09) * self.W * sc, ph=self.rnd.uniform(0, 6.28),
                                       flap=self.rnd.randint(3, 5)))
        if bg == "snow" and self.ai is None and t in ("draw", "crowd"):
            self.snow = [(self.rnd.uniform(0, 1), self.rnd.uniform(0, 1), self.rnd.uniform(2, 5), self.rnd.uniform(.04, .09))
                         for _ in range(70)]

    def animated(self):
        return bool(self.sprites or self.birds or self.snow)

    def compose(self, base, i):
        if not self.animated():
            return base
        t = i / FPS
        img = base.copy()
        W, H = img.size
        for sp in self.sprites:
            im = sp["img"]
            dx = dy = 0.0
            a = sp["anim"]
            if a == "float":
                dy = math.sin(t * 2.1 + sp["ph"]) * H * .009
            elif a == "drift":
                dx = math.sin(t * .5 + sp["ph"]) * W * .012
                dy = math.sin(t * 1.1 + sp["ph"]) * H * .004
            elif a == "idle":
                dy = -abs(math.sin(t * 2.6 + sp["ph"])) * H * .006
            elif a == "pop":
                dy = math.sin(t * 1.8 + sp["ph"]) * H * .005
            elif a == "flicker" and sp["alt"] is not None and (i // 3) % 2:
                im = sp["alt"]
            if a in ("pop", "float", "idle"):
                k = i - sp.get("start", 0)
                if k < 0:
                    continue          # not on screen yet
                if k < 8:             # pop in: 0 -> 1.12 -> 1
                    z = (0.35, 0.6, 0.85, 1.05, 1.12, 1.08, 1.03, 1.0)[k]
                    w0, h0 = im.size
                    im = im.resize((max(2, int(w0 * z)), max(2, int(h0 * z))), Image.BILINEAR)
            x = int(sp["x"] + dx - im.size[0] / 2)
            y = int(sp["y"] + dy - im.size[1] / 2)
            img.paste(im, (x, y), im)
        for b in self.birds:
            im = b["imgs"][(i // b["flap"]) % 2]
            x = int(b["x0"] + b["v"] * t)
            if x > W + 50:
                continue
            y = int(b["y0"] + math.sin(t * 1.7 + b["ph"]) * H * .012)
            img.paste(im, (x, y), im)
        if self.snow:
            d = ImageDraw.Draw(img)
            for (fx, fy, r, sp_) in self.snow:
                x = (fx * W + math.sin(t * 1.3 + fy * 9) * 12) % W
                y = ((fy + sp_ * t) % 1.0) * H
                d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255))
        return img


def frame_states(shot, n, mouth_env, seed):
    """Per-frame (blink, mouth, bob) — richer micro-motion."""
    anim, talk = animate_flags(shot)
    rnd = random.Random(seed)
    out = []
    next_blink = rnd.randint(int(FPS * .7), int(FPS * 2.2))
    talk_phase = 0
    bob_speed = 0.75 + (seed % 7) * 0.04
    bob_phase = (seed % 100) * 0.1
    for i in range(n):
        if not anim:
            out.append((False, 0, 0))
            continue
        blink = next_blink <= i < next_blink + rnd.choice([2, 3, 3, 4])
        if i >= next_blink + 4:
            next_blink = i + rnd.randint(int(FPS * 1.8), int(FPS * 4.2))
        bob = 1 if math.sin(i / FPS * math.pi * bob_speed + bob_phase) > 0.15 else 0
        m = 0
        if talk and mouth_env is not None and i < len(mouth_env) and mouth_env[i] > 0.22:
            talk_phase += 1
            m = 1 if (talk_phase // 2) % 2 == 0 else 0
        else:
            talk_phase = 0
        out.append((blink, m, bob))
    return out


def camera(i, n, style, focus, zh, pop):
    """Stronger cinematic camera motion."""
    t = i / max(1, n - 1)
    e = ease(t)
    if style == "in":
        v = 1.0 + 0.085 * e * max(zh, 1.0)
    elif style == "out":
        v = 1.09 * max(zh, 1.0) - 0.075 * e
    elif style == "pan":
        v = 1.08
    else:
        v = 1.0 + 0.045 * t
    if zh > 1.05 and style != "out":
        v = 1.0 + (min(zh, 2.8) - 1.0) * 0.22 * ease(t * 1.25) + 0.025
    if pop and i < 7:
        v *= (1.09, 1.06, 1.04, 1.025, 1.015, 1.008, 1.0)[min(i, 6)]
    fx, fy = focus
    if style == "pan":
        fx = 0.46 + 0.08 * e
        fy = 0.50 + 0.02 * math.sin(t * 3.1)
    if style not in ("pan",) and n > int(FPS * 1.2):
        fx += 0.008 * math.sin(t * 2.4 + (fx or 0.5) * 5)
        fy += 0.006 * math.cos(t * 1.9 + (fy or 0.5) * 4)
    cx = 0.5 + (fx - 0.5) * min(1.0, (v - 1.0) * 5.5)
    cy = 0.5 + (fy - 0.5) * min(1.0, (v - 1.0) * 5.5)
    return max(1.0, v), cx, cy


def render_segment(task):
    """Worker: render one shot to an mp4 segment. task is a dict."""
    out = task["out"]
    if os.path.exists(out) and os.path.getsize(out) > 1000 and task.get("reuse"):
        return task["idx"], out
    stopf = task.get("stopfile")
    W, H = task["W"], task["H"]
    n = task["frames"]
    src = ShotSource(task["shot"], W, H, task.get("ai_path"), seed=task["seed"])
    states = frame_states(task["shot"], n, task.get("env"), task["seed"])
    first = src.get(False, 0, 0)
    style = task.get("cam", "in")
    pop = task.get("pop", False)
    ow, oh = W, H
    cmd = [ffmpeg_bin(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ow}x{oh}", "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-preset", task.get("preset", "veryfast"), "-crf", str(task.get("crf", 20)),
           "-pix_fmt", "yuv420p", "-threads", "2", "-g", "60", out + ".tmp.mp4"]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for i in range(n):
            if stopf and i % 30 == 0 and os.path.exists(stopf):
                raise KeyboardInterrupt("stopped")
            b, m, bb = states[i]
            img = src.compose(src.get(b, m, bb), i)
            IW, IH = img.size
            v, cx, cy = camera(i, n, style, src.focus, src.zoom_hint, pop)
            cw, ch = IW / v, IH / v
            box = _clamp_box(cx * IW, cy * IH, cw, ch, IW, IH)
            fr = img.crop(tuple(int(round(c)) for c in box)).resize((ow, oh), Image.BILINEAR)
            p.stdin.write(fr.tobytes())
        p.stdin.close()
        err = p.stderr.read()
        p.wait()
        if p.returncode != 0:
            raise RuntimeError("ffmpeg segment error: " + err.decode(errors="ignore")[-400:])
        os.replace(out + ".tmp.mp4", out)
    except BaseException:
        try:
            p.stdin.close()
        except Exception:
            pass
        p.kill()
        p.wait()
        raise
    return task["idx"], out


def run_pool(tasks, progress=None, procs=None):
    procs = procs or max(1, min(os.cpu_count() or 2, 8))
    done = 0
    results = {}
    if procs == 1:
        for t in tasks:
            i, o = render_segment(t)
            results[i] = o
            done += 1
            if progress:
                progress(done / len(tasks))
        return results
    with Pool(procs) as pool:
        for i, o in pool.imap_unordered(render_segment, tasks, chunksize=1):
            results[i] = o
            done += 1
            if progress:
                progress(done / len(tasks))
    return results


def concat(segments, audio_wav, out_mp4, workdir):
    lst = os.path.join(workdir, "segments.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for s in segments:
            f.write("file '" + os.path.abspath(s).replace("\\", "/").replace("'", "'\\''") + "'\n")
    tmp = out_mp4 + ".tmp.mp4"
    cmd = [ffmpeg_bin(), "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", audio_wav,
           "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-shortest", "-movflags", "+faststart", tmp]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("Video jodne mein masla: " + r.stderr.decode(errors="ignore")[-500:])
    os.replace(tmp, out_mp4)


def mouth_envelope(audio24, start, frames):
    sr = 24000
    env = np.zeros(frames, np.float32)
    hop = sr // FPS
    for i in range(frames):
        a = int((start + i / FPS) * sr)
        seg = audio24[a:a + hop]
        if len(seg):
            env[i] = float(np.sqrt(np.mean(seg ** 2)))
    mx = np.percentile(env, 95) if frames else 1
    return (env / (mx + 1e-6)).clip(0, 1)


# =====================================================================
#  VERTICAL (Shorts) frames
# =====================================================================
VW, VH = 1080, 1920
PANEL_Y, PANEL_H = 215, 960
CAP_Y = 1290


def _cap_font(size):
    return D.font("bangers", size)


def caption_groups(words, max_words=4, max_chars=22):
    """words: list of dict(w,s,e). Groups of 3-4 words."""
    groups, cur = [], []
    for w in words:
        cur.append(w)
        txt = " ".join(x["w"] for x in cur)
        if len(cur) >= max_words or len(txt) >= max_chars or w["w"][-1:] in ".!?,;:":
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def caption_image(words, active, width=VW - 120):
    txts = [w["w"].upper().strip("\"") for w in words]
    size = 108
    f = _cap_font(size)
    while size > 50:
        f = _cap_font(size)
        tw = sum(f.getlength(t + " ") for t in txts)
        if tw <= width:
            break
        size -= 6
    sp = f.getlength(" ")
    lines, line, lw = [], [], 0
    for i, t in enumerate(txts):
        l = f.getlength(t)
        if line and lw + l > width:
            lines.append(line)
            line, lw = [], 0
        line.append((i, t, l))
        lw += l + sp
    if line:
        lines.append(line)
    hgt = int(len(lines) * size * 1.05 + 40)
    img = Image.new("RGBA", (VW, hgt), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = 20
    for line in lines:
        tot = sum(l for _, _, l in line) + sp * (len(line) - 1)
        x = (VW - tot) / 2
        for i, t, l in line:
            col = D.YELLOW if i == active else (255, 255, 255)
            d.text((x, y), t, font=f, fill=col, stroke_width=9, stroke_fill=D.INK)
            x += l + sp
        y += size * 1.05
    return img


class VerticalSource:
    def __init__(self, shot, ai_path=None):
        self.shot = shot
        t = S.norm_type(shot.get("type"))
        self.native = t != "map"
        if self.native:
            self.src = ShotSource(shot, VW, PANEL_H, ai_path, seed=len(str(shot)))
        else:
            self.src = ShotSource(shot, 1920, 1080, ai_path, seed=len(str(shot)))

    def frame(self, state, i, n, pop):
        img = self.src.compose(self.src.get(*state), i)
        IW, IH = img.size
        if self.native:
            v, cx, cy = camera(i, n, "in", (.5, .5), 1.0, pop)
            cw, ch = IW / v, IH / v
        else:
            v, cx, cy = camera(i, n, "in", self.src.focus, self.src.zoom_hint, pop)
            ch = IH / v
            cw = ch * VW / PANEL_H
            cx = self.src.focus[0] if S.norm_type(self.shot.get("type")) != "map" else cx
        box = _clamp_box(cx * IW, cy * IH, cw, ch, IW, IH)
        return img.crop(tuple(int(round(c)) for c in box)).resize((VW, PANEL_H), Image.BILINEAR)


def render_vertical_task(task):
    """Worker: one vertical shot segment with captions."""
    out = task["out"]
    stopf = task.get("stopfile")
    n = task["frames"]
    vs = VerticalSource(task["shot"], task.get("ai_path"))
    states = frame_states(task["shot"], n, task.get("env"), task["seed"])
    base = Image.new("RGB", (VW, VH), (255, 255, 255))
    bd = ImageDraw.Draw(base)
    if task.get("brand"):
        bd.text((VW / 2, 120), task["brand"], font=D.font("oswald", 44, "Medium"), fill=(150, 150, 150), anchor="mm")
    groups = task.get("groups") or []
    t0 = task["t0"]
    capcache = {}
    footer = task.get("footer")
    footer_from = task.get("footer_from", 1e9)
    ff = D.font("hand", 54)
    cmd = [ffmpeg_bin(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VW}x{VH}", "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-threads", "2", "-g", "60",
           out + ".tmp.mp4"]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for i in range(n):
            if stopf and i % 30 == 0 and os.path.exists(stopf):
                raise KeyboardInterrupt("stopped")
            t = t0 + i / FPS
            fr = base.copy()
            fr.paste(vs.frame(states[i], i, n, task.get("pop")), (0, PANEL_Y))
            # caption
            gi, wi = None, None
            for k, g in enumerate(groups):
                if g[0]["s"] - 0.05 <= t <= g[-1]["e"] + 0.25:
                    gi = k
                    for j, w in enumerate(g):
                        if w["s"] - 0.05 <= t:
                            wi = j
            if gi is not None and not task.get("no_caps"):
                key = (gi, wi)
                if key not in capcache:
                    capcache[key] = caption_image(groups[gi], wi)
                ci = capcache[key]
                fr.paste(ci, (0, CAP_Y - ci.size[1] // 2), ci)
            if footer and t >= footer_from:
                d = ImageDraw.Draw(fr)
                d.rounded_rectangle([VW / 2 - 330, 1420, VW / 2 + 330, 1505], 40, fill=D.YELLOW, outline=D.INK, width=5)
                d.text((VW / 2, 1462), footer, font=ff, fill=D.INK, anchor="mm")
            p.stdin.write(fr.tobytes())
        p.stdin.close()
        err = p.stderr.read()
        p.wait()
        if p.returncode != 0:
            raise RuntimeError("ffmpeg error: " + err.decode(errors="ignore")[-400:])
        os.replace(out + ".tmp.mp4", out)
    except BaseException:
        try:
            p.stdin.close()
        except Exception:
            pass
        p.kill()
        p.wait()
        raise
    return task["idx"], out


def run_vertical_pool(tasks, progress=None):
    procs = max(1, min(os.cpu_count() or 2, 8))
    res, done = {}, 0
    with Pool(procs) as pool:
        for i, o in pool.imap_unordered(render_vertical_task, tasks, chunksize=1):
            res[i] = o
            done += 1
            if progress:
                progress(done / len(tasks))
    return res
