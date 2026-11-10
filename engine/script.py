"""Load + validate scripts and plan the timing of every shot."""
import json, os, re
from . import draw as D
from . import shots as S
from .voice import split_sentences, word_weight


class ScriptError(Exception):
    pass


def read_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        txt = f.read()
    return parse_json_text(txt)


def parse_json_text(txt):
    txt = (txt or "").strip().lstrip("\ufeff")
    m = re.search(r"```(?:json)?\s*(.*?)```", txt, re.S)
    if m:
        txt = m.group(1).strip()
    if not txt.startswith("{"):
        i = txt.find("{")
        if i >= 0:
            txt = txt[i:txt.rfind("}") + 1]
    txt = re.sub(r",\s*([}\]])", r"\1", txt)  # trailing commas
    tries = [txt,
             # curly quotes INSIDE text (like “honeymoon”) -> plain apostrophes
             txt.replace("\u201c", "'").replace("\u201d", "'").replace("\u2018", "'").replace("\u2019", "'"),
             # whole JSON typed with curly quotes as delimiters
             txt.replace("\u201c", '"').replace("\u201d", '"')]
    err = None
    for t in tries:
        try:
            return json.loads(t)
        except json.JSONDecodeError as e:
            err = err or e
    raise ScriptError(f"JSON theek nahi hai (line {err.lineno}, column {err.colno}): {err.msg}. "
                      "Poora JSON dobara copy karein - shayad aakhri hissa kat gaya. "
                      "Ya ChatGPT ko ye error bata kar theek JSON maangein.")


def validate(data, kind="video"):
    """Returns (clean_data, warnings). Raises ScriptError for fatal problems."""
    warn = []
    if not isinstance(data, dict):
        raise ScriptError("Script ek JSON object { ... } hona chahiye.")
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ScriptError("Script mein 'scenes' list nahi hai (ya khaali hai).")
    data.setdefault("title", "Untitled video")
    data.setdefault("thumbnail_text", " ".join(data["title"].upper().split()[:2]) + "?")
    data.setdefault("voice", "am_michael")
    try:
        data["speed"] = min(1.4, max(0.7, float(data.get("speed", 1.0))))
    except Exception:
        data["speed"] = 1.0
        warn.append("speed number nahi tha, 1.0 rakh diya.")
    clean = []
    for i, sc in enumerate(scenes):
        n = i + 1
        if not isinstance(sc, dict):
            warn.append(f"Scene {n} theek nahi tha, chhor diya.")
            continue
        shots = sc.get("shots") or []
        if not isinstance(shots, list):
            shots = []
        shots = [s for s in shots if isinstance(s, dict)]
        say = (sc.get("say") or "").strip()
        if not say and shots and all((s.get("say") or "").strip() for s in shots):
            say = " ".join(s["say"].strip() for s in shots)
        if not say:
            warn.append(f"Scene {n} mein 'say' (narration) nahi hai, chhor diya.")
            continue
        if not shots:
            shots = [{"type": "me", "pose": "explain", "face": "neutral"}]
            warn.append(f"Scene {n} mein shots nahi the, narrator laga diya.")
        for j, s in enumerate(shots):
            t0 = s.get("type")
            s["type"] = S.norm_type(t0)
            if t0 and S.TYPE_ALIAS.get(str(t0).lower(), str(t0).lower()) not in S.SHOT_TYPES:
                warn.append(f"Scene {n} shot {j + 1}: type '{t0}' samajh nahi aaya, narrator use hoga.")
            for key in ("prop", "think"):
                if s.get(key) and not D.prop_name(s[key]):
                    warn.append(f"Scene {n} shot {j + 1}: prop '{s[key]}' library mein nahi, label box banega.")
            for p in (s.get("props") or []) if isinstance(s.get("props"), list) else []:
                if not D.prop_name(p):
                    warn.append(f"Scene {n} shot {j + 1}: prop '{p}' library mein nahi, label box banega.")
            if s["type"] == "big" and not s.get("text"):
                s["text"] = "..."
                warn.append(f"Scene {n} shot {j + 1}: big text khaali tha.")
        clean.append(dict(sc, say=say, shots=shots, chapter=sc.get("chapter") or f"Part {n}"))
    if not clean:
        raise ScriptError("Koi bhi scene sahi nahi tha. Script dobara banayein.")
    data["scenes"] = clean
    if data.get("more_visuals", True):
        from . import visual as V
        n = V.boost([sc["shots"] for sc in clean], float(data.get("max_narrator", .12)))
        if n:
            warn.append(f"{n} narrator shots ko scenes mein badal diya (zyada visuals).")
    return data, warn


def load(path, kind="video"):
    if not os.path.exists(path):
        raise ScriptError(f"Script file nahi mili: {path}")
    return validate(read_json(path), kind)


def split_say(say, n_shots):
    """Split narration into n parts at word boundaries (prefer punctuation)."""
    words = say.split()
    n = max(1, min(n_shots, len(words)))
    if n == 1:
        return [say]
    ws = [word_weight(w) for w in words]
    tot = sum(ws)
    cum, acc = [], 0
    for w in ws:
        acc += w
        cum.append(acc)
    cuts, last = [], 0
    for k in range(1, n):
        target = tot * k / n
        best, bscore = None, 1e9
        for i in range(last + 1, len(words) - (n - k) + 1):
            d = abs(cum[i - 1] - target)
            if re.search(r"[.!?]$", words[i - 1]):
                d -= tot / n * .35
            elif re.search(r"[,;:—]$", words[i - 1]):
                d -= tot / n * .2
            if d < bscore:
                best, bscore = i, d
        best = best or last + 1
        cuts.append(best)
        last = best
    parts, prev = [], 0
    for c in cuts + [len(words)]:
        parts.append(" ".join(words[prev:c]))
        prev = c
    return parts


def shot_texts(scene):
    shots = scene["shots"]
    if all((s.get("say") or "").strip() for s in shots):
        return [s["say"].strip() for s in shots]
    return split_say(scene["say"], len(shots))


def preview_cut(data, seconds=60):
    """Keep the first scenes up to ~seconds of narration (approx 2.5 words/sec)."""
    out, words = [], 0
    limit = seconds * 2.5
    for sc in data["scenes"]:
        n = len(sc["say"].split())
        if words and words + n > limit * 1.15:
            break
        out.append(sc)
        words += n
        if words >= limit:
            break
    d = dict(data)
    d["scenes"] = out
    return d
