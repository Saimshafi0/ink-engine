"""SRT captions from word timings."""
import re


def fmt(t):
    t = max(0.0, t)
    h, r = divmod(int(t * 1000), 3600000)
    m, r = divmod(r, 60000)
    s, ms = divmod(r, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _lines(words, maxc=42):
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if len(t) > maxc and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def build_cues(words, maxc=42, max_dur=6.0):
    cues, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        txt = [x["w"] for x in cur]
        ln = _lines(txt, maxc)
        end_sent = re.search(r"[.!?][\"')]*$", w["w"]) is not None
        too_long = len(ln) > 2
        if too_long:
            last = cur.pop()
            cues.append(cur)
            cur = [last]
            continue
        nxt_gap = (words[i + 1]["s"] - w["e"]) if i + 1 < len(words) else 9
        if (end_sent and len(" ".join(txt)) > 18) or nxt_gap > 0.7 or (cur[-1]["e"] - cur[0]["s"]) > max_dur:
            cues.append(cur)
            cur = []
    if cur:
        cues.append(cur)
    return cues


def write_srt(words, path, offset=0.0):
    cues = build_cues(words)
    out = []
    for k, c in enumerate(cues):
        s = c[0]["s"] + offset
        e = c[-1]["e"] + offset + 0.15
        if k + 1 < len(cues):
            e = min(e, cues[k + 1][0]["s"] + offset - 0.02)
        e = max(e, s + 0.6)
        text = "\n".join(_lines([x["w"] for x in c]))
        out.append(f"{k + 1}\n{fmt(s)} --> {fmt(e)}\n{text}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    return len(cues)
