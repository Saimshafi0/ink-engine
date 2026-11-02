"""Titles, description, tags, upload settings, shorts info."""
import re

BROAD_TAGS = ["ancient humans", "history documentary", "human evolution", "ancient history", "history explained",
              "stone age", "prehistoric life", "animated history", "history facts", "how people lived"]

PK_TIME = ("Best upload time (USA audience): Thursday, Friday or Saturday.\n"
           "  - November to mid-March (no US daylight saving): 12:00 AM - 2:00 AM Pakistan time\n"
           "    = 2-4 PM New York, 11 AM-1 PM Los Angeles.\n"
           "  - Mid-March to early November: 11:00 PM - 1:00 AM Pakistan time.\n"
           "  Tip: upload as 'Scheduled' 1-2 hours before this time so YouTube finishes HD processing.")

SHORTS_TIME = ("Best Shorts time (USA): 4:00 AM - 6:00 AM Pakistan time (= 6-8 PM New York, Nov-Mar),\n"
               "  or 9:00 PM - 10:00 PM Pakistan time (= 11 AM-12 PM New York). One Short per day is enough.")


def ts(t):
    t = int(t)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def chapters(chs, total):
    """chs: list of (start, name). Merge so each >= 10s and first = 0:00."""
    out = []
    for st, name in chs:
        if out and out[-1][1] == name:
            continue
        out.append([st, name])
    if not out:
        return []
    out[0][0] = 0
    merged = [out[0]]
    for st, name in out[1:]:
        if st - merged[-1][0] < 10:
            continue
        merged.append([st, name])
    if len(merged) > 1 and total - merged[-1][0] < 10:
        merged.pop()
    return merged if len(merged) >= 3 else merged[:1]


def build_description(data, chs, total):
    seo = data.get("seo") or {}
    title = data.get("title", "")
    hook = seo.get("description_hook") or f"{title} The answer is weirder (and funnier) than you think."
    paras = seo.get("paragraphs") or []
    sources = seo.get("sources") or []
    hashtags = seo.get("hashtags") or ["#history", "#ancienthumans", "#documentary"]
    hashtags = [h if h.startswith("#") else "#" + h for h in hashtags][:3]
    parts = [hook.strip(), ""]
    for p in paras[:3]:
        parts += [p.strip(), ""]
    ch = chapters(chs, total)
    if len(ch) >= 3:
        parts.append("Chapters:")
        for st, name in ch:
            parts.append(f"{ts(st)} {name}")
        parts.append("")
    if sources:
        parts.append("Sources:")
        for s in sources[:8]:
            parts.append(f"- {s}")
        parts.append("")
    parts.append(seo.get("subscribe_line") or "New weird-history question every week. Subscribe so you don't miss the next one.")
    parts.append("")
    parts.append(" ".join(hashtags))
    desc = "\n".join(parts)
    while len(desc) > 4500 and paras:
        paras = paras[:-1]
        return build_description(dict(data, seo=dict(seo, paragraphs=paras)), chs, total)
    return desc[:4500]


def build_tags(data):
    seo = data.get("seo") or {}
    tags = list(seo.get("tags") or [])
    for t in BROAD_TAGS:
        if len(tags) >= 20:
            break
        if t not in tags:
            tags.append(t)
    out, total = [], 0
    for t in tags:
        t = re.sub(r"[<>,]", "", str(t)).strip()
        if not t or t.lower() in (x.lower() for x in out):
            continue
        if total + len(t) + 2 > 490:
            break
        out.append(t)
        total += len(t) + 2
    return out


def titles(data):
    seo = data.get("seo") or {}
    ts_ = list(seo.get("titles") or [])
    if data.get("title") and data["title"] not in ts_:
        ts_.insert(0, data["title"])
    best = seo.get("best_title") or (ts_[0] if ts_ else data.get("title", ""))
    lines = []
    for t in ts_[:5]:
        mark = "  <-- BEST" if t == best else ""
        warn = "  (too long!)" if len(t) > 60 else ""
        lines.append(f"{t}  [{len(t)} chars]{mark}{warn}")
    return best, "\n".join(lines)


def upload_settings(data, mode="A"):
    seo = data.get("seo") or {}
    return f"""UPLOAD SETTINGS - {data.get('title')}
==========================================
Title: {titles(data)[0]}
Category: Education
Audience: "No, it's not made for kids"
Language: English (United States)   |   Caption language: English
Subtitles: upload captions.srt  (Subtitles > Upload file > With timing)
Thumbnail: thumbnail.jpg  (then Test & Compare: thumbnail_B.jpg, thumbnail_C.jpg)
Altered or synthetic content: "No"
   (Reason: cartoon drawings, nothing realistic, no real person made to say
    anything. AI narration voice alone does not need this label.
    {'AI-made cartoon scenes are also clearly not realistic.' if mode == 'B' else ''})
Paid promotion: No   |   Allow embedding: Yes   |   Publish to subscriptions feed: Yes
License: Standard YouTube License
Comments: On. Pin this comment:
   {seo.get('pinned_comment') or 'Which ancient habit would YOU survive the longest? Tell me below.'}
End screen: "Best for viewer" video + Subscribe, last 15 seconds.
Playlist: "Ancient Humans Explained"

{PK_TIME}

HONEST NOTE: YouTube does not pay channels that look mass-produced. Every video
must have its own research, jokes and a real story. Never upload two very similar
videos the same week.
"""
