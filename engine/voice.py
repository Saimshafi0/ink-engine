"""Voice: Kokoro (offline) with edge-tts fallback, cached, with word timings."""
import os, re, hashlib, io, json, subprocess, tempfile, threading
import numpy as np
from .textnum import speakable
from .ff import ffmpeg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(ROOT, "models")
CACHE = os.path.join(ROOT, "cache", "voice")
SR = 24000
_K = None
_lock = threading.Lock()

VOICES = {
    "am_michael": "Michael (US, calm, default)",
    "am_puck": "Puck (US, playful)",
    "am_adam": "Adam (US, deep)",
    "am_eric": "Eric (US, clear)",
    "am_liam": "Liam (US, young)",
    "am_onyx": "Onyx (US, low)",
    "am_fenrir": "Fenrir (US, strong)",
    "bm_george": "George (UK, storyteller)",
    "bm_fable": "Fable (UK, warm)",
    "bm_lewis": "Lewis (UK, deep)",
    "af_heart": "Heart (US female, best quality)",
    "af_bella": "Bella (US female, lively)",
    "af_nicole": "Nicole (US female, soft)",
    "bf_emma": "Emma (UK female)",
}
EDGE = {"am_": "en-US-AndrewNeural", "bm_": "en-GB-RyanNeural", "af_": "en-US-AvaNeural", "bf_": "en-GB-SoniaNeural"}


def model_paths():
    for name in ("kokoro-v1.0.onnx", "kokoro-v1.0.int8.onnx"):
        p = os.path.join(MODELS, name)
        if os.path.exists(p) and os.path.getsize(p) > 10_000_000:
            return p, os.path.join(MODELS, "voices-v1.0.bin")
    return None, None


def kokoro():
    global _K
    with _lock:
        if _K is None:
            mp, vp = model_paths()
            if not mp or not os.path.exists(vp):
                raise RuntimeError("Voice model nahi mila (models folder). START.bat dobara chalayein.")
            from kokoro_onnx import Kokoro
            _K = Kokoro(mp, vp)
        return _K


def _edge(text, voice, speed):
    import asyncio
    import edge_tts
    rate = f"{int(round((speed - 1) * 100)):+d}%"
    ev = EDGE.get(voice[:3], "en-US-AndrewNeural")

    async def go():
        out = b""
        async for ch in edge_tts.Communicate(text, ev, rate=rate).stream():
            if ch["type"] == "audio":
                out += ch["data"]
        return out
    mp3 = asyncio.run(go())
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(mp3)
        name = f.name
    try:
        raw = subprocess.run([ffmpeg(), "-v", "error", "-i", name, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                             capture_output=True, check=True).stdout
    finally:
        os.remove(name)
    return np.frombuffer(raw, dtype=np.float32).copy()


def _trim(a, thr=0.008):
    idx = np.where(np.abs(a) > thr)[0]
    if len(idx) == 0:
        return a
    s, e = max(0, idx[0] - int(.02 * SR)), min(len(a), idx[-1] + int(.06 * SR))
    return a[s:e]


def tts(text, voice="am_michael", speed=1.0):
    """Synthesize one sentence. Cached on disk."""
    spoken = speakable(text)
    key = hashlib.sha1(f"{voice}|{speed:.2f}|{spoken}".encode()).hexdigest()[:20]
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, key + ".npy")
    if os.path.exists(path):
        try:
            return np.load(path)
        except Exception:
            pass
    a = None
    try:
        k = kokoro()
        v = voice if voice in k.get_voices() else "am_michael"
        a, sr = k.create(spoken, voice=v, speed=float(speed), lang="en-gb" if v.startswith("b") else "en-us")
        a = np.asarray(a, dtype=np.float32)
    except Exception as e:
        try:
            a = _edge(spoken, voice, speed)
        except Exception as e2:
            raise RuntimeError(f"Awaaz nahi ban saki. Kokoro: {e} | edge-tts: {e2}")
    a = _trim(a)
    tmp = path + ".tmp.npy"
    np.save(tmp, a)
    os.replace(tmp, path)
    return a


# ------------------------------------------------------------------
SENT_RE = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[A-Z0-9\"'(\[])")


def split_sentences(text):
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    parts = [p.strip() for p in SENT_RE.split(text) if p.strip()]
    out = []
    for p in parts:  # very long sentence -> split at ; or : or ,
        while len(p) > 260:
            cut = max(p.rfind(", ", 0, 220), p.rfind("; ", 0, 220), p.rfind(": ", 0, 220))
            if cut < 60:
                cut = p.rfind(" ", 0, 220)
            out.append(p[:cut + 1].strip())
            p = p[cut + 1:].strip()
        out.append(p)
    return out


