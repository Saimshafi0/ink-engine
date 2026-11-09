"""High level: script -> finished video folder (video, captions, thumbnails, SEO, shorts)."""
import os, json, time, re, shutil, random, hashlib, traceback
import numpy as np
from . import script as SC
from . import voice as V
from . import audio as A
from . import render as R
from . import shots as S
from . import thumb as T
from . import seo as SEO
from . import captions as CAP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")


def safe_write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def slug(s, n=50):
    s = re.sub(r"[^A-Za-z0-9]+", "-", s or "video").strip("-").lower()
    return s[:n].strip("-") or "video"


class Progress:
    def __init__(self, folder, steps):
        self.folder = folder
        self.steps = steps
        self.t0 = time.time()
        self.cur = 0
        os.makedirs(folder, exist_ok=True)
        self.path = os.path.join(folder, "status.json")
        self.stop = os.path.join(folder, "STOP")
        if os.path.exists(self.stop):
            os.remove(self.stop)

    def set(self, i, frac=0.0, msg=""):
        self.cur = i
        tot = len(self.steps)
        pct = int(100 * (i + max(0.0, min(1.0, frac))) / tot)
        st = dict(step=self.steps[i], step_no=i + 1, steps=tot, pct=pct, msg=msg,
                  elapsed=int(time.time() - self.t0), done=False, error=None)
        safe_write_json(self.path, st)
        print(f"@@PROGRESS {pct}% | {self.steps[i]} {msg}", flush=True)
        if os.path.exists(self.stop):
            raise KeyboardInterrupt("Stopped by user")

    def finish(self, extra=None, error=None):
        st = dict(step="Done" if not error else "Error", pct=100 if not error else 0, done=True, error=error,
                  elapsed=int(time.time() - self.t0))
        if extra:
            st.update(extra)
        safe_write_json(self.path, st)


# ---------------------------------------------------------------------
def plan_timeline(data, words):
    """Assign start/end to every shot from word timings. Returns flat shot list."""
    flat = []
    for ci, sc in enumerate(data["scenes"]):
        texts = SC.shot_texts(sc)
        cw = [w for w in words if w["chunk"] == ci]
        idx = 0
        for k, (shot, txt) in enumerate(zip(sc["shots"], texts)):
            n = len(txt.split())
            ws = cw[idx: idx + n]
            idx += n
            if not ws:
                continue
            flat.append(dict(shot=shot, scene=ci, chapter=sc["chapter"], words=ws, start=ws[0]["s"], text=txt))
    for i, f in enumerate(flat):
        f["start"] = 0.0 if i == 0 else max(0.0, f["start"] - 0.1)
    return flat


def assign_ends(flat, total):
    for i, f in enumerate(flat):
        f["end"] = flat[i + 1]["start"] if i + 1 < len(flat) else total
    # frame-exact boundaries
    for f in flat:
        f["f0"] = int(round(f["start"] * R.FPS))
        f["f1"] = int(round(f["end"] * R.FPS))
    for i in range(len(flat) - 1):
        flat[i]["f1"] = flat[i + 1]["f0"]
    return [f for f in flat if f["f1"] > f["f0"]]


def split_long(flat, max_len=5.5):
    """Very long shots get a second 'camera' segment so the picture never sits still too long."""
    out = []
    for f in flat:
        n = f["f1"] - f["f0"]
        if n > max_len * R.FPS:
            parts = int(np.ceil(n / (4.0 * R.FPS)))
            step = n // parts
            for p in range(parts):
                g = dict(f)
                g["f0"] = f["f0"] + p * step
                g["f1"] = f["f0"] + (p + 1) * step if p < parts - 1 else f["f1"]
                g["part"] = p
                out.append(g)
        else:
            f["part"] = 0
            out.append(f)
    return out


