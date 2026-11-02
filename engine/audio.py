"""Background music + sound effects made in code, mixing and loudness."""
import subprocess, os
from .ff import ffmpeg
import numpy as np

SR = 48000


def _env(n, a, r):
    e = np.ones(n, np.float32)
    na, nr = int(a * SR), int(r * SR)
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def _lp(x, cut):
    a = np.exp(-2 * np.pi * cut / SR)
    y = np.empty_like(x)
    acc = 0.0
    # vectorised one-pole via lfilter-like loop in chunks (numpy only)
    from itertools import accumulate
    b = 1 - a
    y = np.fromiter(accumulate(x * b, lambda p, v: p * a + v), dtype=np.float32, count=len(x))
    return y


def _midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


PROGS = [
    [[48, 55, 59, 64], [45, 52, 55, 60], [41, 48, 52, 57], [43, 50, 55, 59]],   # Cmaj7 Am F G
    [[50, 57, 60, 65], [46, 53, 57, 62], [41, 48, 53, 57], [48, 55, 60, 64]],   # Dm Bb F C
    [[45, 52, 57, 60], [41, 48, 53, 57], [48, 55, 60, 64], [43, 50, 55, 59]],   # Am F C G
]


def _pluck(freq, dur, bright=0.5, seed=0):
    n = int(dur * SR)
    L = max(2, int(SR / freq))
    rng = np.random.default_rng(seed)
    buf = rng.uniform(-1, 1, L).astype(np.float32)
    out = np.empty(n, np.float32)
    idx = 0
    damp = 0.996 - 0.004 * (1 - bright)
    for i in range(n):
        v = buf[idx]
        nxt = buf[(idx + 1) % L]
        buf[idx] = damp * 0.5 * (v + nxt)
        out[i] = v
        idx = (idx + 1) % L
    return out * _env(n, 0.002, 0.2)


def make_music(seconds, seed=1, mood=None):
    """Soft ambient pad + gentle pluck arpeggio. Returns mono float32 at 48k."""
    rng = np.random.default_rng(seed)
    prog = PROGS[(mood if mood is not None else seed) % len(PROGS)]
    bpm = 84
    beat = 60 / bpm
    bar = beat * 4
    loop_n = int(bar * 4 * SR)
    t = np.arange(int(bar * SR)) / SR
    pad = np.zeros(loop_n, np.float32)
    plk = np.zeros(loop_n, np.float32)
    cache = {}
    for bi, chord in enumerate(prog):
        seg = np.zeros(len(t), np.float32)
        for m in chord:
            f = _midi(m + 12)
            for det in (-0.12, 0.12):
                ff = f * 2 ** (det / 12)
                seg += (np.sin(2 * np.pi * ff * t) + 0.25 * np.sin(4 * np.pi * ff * t + 0.3)).astype(np.float32)
        seg *= _env(len(t), 0.9, 0.9) * 0.05
        s0 = int(bi * bar * SR)
        pad[s0:s0 + len(seg)] += seg[:loop_n - s0]
        # arpeggio: 8th notes, sparse
        pattern = [0, 2, 1, 3, 2, 1, 3, 2]
        for k, pi in enumerate(pattern):
            if rng.random() < 0.25:
                continue
            m = chord[pi] + 24
            key = m
            if key not in cache:
                cache[key] = _pluck(_midi(m), beat * 1.6, seed=m)
            note = cache[key] * 0.16
            st = s0 + int(k * beat / 2 * SR)
            en = min(loop_n, st + len(note))
            plk[st:en] += note[:en - st]
    loop = pad + _lp(plk, 3500)
    # soft bass
    for bi, chord in enumerate(prog):
        f = _midi(chord[0] - 12)
        n = int(bar * SR)
        tt = np.arange(n) / SR
        b = np.sin(2 * np.pi * f * tt).astype(np.float32) * _env(n, 0.05, 1.2) * 0.07
        s0 = int(bi * bar * SR)
        loop[s0:s0 + n] += b[:loop_n - s0]
    reps = int(np.ceil(seconds * SR / loop_n)) + 1
    out = np.tile(loop, reps)[:int(seconds * SR)]
    fade = min(len(out) // 4, int(2.5 * SR))
    if fade > 0:
        out[:fade] *= np.linspace(0, 1, fade)
        out[-fade:] *= np.linspace(1, 0, fade)
    return out.astype(np.float32)


def _fit(x, n):
    """Make an array exactly n samples long (cut or pad with zeros/ones-edge)."""
    x = np.asarray(x, dtype=np.float32)
    if len(x) >= n:
        return x[:n]
    return np.concatenate([x, np.full(n - len(x), x[-1] if len(x) else 0, np.float32)])


def sfx(kind):
    if kind == "pop":
        n = int(0.09 * SR)
        t = np.arange(n) / SR
        f = 900 * np.exp(-t * 25) + 250
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 45)
        return (x * 0.35).astype(np.float32)
    if kind == "whoosh":
        n = int(0.35 * SR)
        rng = np.random.default_rng(3)
        x = rng.normal(0, 1, n).astype(np.float32)
        x = _lp(x, 1800) - _lp(x, 300)
        e = np.sin(np.linspace(0, np.pi, n)) ** 2
        return (x * e * 0.25).astype(np.float32)
    if kind == "ding":
        n = int(0.9 * SR)
        t = np.arange(n) / SR
        x = sum(a * np.sin(2 * np.pi * 1320 * r * t) * np.exp(-t * d) for r, a, d in ((1, 1, 5), (2.76, .35, 9), (5.4, .15, 14)))
        return (x * 0.14 * _env(n, 0.003, 0.05)).astype(np.float32)
    if kind == "boing":
        n = int(0.3 * SR)
        t = np.arange(n) / SR
        f = 200 + 300 * np.sin(t * 30) * np.exp(-t * 6)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
        return (x * 0.25).astype(np.float32)
    return np.zeros(10, np.float32)


