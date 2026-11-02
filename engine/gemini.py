"""Free Gemini TEXT API (script writing)."""
import json
from . import net

BASE = "https://generativelanguage.googleapis.com/v1beta"
PREFERRED = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-lite-latest", "gemini-2.5-flash-lite"]


class GeminiError(Exception):
    pass


def _call(model, key, prompt, temperature=0.9):
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "responseMimeType": "application/json",
                                 "maxOutputTokens": 32768}}
    st, data = net.send_json(f"{BASE}/models/{model}:generateContent", body,
                             headers={"x-goog-api-key": key}, timeout=240, retries=2)
    return st, data


def generate(key, prompt, temperature=0.9):
    if not key:
        raise GeminiError("Gemini key nahi hai. Settings mein key daalein, ya 'Copy prompt' use karein.")
    last = ""
    for m in PREFERRED:
        st, data = _call(m, key, prompt, temperature)
        if st == 200:
            try:
                parts = data["candidates"][0]["content"]["parts"]
                return "".join(p.get("text", "") for p in parts)
            except Exception:
                last = f"{m}: khaali jawab"
                continue
        msg = (data.get("error") or {}).get("message", "") if isinstance(data, dict) else ""
        if st in (400, 401, 403) and "API key" in msg:
            raise GeminiError("Gemini key ghalat hai. aistudio.google.com se nayi key bana kar Settings mein daalein.")
        if st == 429:
            last = "Gemini ka free limit abhi khatam (429). 1-2 minute baad dobara, ya 'Copy prompt' use karein."
            continue
        last = f"{m}: {st} {msg[:150]}"
    raise GeminiError("Gemini se script nahi bani. " + last)


def test_key(key):
    try:
        st, data = net.get_json(f"{BASE}/models?pageSize=5", headers={"x-goog-api-key": key}, timeout=20, retries=1)
        return st == 200
    except Exception:
        return False