def word_weight(w):
    s = speakable(w)
    core = re.sub(r"[^A-Za-z0-9]", "", s)
    wt = len(core) * 1.0 + 2.2
    if re.search(r"[,;:]$", w):
        wt += 3.5
    elif re.search(r"[.!?…][\"')]*$", w):
        wt += 3.0
    elif w.endswith("—") or w.endswith("-"):
        wt += 3.0
    return wt


def sentence_words(sent, dur):
    words = sent.split()
    ws = [word_weight(w) for w in words]
    tot = sum(ws) or 1
    t, out = 0.0, []
    for w, wt in zip(words, ws):
        d = dur * wt / tot
        core = d * (0.8 if re.search(r"[,.;:!?]$", w) else 0.95)
        out.append([w, t, t + core])
        t += d
    return out


def _groups(sents, max_chars=190, max_n=3):
    """Join sentences into natural 'breath groups' spoken in one go."""
    out, cur = [], []
    for st in sents:
        if cur and (len(" ".join(cur + [st])) > max_chars or len(cur) >= max_n):
            out.append(cur)
            cur = []
        cur.append(st)
    if cur:
        out.append(cur)
    return out


def _silences(a, min_len=0.12, thr=0.012):
    """Return list of (start, end) seconds of quiet gaps inside audio."""
    hop = int(SR * .01)
    n = len(a) // hop
    if n < 5:
        return []
    env = np.sqrt(np.mean(a[:n * hop].reshape(n, hop) ** 2, axis=1))
    quiet = env < thr
    out, st = [], None
    for k, q in enumerate(quiet):
        if q and st is None:
            st = k
        elif not q and st is not None:
            if (k - st) * .01 >= min_len and st > 0:
                out.append((st * .01, k * .01))
            st = None
    return out


def group_words(sents, a):
    """Word timings for several sentences spoken together, using real pauses
    in the audio to find where each sentence starts."""
    dur = len(a) / SR
    if len(sents) == 1:
        return sentence_words(sents[0], dur)
    lens = [sum(word_weight(w) for w in st.split()) for st in sents]
    tot = sum(lens) or 1
    expect, acc = [], 0
    for L in lens[:-1]:
        acc += L
        expect.append(dur * acc / tot)
    gaps = _silences(a)
    bounds = []
    used = set()
    for e in expect:
        best, bd = None, dur * .18
        for gi, (g0, g1) in enumerate(gaps):
            if gi in used:
                continue
            c = (g0 + g1) / 2
            if abs(c - e) < bd:
                best, bd = gi, abs(c - e)
        if best is not None:
            used.add(best)
            bounds.append(gaps[best])
        else:
            bounds.append((e - .05, e + .05))
    bounds = sorted(bounds)
    out = []
    starts = [0.0] + [b[1] for b in bounds]
    ends = [b[0] for b in bounds] + [dur]
    for st, s0, s1 in zip(sents, starts, ends):
        s1 = max(s1, s0 + .2)
        for w, ws, we in sentence_words(st, s1 - s0):
            out.append([w, s0 + ws, s0 + we])
    return out


def narrate(chunks, voice="am_michael", speed=1.0, gap=0.28, chunk_gaps=None, progress=None, natural=True):
    """chunks: list of texts (one per scene). Returns (audio, words[]) where each
    word = dict(w, s, e, chunk, sent). natural=True speaks 2-3 sentences in one
    breath so the voice flows like a person, not a robot."""
    pieces, words, t = [], [], 0.0
    allg = [(_groups(split_sentences(c)) if natural else [[x] for x in split_sentences(c)]) for c in chunks]
    total = sum(len(g) for g in allg) or 1
    done = 0
    for ci, groups in enumerate(allg):
        for grp in groups:
            text = " ".join(grp)
            try:
                a = tts(text, voice, speed)
                tw = group_words(grp, a)
            except Exception:
                a = np.concatenate([np.concatenate([tts(sg, voice, speed), np.zeros(int(.25 * SR), np.float32)]) for sg in grp])
                tw = group_words(grp, a)
            for w, s_, e_ in tw:
                words.append(dict(w=w, s=t + s_, e=t + e_, chunk=ci, sent=len(pieces)))
            pieces.append(a)
            t += len(a) / SR
            g = gap * (1.25 if text.endswith("?") else 1.0)
            pieces.append(np.zeros(int(g * SR), np.float32))
            t += g
            done += 1
            if progress:
                progress(done / total)
        extra = (chunk_gaps[ci] if chunk_gaps else 0.4)
        pieces.append(np.zeros(int(extra * SR), np.float32))
        t += extra
    audio = np.concatenate(pieces) if pieces else np.zeros(SR, np.float32)
    return audio, words


def sample(voice, speed=1.0, text=None):
    text = text or "Ten thousand years ago, someone invented beer. By accident. Honestly? Best accident in history."
    a = tts(text, voice, speed)
    return a