def sfx_events(flat):
    ev = []
    prev_t, prev_scene = None, -1
    for f in flat:
        if f.get("part"):
            continue
        t = f["f0"] / R.FPS
        typ = S.norm_type(f["shot"].get("type"))
        if f["scene"] != prev_scene and f["scene"] > 0:
            ev.append((max(0, t - 0.15), "whoosh"))
        elif typ == "big":
            ev.append((t, "ding"))
        elif typ == "me" and (prev_t is None or prev_t != "me"):
            ev.append((t, "pop"))
        prev_t, prev_scene = typ, f["scene"]
    return ev


def camera_style(i, f):
    """Phase 3: more energetic, varied camera per shot type."""
    typ = S.norm_type(f["shot"].get("type"))
    if typ == "big":
        return "in", True
    if typ == "map":
        return "in", False
    if typ == "compare" or typ == "diagram":
        return ("in" if i % 2 == 0 else "out"), True
    if f.get("part"):
        return ("pan" if i % 2 else "out"), False
    if typ == "me":
        return ("in" if i % 2 == 0 else "out"), True
    if typ in ("draw", "crowd"):
        return ("in", "out", "pan")[i % 3], (i % 3 == 0)
    return ("in", "out", "pan")[i % 3], (i % 3 == 0)


def ai_paths(flat, data, mode, settings, log):
    """Mode B: get AI images for draw shots (cached). Returns {id(shot): path}."""
    if mode != "B":
        return {}
    try:
        from . import ai_images as AI
    except Exception as e:
        log(f"AI module error: {e}")
        return {}
    return AI.fetch_for_shots([f["shot"] for f in flat if not f.get("part")], data, settings, log)


