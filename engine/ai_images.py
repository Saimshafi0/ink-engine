"""Mode B: AI scene pictures from Cloudflare Workers AI (free 10,000 neurons/day).

UNTESTED WITH A REAL KEY (written carefully; every failure falls back to drawn pictures).
"""
import os, io, json, time, base64, hashlib, uuid, datetime, threading
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from . import net
from . import draw as D

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "cache", "ai")
MAIN = "@cf/black-forest-labs/flux-2-klein-4b"
FALLBACK = "@cf/black-forest-labs/flux-1-schnell"
STYLE = ("Flat 2D cartoon illustration for an educational history video. Muted earthy colours, thin clean black "
         "outlines, simple flat shapes, soft light background, no shading, no gradients. The people are simple stick "
         "figures exactly like the reference image: big round cream-coloured heads with black outline, dot eyes, thin "
         "black line bodies and arms, small round hands. No text, no letters, no words, no watermark, no frame. Scene: ")
MAX_IMAGES = 120
DAILY_LIMIT = 9500          # neurons (free plan gives 10,000; keep a safety margin)
COST_MAIN = 58              # ~ 2 output tiles + reference tile
COST_FALLBACK = 58
QUOTA_MSG = ("Aaj ka free quota khatam, kal dobara Make dabao, banay hue pictures save hain. "
             "(Baqi pictures abhi drawn style mein ban rahi hain.)")


class QuotaHit(Exception):
    pass


def _today():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


_qlock = threading.Lock()


def _quota_file():
    os.makedirs(CACHE, exist_ok=True)
    return os.path.join(CACHE, "quota.json")


def used_today():
    try:
        with open(_quota_file()) as f:
            q = json.load(f)
        return q.get(_today(), 0)
    except Exception:
        return 0


def _spend(n):
    with _qlock:
        try:
            with open(_quota_file()) as f:
                q = json.load(f)
        except Exception:
            q = {}
        q = {_today(): q.get(_today(), 0) + n}
        tmp = _quota_file() + ".tmp"
        with open(tmp, "w") as f:
            json.dump(q, f)
        os.replace(tmp, _quota_file())