def resample(x, sr_in, sr_out=SR):
    if sr_in == sr_out:
        return x.astype(np.float32)
    try:
        p = subprocess.run([ffmpeg(), "-v", "error", "-f", "f32le", "-ar", str(sr_in), "-ac", "1", "-i", "pipe:0",
                            "-af", "aresample=resampler=soxr" if _has_soxr() else "anull", "-ar", str(sr_out),
                            "-f", "f32le", "-ac", "1", "pipe:1"], input=x.astype(np.float32).tobytes(), capture_output=True, check=True)
        return np.frombuffer(p.stdout, np.float32).copy()
    except Exception:
        n = int(len(x) * sr_out / sr_in)
        return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


_SOXR = None


def _has_soxr():
    global _SOXR
    if _SOXR is None:
        try:
            out = subprocess.run([ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=24000", "-t", "0.05",
                                  "-af", "aresample=resampler=soxr", "-ar", "48000", "-f", "null", "-"], capture_output=True)
            _SOXR = out.returncode == 0
        except Exception:
            _SOXR = False
    return _SOXR


def lufs(x):
    try:
        import pyloudnorm as pyln
        return pyln.Meter(SR).integrated_loudness(np.stack([x, x], 1).astype(np.float64))
    except Exception:
        rms = np.sqrt(np.mean(x ** 2) + 1e-12)
        return 20 * np.log10(rms) - 0.7


def mix(voice24, events, music_db=-24.0, target_lufs=-14.0, seed=1, music=True):
    """voice24: voice at 24k. events: list of (time_sec, kind). Returns stereo int16 bytes-ready float array (n,2)."""
    v = resample(voice24, 24000, SR)
    n = len(v) + int(1.5 * SR)
    out = np.zeros(n, np.float32)
    out[:len(v)] += v
    vl = lufs(v) if len(v) > SR else -20
    if music:
        m = make_music(n / SR + 0.5, seed=seed)
        m = _fit(m, n)
        ml = lufs(m)
        gain = 10 ** ((vl + music_db - ml) / 20) if np.isfinite(ml) and np.isfinite(vl) else 0.05
        # gentle ducking: slightly louder in long pauses
        env = np.abs(v)
        k = int(0.3 * SR)
        if len(env) > k:
            env = np.convolve(env, np.ones(k) / k, mode="same")
        duck = np.ones(n, np.float32)
        duck[:len(env)] = np.where(env > 0.01, 1.0, 1.6)
        duck = np.convolve(duck, np.ones(int(.4 * SR)) / int(.4 * SR), mode="same").astype(np.float32)
        duck = _fit(duck, n)
        out += m * gain * duck
    sounds = {}
    for t, kind in events:
        if kind not in sounds:
            sounds[kind] = sfx(kind)
        s = sounds[kind] * (10 ** ((vl + 2 - lufs(np.tile(sounds[kind], 8))) / 20) if len(v) > SR else 0.3) * 0.35
        i = int(t * SR)
        if 0 <= i < n:
            e = min(n, i + len(s))
            out[i:e] += s[:e - i]
    cur = lufs(out)
    if np.isfinite(cur):
        out *= 10 ** ((target_lufs - cur) / 20)
    # soft limiter at -1 dBFS
    lim = 10 ** (-1 / 20)
    over = np.abs(out) > lim * 0.9
    if over.any():
        out = np.where(over, np.sign(out) * (lim * 0.9 + (lim * 0.1) * np.tanh((np.abs(out) - lim * 0.9) / (lim * 0.1))), out)
    return np.stack([out, out], 1)


def write_wav(path, stereo):
    import soundfile as sf
    sf.write(path, stereo, SR, subtype="PCM_16")