# ---------------------------------------------------------------------
def make_video(script_path, preview=False, mode="A", settings=None, out_name=None, shorts=True, log=print):
    settings = settings or {}
    steps = ["Reading script", "Making the voice", "Planning shots", "AI pictures" if mode == "B" else "Preparing pictures",
             "Drawing video frames", "Mixing music + sound", "Joining video", "Captions + thumbnails + SEO"]
    if shorts and not preview:
        steps.append("Making Shorts")
    data, warns = SC.load(script_path)
    name = out_name or (slug(os.path.splitext(os.path.basename(script_path))[0]) + ("-test" if preview else ""))
    folder = os.path.join(OUT, name)
    os.makedirs(folder, exist_ok=True)
    pr = Progress(folder, steps)
    try:
        pr.set(0, 0, f"{len(data['scenes'])} scenes")
        for w in warns:
            log("NOTE: " + w)
        if preview:
            data = SC.preview_cut(data, 60)
        voice, speed = data.get("voice", "am_michael"), data.get("speed", 1.0)
        pr.set(1, 0)
        audio, words = V.narrate([sc["say"] for sc in data["scenes"]], voice, speed,
                                 progress=lambda f: pr.set(1, f, f"{int(f * 100)}%"))
        total = len(audio) / V.SR
        pr.set(2, 0, f"{total / 60:.1f} min")
        flat = plan_timeline(data, words)
        flat = assign_ends(flat, total)
        flat = split_long(flat)
        pr.set(3, 0)
        aimap = ai_paths(flat, data, mode, settings, log)
        work = os.path.join(folder, "_work")
        os.makedirs(work, exist_ok=True)
        tasks = []
        for i, f in enumerate(flat):
            n = f["f1"] - f["f0"]
            cam, pop = camera_style(i, f)
            key = hashlib.sha1((json.dumps(f["shot"], sort_keys=True) + f"{n}{cam}{pop}{f['f0']}").encode()).hexdigest()[:10]
            tasks.append(dict(idx=i, shot=f["shot"], frames=n, W=1920, H=1080, seed=i * 7 + 1, cam=cam, pop=pop,
                              env=R.mouth_envelope(audio, f["f0"] / R.FPS, n), out=os.path.join(work, f"seg_{i:04d}_{key}.mp4"),
                              reuse=True, stopfile=pr.stop, ai_path=aimap.get(id(f["shot"]))))
        pr.set(4, 0, f"{len(tasks)} shots")
        res = R.run_pool(tasks, progress=lambda fr: pr.set(4, fr, f"{int(fr * len(tasks))}/{len(tasks)} shots"))
        segs = [res[i] for i in range(len(tasks))]
        pr.set(5, 0)
        mixd = A.mix(audio, sfx_events(flat), seed=abs(hash(data.get("title", ""))) % 3)
        wav = os.path.join(work, "audio.wav")
        A.write_wav(wav, mixd)
        pr.set(6, 0)
        mp4 = os.path.join(folder, "video.mp4")
        R.concat(segs, wav, mp4, work)
        pr.set(7, 0)
        CAP.write_srt(words, os.path.join(folder, "captions.srt"))
        tspecs = make_thumbs(data, folder, aimap, flat)
        seo_ = data.setdefault("seo", {})
        paired = [t["title"] for t in tspecs if t.get("title")]
        if paired:
            seo_["best_title"] = paired[0]
            seo_["titles"] = paired + [t for t in (seo_.get("titles") or []) if t not in paired]
        chs = [(f["start"], f["chapter"]) for f in flat if not f.get("part")]
        best, tlist = SEO.titles(data)
        with open(os.path.join(folder, "title.txt"), "w", encoding="utf-8") as fh:
            fh.write(best + "\n\nOther options:\n" + tlist + "\n")
        with open(os.path.join(folder, "description.txt"), "w", encoding="utf-8") as fh:
            fh.write(SEO.build_description(data, chs, total))
        with open(os.path.join(folder, "tags.txt"), "w", encoding="utf-8") as fh:
            fh.write(", ".join(SEO.build_tags(data)))
        with open(os.path.join(folder, "upload-settings.txt"), "w", encoding="utf-8") as fh:
            fh.write(SEO.upload_settings(data, mode))
        meta = dict(title=best, duration=round(total, 1), shots=len(flat), preview=preview, mode=mode)
        if shorts and not preview:
            pr.set(8, 0)
            try:
                make_shorts_from_video(data, flat, audio, words, folder, aimap, pr, 8)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                traceback.print_exc()
                log(f"NOTE: Shorts nahi ban sake ({e}). Lambi video, thumbnails aur SEO tayyar hain.")
                meta["shorts_error"] = str(e)
        shutil.rmtree(work, ignore_errors=True)
        safe_write_json(os.path.join(folder, "meta.json"), meta)
        pr.finish(dict(folder=folder, **meta))
        log(f"DONE: {folder}")
        return folder
    except KeyboardInterrupt:
        pr.finish(error="Stopped (aap ne Stop dabaya).")
        raise
    except Exception as e:
        pr.finish(error=f"{e}")
        traceback.print_exc()
        raise


def make_thumbs(data, folder, aimap=None, flat=None):
    """3 click-worthy thumbnails, each paired with its own title."""
    given = [t for t in (data.get("thumbnails") or []) if isinstance(t, dict)]
    auto = T.auto_specs(data)
    specs = []
    for k in range(3):
        sp = dict(auto[k])
        if k < len(given):
            g = dict(given[k])
            # old style entries only had text/face/pose/bg/props/mark: keep auto extras unless given
            sp = dict(g) if any(x in g for x in ("hero", "color", "hold", "above", "sidekick", "arrow")) else dict(sp, **g)
        specs.append(sp)
    seo = data.get("seo") or {}
    titles = [t for t in (seo.get("titles") or []) if t]
    lines = []
    for k, (letter, sp) in enumerate(zip("ABC", specs)):
        try:
            img = T.make_pro(sp, k)
        except Exception as e:
            print(f"NOTE: thumbnail {letter} simple style mein bana ({e})")
            img = T.make_pro(T.auto_specs(data)[k], k)
        name = "thumbnail.jpg" if letter == "A" else f"thumbnail_{letter}.jpg"
        img.save(os.path.join(folder, name), quality=93)
        T.phone_preview(img).save(os.path.join(folder, f"thumbnail_{letter}_phone.png"))
        title = sp.get("title") or (titles[k] if k < len(titles) else data.get("title", ""))
        sp["title"] = title
        lines.append(f"{letter}: {name}\n   Thumbnail text: {sp.get('text')}\n   Title: {title}  [{len(title)} chars]")
    best = specs[0].get("title") or data.get("title", "")
    with open(os.path.join(folder, "thumbnails.txt"), "w", encoding="utf-8") as fh:
        fh.write("THUMBNAILS + TITLES (YouTube Studio > Test & Compare)\n"
                 "=====================================================\n\n" + "\n\n".join(lines) +
                 f"\n\nAgar sirf thumbnails test ho sakte hain: title rakhein -> {best}\n"
                 "Test 2-3 din chalne dein, beech mein kuch na badlein.\n")
    return specs


