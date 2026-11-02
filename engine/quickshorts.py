"""Standalone Quick Shorts: topic -> 2 complete vertical Shorts."""
import os, json, re, time
import numpy as np
from . import script as SC
from . import voice as V
from . import audio as A
from . import render as R
from . import shots as S
from . import prompts
from .pipeline import Progress, slug, safe_write_json, vertical_tasks, OUT, ROOT

SHORTS_DIR = os.path.join(ROOT, "scripts", "shorts")


def validate_pair(data):
    if not isinstance(data, dict) or not isinstance(data.get("shorts"), list) or not data["shorts"]:
        raise SC.ScriptError("Shorts JSON mein 'shorts' list nahi hai.")
    warns = []
    out = []
    for k, sh in enumerate(data["shorts"][:2]):
        shots = [s for s in (sh.get("shots") or []) if isinstance(s, dict) and (s.get("say") or "").strip()]
        if len(shots) < 3:
            warns.append(f"Short {k + 1} mein bohat kam shots hain, chhor diya.")
            continue
        for s in shots:
            s["type"] = S.norm_type(s.get("type"))
            if s["type"] == "big" and not s.get("text"):
                s["text"] = s["say"].upper()
        sh["shots"] = shots
        sh.setdefault("topic", data.get("topic", "Short"))
        sh.setdefault("title", sh["topic"][:48])
        out.append(sh)
    if not out:
        raise SC.ScriptError("Koi bhi Short sahi nahi tha.")
    data["shorts"] = out
    try:
        data["speed"] = min(1.4, max(0.7, float(data.get("speed", 1.05))))
    except Exception:
        data["speed"] = 1.05
    data.setdefault("voice", "am_michael")
    return data, warns


def save_pair(data, topic):
    os.makedirs(SHORTS_DIR, exist_ok=True)
    name = slug(topic, 40) + "-" + time.strftime("%m%d-%H%M%S")
    path = os.path.join(SHORTS_DIR, name + ".json")
    data["topic"] = topic
    safe_write_json(path, data)
    return path


def write_with_gemini(key, topic, voice=None, speed=None, variation=0):
    from . import gemini
    txt = gemini.generate(key, prompts.quick_shorts_prompt(topic, variation), temperature=1.0)
    data = SC.parse_json_text(txt)
    data, warns = validate_pair(data)
    if voice:
        data["voice"] = voice
    if speed:
        data["speed"] = float(speed)
    return save_pair(data, topic), data


def render_one(sh, voice, speed, folder, letter, pr, step, mode, aimap):
    texts = [s["say"].strip() for s in sh["shots"]]
    audio, words = V.narrate(texts, voice, speed, gap=0.16, chunk_gaps=[0.04] * len(texts))
    lead = 0.15
    audio = np.concatenate([np.zeros(int(lead * V.SR), np.float32), audio, np.zeros(int(1.0 * V.SR), np.float32)])
    for w in words:
        w["s"] += lead
        w["e"] += lead
    total = len(audio) / V.SR
    starts = []
    for ci in range(len(texts)):
        ws = [w for w in words if w["chunk"] == ci]
        starts.append(ws[0]["s"] - 0.06 if ws else None)
    shots_t = []
    valid = [(s, st) for s, st in zip(sh["shots"], starts) if st is not None]
    for j, (s, st) in enumerate(valid):
        s0 = 0.0 if j == 0 else st
        s1 = valid[j + 1][1] if j + 1 < len(valid) else total
        shots_t.append((s, s0, s1))
    groups = R.caption_groups(words)
    work = os.path.join(folder, "_work")
    os.makedirs(work, exist_ok=True)
    tasks = vertical_tasks(shots_t, audio, groups, work, f"q{letter}", pr.stop, aimap,
                           footer="Follow for part 2", footer_from=total - 2.0)
    res = R.run_vertical_pool(tasks, progress=lambda f: pr.set(step, f * .9, f"Short {letter}: drawing"))
    ev = [(0.0, "ding")] + [(st, "pop") for (s, st, _) in shots_t[1:] if S.norm_type(s.get("type")) == "big"]
    mixd = A.mix(audio, ev, seed=ord(letter))
    wav = os.path.join(work, f"q{letter}.wav")
    A.write_wav(wav, mixd)
    out = os.path.join(folder, f"short_{letter}.mp4")
    R.concat([res[t["idx"]] for t in tasks], wav, out, work)
    from . import captions as CAP
    CAP.write_srt(words, os.path.join(folder, f"short_{letter}.srt"))
    return out, total


def render_pair(path, mode="A", settings=None, out_name=None, log=print):
    data, warns = validate_pair(SC.read_json(path))
    topic = data.get("topic") or data["shorts"][0].get("topic", "short")
    folder = os.path.join(OUT, out_name or ("shorts-" + slug(os.path.splitext(os.path.basename(path))[0], 60)))
    steps = ["Reading", "Short A", "Short B", "Writing info"][:2 + len(data["shorts"][1:2]) + 1]
    steps = ["Reading"] + [f"Short {'AB'[i]}" for i in range(len(data["shorts"]))] + ["Writing info"]
    pr = Progress(folder, steps)
    try:
        pr.set(0)
        aimap = {}
        if mode == "B":
            try:
                from . import ai_images as AI
                allshots = [s for sh in data["shorts"] for s in sh["shots"]]
                aimap = AI.fetch_for_shots(allshots, data, settings or {}, log, vertical=True)
            except Exception as e:
                log(f"AI pictures skipped: {e}")
        info = []
        for k, sh in enumerate(data["shorts"]):
            letter = "AB"[k]
            pr.set(1 + k, 0, sh.get("topic", ""))
            out, dur = render_one(sh, data["voice"], data["speed"], folder, letter, pr, 1 + k, mode, aimap)
            desc = sh.get("description") or f"{sh.get('topic')} #shorts #funny #life"
            if "#shorts" not in desc:
                desc += " #shorts"
            info.append(dict(file=os.path.basename(out), topic=sh.get("topic"), title=(sh.get("title") or "")[:50],
                             description=desc, pinned=sh.get("pinned", ""), cover=sh.get("cover", ""), seconds=round(dur)))
        pr.set(len(steps) - 1)
        from .seo import SHORTS_TIME
        lines = []
        for i, it in enumerate(info):
            tag = "YOUR TOPIC" if i == 0 else "NEW TOPIC I PICKED"
            lines.append(f"SHORT {'AB'[i]} ({tag}: {it['topic']})  -  {it['file']}, {it['seconds']} sec\n"
                         f"Title: {it['title']}\nDescription: {it['description']}\nPinned comment: {it['pinned']}\n"
                         f"Cover frame: {it['cover']}\n")
        with open(os.path.join(folder, "info.txt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n" + SHORTS_TIME + "\n")
        safe_write_json(os.path.join(folder, "info.json"), info)
        import shutil
        shutil.rmtree(os.path.join(folder, "_work"), ignore_errors=True)
        pr.finish(dict(folder=folder, shorts=info))
        return folder
    except KeyboardInterrupt:
        pr.finish(error="Stopped.")
        raise
    except Exception as e:
        pr.finish(error=str(e))
        raise
