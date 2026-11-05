"""More pictures, less talking head.

Turns runs of narrator ("me") shots into real scenes: the stick figure is put into a
background with the props the line talks about. Keeps the hook (first shot) and big text.
"""
import re
from . import draw as D

BG_WORDS = [
    (r"\b(rome|roman|athens|athenian|greek|greece|forum|senate|pompeii|sparta\w*|temple|toga)\b", "ancient"),
    (r"\b(city|street|capital|palace|venice)\b", "city"),
    (r"\b(market|shop|sell|buy|trade|agora)\b", "market"),
    (r"\b(village|farm|farmer|town|home|house)\b", "village"),
    (r"\b(night|dark|midnight|sleep)\b", "night"),
    (r"\b(sea|ship|boat|ocean|island|iceland|viking)\b", "sea"),
    (r"\b(river|nile|bridge)\b", "river"),
    (r"\b(desert|egypt|sand|mesopotamia|sumer|iraq)\b", "desert"),
    (r"\b(snow|winter|ice|cold)\b", "snow"),
    (r"\b(cave|stone age|caveman)\b", "cave"),
    (r"\b(jungle|forest|tree)\b", "jungle"),
    (r"\b(mountain|hill)\b", "mountains"),
    (r"\b(lab|scientist|research|study|archaeolog)\w*", "lab"),
    (r"\b(field|grass|outside|outdoor|crowd|assembly|meeting)\b", "grass"),
]

EXTRA_PROPS = [
    (r"\bvot\w*|ballot|elect\w*", "ballot_box"), (r"shard|pottery|ostra", "ostrakon"), (r"\bkey\b|locked", "key"),
    (r"\bhand(s)?\b|raise", "hand"), (r"lottery|random", "vote_balls"), (r"shout|scream|loud", "speech"),
    (r"exile|banish|kick\w* out", "boat"), (r"bribe|bought|money|paid|pay\b", "coin"),
]


def guess_bg(text, fallback="grass"):
    t = (text or "").lower()
    for rx, bg in BG_WORDS:
        if re.search(rx, t):
            return bg
    return fallback


def guess_props(text, limit=2):
    from .thumb import KEYWORD_PROPS
    t = (text or "").lower()
    out = []
    for rx, prop in EXTRA_PROPS + KEYWORD_PROPS:
        if re.search(rx, t) and prop not in out and D.prop_name(prop):
            out.append(prop)
        if len(out) >= limit:
            break
    return out


def _scene_bg(shots):
    for s in shots:
        if s.get("type") in ("draw", "crowd") and s.get("bg") and D.norm_bg(s["bg"]) != "white":
            return s["bg"]
    return None


def to_scene(s, bg):
    """Make a 'me' shot into a 'draw' shot with a background and props."""
    say = s.get("say") or ""
    text = s.get("text") or ""
    prop = s.get("prop")
    extra = [p for p in guess_props(say + " " + text) if p != prop]
    mark = s.get("cross") or s.get("tick")
    person = {"pose": s.get("pose", "explain"), "face": s.get("face", "neutral")}
    for k in ("hat", "beard", "wear"):
        if s.get(k):
            person[k] = s[k]
    props = []
    if prop and (mark or D.prop_name(prop) in getattr(D, "ANIMALS", ())):
        props.append(prop)
    elif prop:
        person["hold"] = prop
    props += extra[:2 - len(props)] if len(props) < 2 else []
    if not prop and not props:
        return None  # nothing to show, keep the narrator
    out = {"type": "draw", "bg": bg or guess_bg(say + " " + text), "people": [person], "props": props[:2],
           "say": s.get("say"), "auto_visual": True}
    if text:
        out["text"] = text
    if s.get("cross"):
        out["cross"] = True
    elif s.get("tick"):
        out["tick"] = True
    for k in ("chapter", "seed"):
        if k in s:
            out[k] = s[k]
    return out


def boost(scenes_shots, max_me=0.3):
    """scenes_shots: list of shot lists (one per scene). Changes them in place. Returns count converted."""
    total = sum(len(x) for x in scenes_shots)
    if not total:
        return 0
    changed = 0
    first = True
    # pass 1: never two narrator shots in a row
    for shots in scenes_shots:
        bg = _scene_bg(shots)
        run = 0
        for i, s in enumerate(shots):
            if first:
                first = False
                run = 1 if s.get("type") == "me" else 0
                continue
            if s.get("type") == "me" and not s.get("keep"):
                run += 1
                if run >= 2:
                    new = to_scene(s, bg)
                    if new:
                        shots[i] = new
                        changed += 1
                        run = 0
            else:
                run = 0
    # pass 2: still too much narrator? convert every other remaining one that has something to show
    def ratio():
        return sum(1 for sh in scenes_shots for s in sh if s.get("type") == "me") / total
    flip = False
    for shots in scenes_shots:
        bg = _scene_bg(shots)
        for i, s in enumerate(shots):
            if ratio() <= max_me:
                return changed
            if s.get("type") == "me" and not s.get("keep") and (scenes_shots[0] is not shots or i):
                flip = not flip
                if flip:
                    new = to_scene(s, bg)
                    if new:
                        shots[i] = new
                        changed += 1
    return changed