# ---------------------------------------------------------------------
def pick_short_ranges(data, flat, total, n=4):
    """Pick up to n ranges of shots (30-55 s) with the most surprising content."""
    custom = data.get("shorts") or []
    ranges = []
    scenes = sorted(set(f["scene"] for f in flat))
    if custom:
        for c in custom[:n]:
            sc = c.get("scenes") or ([c["scene"]] if "scene" in c else [])
            sc = [s - 1 if isinstance(s, int) and s >= 1 else s for s in sc]
            fl = [i for i, f in enumerate(flat) if f["scene"] in sc]
            if fl:
                ranges.append((fl, c))
    if len(ranges) < n:
        cand = []
        for s in scenes:
            fl = [i for i, f in enumerate(flat) if f["scene"] == s]
            txt = " ".join(flat[i]["text"] for i in fl if not flat[i].get("part"))
            score = len(re.findall(r"\d", txt)) * .3 + txt.count("!") + txt.count("?") * .7 + sum(
                1 for i in fl if S.norm_type(flat[i]["shot"].get("type")) == "big") * 2
            cand.append((score, s, fl))
        cand.sort(reverse=True)
        used = {tuple(r[0]) for r in ranges}
        for score, s, fl in cand:
            if len(ranges) >= n:
                break
            if tuple(fl) in used:
                continue
            ranges.append((fl, {}))
    out = []
    for fl, c in ranges:
        # trim to <= 55 s, extend if < 25 s by adding next shots
        start = flat[fl[0]]["f0"] / R.FPS
        keep = [i for i in fl if flat[i]["f1"] / R.FPS - start <= 54]
        if not keep:
            keep = fl[:1]
        j = keep[-1] + 1
        scenes_ok = {flat[i]["scene"] for i in fl}
        while flat[keep[-1]]["f1"] / R.FPS - start < 28 and j < len(flat) and flat[j]["scene"] in scenes_ok:
            if flat[j]["f1"] / R.FPS - start > 54:
                break
            keep.append(j)
            j += 1
        out.append((keep, c))
    return out[:n]