def reference_png():
    """Our stick figure on white, 448x448, sent as input_image_0."""
    img = D.new_canvas(448, 448, 2)
    pen = D.Pen(img, 2, seed=5)
    D.draw_person(pen, 224, 420, 380, "wave", "happy", lw=5)
    img = D.finish(img, 448, 448)
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def _multipart(fields, files):
    bnd = "----ink" + uuid.uuid4().hex
    out = io.BytesIO()
    for k, v in fields.items():
        out.write(f"--{bnd}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    for k, (fname, data, ctype) in files.items():
        out.write(f"--{bnd}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fname}\"\r\nContent-Type: {ctype}\r\n\r\n".encode())
        out.write(data)
        out.write(b"\r\n")
    out.write(f"--{bnd}--\r\n".encode())
    return out.getvalue(), f"multipart/form-data; boundary={bnd}"


def _decode(status, headers, body):
    ctype = (headers.get("Content-Type") or headers.get("content-type") or "").lower()
    if status == 200 and ctype.startswith("image/"):
        return Image.open(io.BytesIO(body)).convert("RGB")
    try:
        js = json.loads(body.decode())
    except Exception:
        js = None
    if status == 200 and js is not None:
        r = js.get("result", js)
        b64 = r.get("image") if isinstance(r, dict) else (r if isinstance(r, str) else None)
        if b64:
            if "," in b64[:40]:
                b64 = b64.split(",", 1)[1]
            return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    if status == 200 and body[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1", b"RIFF"):
        return Image.open(io.BytesIO(body)).convert("RGB")
    txt = body[:400].decode(errors="ignore").lower()
    if status == 429 or "4006" in txt or "daily free allocation" in txt or "neurons" in txt and "exceed" in txt:
        raise QuotaHit()
    if status in (401, 403):
        raise PermissionError("Cloudflare token ya Account ID ghalat hai (ya token mein 'Workers AI' permission nahi).")
    raise RuntimeError(f"Cloudflare jawab {status}: {txt[:160]}")


def _gen(account, token, prompt, seed, w, h, ref):
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/"
    auth = {"Authorization": f"Bearer {token}"}
    try:
        fields = {"prompt": STYLE + prompt, "width": str(w), "height": str(h), "seed": str(seed), "guidance": "4"}
        body, ctype = _multipart(fields, {"input_image_0": ("ref.png", ref, "image/png")})
        st, hd, b = net.request(url + MAIN, "POST", dict(auth, **{"Content-Type": ctype}), body, timeout=120, retries=2)
        img = _decode(st, hd, b)
        _spend(COST_MAIN)
        return img
    except (QuotaHit, PermissionError):
        raise
    except Exception:
        pass
    js = json.dumps({"prompt": STYLE + prompt, "steps": 4, "seed": seed}).encode()
    st, hd, b = net.request(url + FALLBACK, "POST", dict(auth, **{"Content-Type": "application/json"}), js, timeout=120, retries=2)
    img = _decode(st, hd, b)
    _spend(COST_FALLBACK)
    return img


def fetch_for_shots(shots, data, settings, log, vertical=False):
    account = (settings.get("cf_account") or "").strip()
    token = (settings.get("cf_token") or "").strip()
    if not account or not token:
        return {}
    os.makedirs(CACHE, exist_ok=True)
    want = {}
    for s in shots:
        if (s.get("type") in ("draw", "scene", "image", "ai")) and (s.get("ai") or "").strip():
            p = s["ai"].strip()
            key = hashlib.sha1(f"{MAIN}|{STYLE}|{p}".encode()).hexdigest()[:20]
            want.setdefault(key, (p, []))[1].append(s)
    keys = list(want)[:MAX_IMAGES]
    ref = reference_png()
    result = {}
    todo = []
    for k in keys:
        path = os.path.join(CACHE, k + ".png")
        if os.path.exists(path):
            for s in want[k][1]:
                result[id(s)] = path
                s["_ai"] = True
        else:
            todo.append(k)
    log(f"AI pictures: {len(keys) - len(todo)} cache se, {len(todo)} nayi banengi (aaj tak use: ~{used_today()} neurons)")
    stop = threading.Event()

    def one(k):
        if stop.is_set():
            return
        if used_today() + COST_MAIN > DAILY_LIMIT:
            stop.set()
            return
        p, ss = want[k]
        seed = int(k[:8], 16) % 1000000
        try:
            img = _gen(account, token, p, seed, 1024, 512, ref)
        except QuotaHit:
            stop.set()
            return
        except PermissionError as e:
            stop.set()
            log("AI ERROR: " + str(e))
            return
        except Exception as e:
            log(f"AI picture fail (drawn picture use hogi): {str(e)[:120]}")
            return
        path = os.path.join(CACHE, k + ".png")
        img.save(path + ".tmp.png")
        os.replace(path + ".tmp.png", path)
        for s in ss:
            result[id(s)] = path
            s["_ai"] = True

    with ThreadPoolExecutor(3) as ex:
        list(ex.map(one, todo))
    if stop.is_set():
        log("NOTE: " + QUOTA_MSG)
    return result


def test_keys(account, token):
    """Cheap check: verify token (no image generated)."""
    try:
        st, js = net.get_json("https://api.cloudflare.com/client/v4/user/tokens/verify",
                              headers={"Authorization": f"Bearer {token}"}, timeout=20, retries=1)
        if st == 200 and js.get("success"):
            return True, "Token theek hai."
        st2, js2 = net.get_json(f"https://api.cloudflare.com/client/v4/accounts/{account}/tokens/verify",
                                headers={"Authorization": f"Bearer {token}"}, timeout=20, retries=1)
        if st2 == 200 and js2.get("success"):
            return True, "Token theek hai."
        return False, "Token sahi nahi laga. Dobara copy karein."
    except Exception as e:
        return False, str(e)
