"""Network helpers: timeouts, retries, DNS-over-HTTPS fallback, simple errors."""
import socket, json, time, ssl, urllib.request, urllib.error, urllib.parse

_orig_getaddrinfo = socket.getaddrinfo
_doh_cache = {}


def _doh(host):
    if host in _doh_cache:
        return _doh_cache[host]
    for ip, hdr in (("1.1.1.1", "cloudflare-dns.com"), ("8.8.8.8", "dns.google")):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE  # IP-literal DoH endpoint; answer is only an address hint
            req = urllib.request.Request(f"https://{ip}/dns-query?name={urllib.parse.quote(host)}&type=A",
                                         headers={"accept": "application/dns-json", "host": hdr})
            with urllib.request.urlopen(req, timeout=6, context=ctx) as r:
                data = json.loads(r.read().decode())
            ips = [a["data"] for a in data.get("Answer", []) if a.get("type") == 1]
            if ips:
                _doh_cache[host] = ips
                return ips
        except Exception:
            continue
    return []


def _patched(host, port, *a, **k):
    try:
        return _orig_getaddrinfo(host, port, *a, **k)
    except socket.gaierror:
        ips = _doh(host) if isinstance(host, str) else []
        if not ips:
            raise
        return _orig_getaddrinfo(ips[0], port, *a, **k)


def install_dns_fallback():
    if socket.getaddrinfo is not _patched:
        socket.getaddrinfo = _patched


class NetError(Exception):
    pass


def request(url, method="GET", headers=None, data=None, timeout=60, retries=3, follow=True, raw=False):
    """Returns (status, headers, body_bytes). Retries on network errors / 5xx / 429."""
    install_dns_fallback()
    headers = dict(headers or {})
    headers.setdefault("User-Agent", "InkEngine/1.0")
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, method=method, headers=headers)
            if follow:
                opener = urllib.request.build_opener()
            else:
                class NoRedirect(urllib.request.HTTPRedirectHandler):
                    def redirect_request(self, *a, **k):
                        return None
                opener = urllib.request.build_opener(NoRedirect)
            with opener.open(req, timeout=timeout) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            body = e.read() if hasattr(e, "read") else b""
            if e.code in (301, 302, 303, 307, 308) and not follow:
                return e.code, dict(e.headers), body
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 * (attempt + 1) + (5 if e.code == 429 else 0))
                last = e
                continue
            return e.code, dict(e.headers or {}), body
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise NetError(f"Internet se rabta nahi ho saka ({type(last).__name__}: {last}). "
                   "Internet check karein, phir dobara koshish karein.")


def get_json(url, headers=None, timeout=60, retries=3):
    st, h, b = request(url, headers=headers, timeout=timeout, retries=retries)
    try:
        return st, json.loads(b.decode() or "{}")
    except Exception:
        return st, {"_raw": b[:300].decode(errors="ignore")}


def send_json(url, obj, method="POST", headers=None, timeout=90, retries=3):
    h = dict(headers or {})
    h["Content-Type"] = "application/json"
    st, hh, b = request(url, method=method, headers=h, data=json.dumps(obj).encode(), timeout=timeout, retries=retries)
    try:
        return st, json.loads(b.decode() or "{}")
    except Exception:
        return st, {"_raw": b[:300].decode(errors="ignore")}