def make_shorts_from_video(data, flat, audio, words, folder, aimap, pr, step):
    sdir = os.path.join(folder, "shorts")
    os.makedirs(sdir, exist_ok=True)
    work = os.path.join(folder, "_work", "shorts")
    os.makedirs(work, exist_ok=True)
    picks = pick_short_ranges(data, flat, len(audio) / V.SR)
    info_lines = []
    tasks_all = []
    jobs = []
    for k, (idxs, c) in enumerate(picks):
        t_start = flat[idxs[0]]["f0"] / R.FPS
        t_end = flat[idxs[-1]]["f1"] / R.FPS
        hook = c.get("hook") or _auto_hook(flat, idxs)
        hook_dur = 1.0
        a0, a1 = int(t_start * V.SR), int(t_end * V.SR)
        seg_audio = np.concatenate([np.zeros(int(hook_dur * V.SR), np.float32), audio[a0:a1], np.zeros(int(1.2 * V.SR), np.float32)])
        sw = [dict(w, s=w["s"] - t_start + hook_dur, e=w["e"] - t_start + hook_dur) for w in words if t_start <= w["s"] < t_end]
        groups = R.caption_groups(sw)
        total = len(seg_audio) / V.SR
        shots_t = [(dict(type="big", text=hook), 0.0, hook_dur)]
        for i in idxs:
            f = flat[i]
            shots_t.append((f["shot"], f["f0"] / R.FPS - t_start + hook_dur, f["f1"] / R.FPS - t_start + hook_dur))
        shots_t[-1] = (shots_t[-1][0], shots_t[-1][1], total)
        tasks = vertical_tasks(shots_t, seg_audio, groups, work, f"s{k}", pr.stop, aimap,
                               footer="Full video on the channel", footer_from=total - 2.2)
        jobs.append((k, c, hook, seg_audio, tasks, sw, total))
        tasks_all += tasks
    res = R.run_vertical_pool(tasks_all, progress=lambda fr: pr.set(step, fr * .9, "drawing Shorts"))
    seo = data.get("seo") or {}
    for k, c, hook, seg_audio, tasks, sw, total in jobs:
        ev = [(0.0, "ding")]
        mixd = A.mix(seg_audio, ev, seed=k)
        wav = os.path.join(work, f"s{k}.wav")
        A.write_wav(wav, mixd)
        segs = [res[t["idx"]] for t in tasks]
        R.concat(segs, wav, os.path.join(sdir, f"short_{k + 1}.mp4"), work)
        title = c.get("title") or (hook.title()[:46] + " #shorts")
        desc = c.get("description") or f"{hook} Full story on the channel."
        tags = c.get("hashtags") or ["#shorts", "#history", "#ancienthumans"]
        info_lines.append(f"SHORT {k + 1}  (short_{k + 1}.mp4, {total:.0f} sec)\nTitle: {title[:50]}\nDescription: {desc}\n"
                          f"{' '.join(tags)}\nPinned comment: {c.get('pinned') or seo.get('pinned_comment') or 'Would you survive this? Yes or no?'}\n")
    with open(os.path.join(sdir, "shorts.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(info_lines) + "\n" + SEO.SHORTS_TIME + "\n")


def _auto_hook(flat, idxs):
    for i in idxs:
        s = flat[i]["shot"]
        if S.norm_type(s.get("type")) == "big" and s.get("text"):
            return s["text"]
    t = flat[idxs[0]]["text"]
    q = re.findall(r"[^.?!]*\?", " ".join(flat[i]["text"] for i in idxs))
    if q:
        t = q[0]
    words = t.split()
    return " ".join(words[:6]).upper().rstrip(",.") + ("?" if not t.strip().endswith("?") else "")


_vt_counter = [0]


def vertical_tasks(shots_t, seg_audio, groups, work, tag, stopfile, aimap, footer=None, footer_from=1e9, brand=None):
    tasks = []
    for j, (shot, s0, s1) in enumerate(shots_t):
        f0, f1 = int(round(s0 * R.FPS)), int(round(s1 * R.FPS))
        if f1 <= f0:
            continue
        _vt_counter[0] += 1
        tasks.append(dict(idx=_vt_counter[0], shot=shot, frames=f1 - f0, t0=f0 / R.FPS, seed=j * 5 + 2,
                          env=R.mouth_envelope(seg_audio, f0 / R.FPS, f1 - f0), groups=groups, pop=(j % 2 == 0),
                          out=os.path.join(work, f"{tag}_{j:03d}.mp4"), stopfile=stopfile, ai_path=aimap.get(id(shot)),
                          footer=footer, footer_from=footer_from, brand=brand))
    # fix contiguous frames: recompute so segments don't drop frames
    return tasks
