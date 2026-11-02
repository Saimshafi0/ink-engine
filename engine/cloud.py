"""Cloud mode: make videos on GitHub's free computers (GitHub Actions)."""
import os, json, time, base64, hashlib, zipfile, io, shutil, uuid
from . import net

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.github.com"
REPO = "ink-engine"
WORKFLOW = "make-ink.yml"
UPLOAD_DIRS = ["engine", "assets", "scripts", ".github"]
UPLOAD_FILES = ["make.py", "requirements.txt"]
NEVER = ("settings.json", ".tmp", "__pycache__", ".pyc", "status.json")


class CloudError(Exception):
    pass


def _h(token):
    return {"Authorization": f"token {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def _req(token, method, path, body=None, ok=(200, 201, 204), timeout=60):
    url = path if path.startswith("http") else API + path
    if body is not None:
        st, js = net.send_json(url, body, method=method, headers=_h(token), timeout=timeout)
    else:
        st, js = net.get_json(url, headers=_h(token), timeout=timeout) if method == "GET" else \
            (lambda r: (r[0], json.loads(r[2].decode() or "{}") if r[2] else {}))(net.request(url, method, _h(token), None, timeout))
    if st not in ok:
        msg = js.get("message", "") if isinstance(js, dict) else ""
        if st == 401:
            raise CloudError("GitHub token ghalat ya expire ho gaya. Settings mein naya token daalein.")
        if st == 403 and "rate limit" in msg.lower():
            raise CloudError("GitHub ne thori der ke liye rok diya (rate limit). 15 minute baad dobara.")
        raise CloudError(f"GitHub {method} {path.split('?')[0]} -> {st}: {msg[:160]}")
    return st, js


def whoami(token):
    st, js = _req(token, "GET", "/user")
    return js["login"]


def check_scopes(token):
    st, h, b = net.request(API + "/user", headers=_h(token), timeout=20)
    if st != 200:
        return False, "Token kaam nahi kar raha."
    scopes = (h.get("X-OAuth-Scopes") or h.get("x-oauth-scopes") or "")
    if scopes and not ("repo" in scopes and "workflow" in scopes):
        return False, f"Token mein 'repo' aur 'workflow' dono tick hone chahiye (abhi: {scopes})."
    return True, json.loads(b.decode()).get("login")


def ensure_repo(token, login):
    st, js = net.get_json(f"{API}/repos/{login}/{REPO}", headers=_h(token))
    if st == 200:
        return js.get("default_branch", "main")
    _req(token, "POST", "/user/repos", {"name": REPO, "private": False, "auto_init": True,
                                         "description": "Ink Engine - stick figure history videos (made by the app)"})
    for _ in range(10):
        time.sleep(2)
        st, js = net.get_json(f"{API}/repos/{login}/{REPO}", headers=_h(token))
        if st == 200 and js.get("default_branch"):
            return js["default_branch"]
    return "main"


def blob_sha(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def local_files():
    out = {}
    for d in UPLOAD_DIRS:
        base = os.path.join(ROOT, d)
        for dp, dn, fn in os.walk(base):
            dn[:] = [x for x in dn if x != "__pycache__"]
            for f in fn:
                if any(n in f for n in NEVER):
                    continue
                p = os.path.join(dp, f)
                out[os.path.relpath(p, ROOT).replace("\\", "/")] = p
    for f in UPLOAD_FILES:
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            out[f] = p
    return out


def sync(token, login, branch, log=print):
    """Upload only changed files in ONE commit."""
    st, ref = _req(token, "GET", f"/repos/{login}/{REPO}/git/ref/heads/{branch}")
    head = ref["object"]["sha"]
    st, commit = _req(token, "GET", f"/repos/{login}/{REPO}/git/commits/{head}")
    st, tree = _req(token, "GET", f"/repos/{login}/{REPO}/git/trees/{commit['tree']['sha']}?recursive=1")
    remote = {t["path"]: t["sha"] for t in tree.get("tree", []) if t["type"] == "blob"}
    changes = []
    for rel, p in local_files().items():
        with open(p, "rb") as f:
            data = f.read()
        if remote.get(rel) != blob_sha(data):
            changes.append((rel, data))
    if not changes:
        log("Cloud: sab files pehle se upload hain.")
        return head
    log(f"Cloud: {len(changes)} files upload ho rahi hain...")
    items = []
    for rel, data in changes:
        st, b = _req(token, "POST", f"/repos/{login}/{REPO}/git/blobs",
                     {"content": base64.b64encode(data).decode(), "encoding": "base64"}, timeout=180)
        items.append({"path": rel, "mode": "100644", "type": "blob", "sha": b["sha"]})
    st, nt = _req(token, "POST", f"/repos/{login}/{REPO}/git/trees", {"base_tree": commit["tree"]["sha"], "tree": items})
    st, nc = _req(token, "POST", f"/repos/{login}/{REPO}/git/commits",
                  {"message": f"InkEngine update ({len(changes)} files)", "tree": nt["sha"], "parents": [head]})
    _req(token, "PATCH", f"/repos/{login}/{REPO}/git/refs/heads/{branch}", {"sha": nc["sha"]})
    return nc["sha"]


def set_secret(token, login, name, value):
    from nacl import encoding, public
    st, key = _req(token, "GET", f"/repos/{login}/{REPO}/actions/secrets/public-key")
    pk = public.PublicKey(key["key"].encode(), encoding.Base64Encoder())
    sealed = public.SealedBox(pk).encrypt(value.encode())
    _req(token, "PUT", f"/repos/{login}/{REPO}/actions/secrets/{name}",
         {"encrypted_value": base64.b64encode(sealed).decode(), "key_id": key["key_id"]})


def push_secrets(token, login, settings):
    acc, tok = (settings.get("cf_account") or "").strip(), (settings.get("cf_token") or "").strip()
    if acc and tok:
        set_secret(token, login, "CF_ACCOUNT_ID", acc)
        set_secret(token, login, "CF_API_TOKEN", tok)
        return True
    return False


def dispatch(token, login, branch, kind, script_rel, preview, mode):
    tag = uuid.uuid4().hex[:10]
    body = {"ref": branch, "inputs": {"kind": kind, "script": script_rel, "preview": "yes" if preview else "no",
                                      "mode": mode, "tag": tag}}
    for attempt in range(8):
        st, js = net.send_json(f"{API}/repos/{login}/{REPO}/actions/workflows/{WORKFLOW}/dispatches", body,
                               headers=_h(token), timeout=30)
        if st == 204:
            break
        time.sleep(4)
    else:
        raise CloudError(f"Cloud kaam shuru nahi hua ({st}). Repo ke 'Actions' tab mein workflows ON karein.")
    for _ in range(40):
        time.sleep(3)
        st, js = net.get_json(f"{API}/repos/{login}/{REPO}/actions/workflows/{WORKFLOW}/runs?event=workflow_dispatch&per_page=10",
                              headers=_h(token))
        for r in (js.get("workflow_runs") or []):
            if tag in (r.get("display_title") or "") or tag in (r.get("name") or ""):
                return r["id"]
    raise CloudError("Cloud run nahi mila. GitHub par Actions tab check karein.")


def status(token, login, run_id):
    st, run = _req(token, "GET", f"/repos/{login}/{REPO}/actions/runs/{run_id}")
    st, jobs = _req(token, "GET", f"/repos/{login}/{REPO}/actions/runs/{run_id}/jobs")
    steps = []
    for j in jobs.get("jobs", []):
        for s in j.get("steps", []):
            steps.append(dict(name=s["name"], status=s["status"], conclusion=s.get("conclusion")))
    return dict(status=run["status"], conclusion=run.get("conclusion"), steps=steps, url=run.get("html_url"))


def cancel(token, login, run_id):
    try:
        _req(token, "POST", f"/repos/{login}/{REPO}/actions/runs/{run_id}/cancel", {}, ok=(202, 200, 409))
    except CloudError:
        pass


def download(token, login, run_id, dest):
    st, js = _req(token, "GET", f"/repos/{login}/{REPO}/actions/runs/{run_id}/artifacts")
    arts = [a for a in js.get("artifacts", []) if a["name"] == "result"]
    if not arts:
        raise CloudError("Cloud par result file nahi bani (shayad error aaya). GitHub Actions log dekhein.")
    url = arts[0]["archive_download_url"]
    st, h, b = net.request(url, headers=_h(token), follow=False, timeout=60)
    loc = h.get("Location") or h.get("location")
    if st in (301, 302, 303, 307, 308) and loc:
        st, h, b = net.request(loc, headers={}, timeout=900, retries=4)   # NO auth on the redirect target
    if st != 200:
        raise CloudError(f"Result download nahi hua ({st}).")
    if os.path.exists(dest):
        shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        for m in z.namelist():
            target = os.path.normpath(os.path.join(dest, m))
            if not target.startswith(os.path.normpath(dest)):
                continue
            if m.endswith("/"):
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(m) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
    return dest
