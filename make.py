"""Command line entry (used by the app and by the cloud).

python make.py video scripts/x.json [--preview] [--mode A|B] [--no-shorts]
python make.py qshorts scripts/shorts/x.json [--mode A|B]
"""
import os, sys, json, argparse

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def load_settings():
    s = {}
    p = os.path.join(ROOT, "settings.json")
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                s = json.load(f)
        except Exception:
            s = {}
    # cloud: secrets come from environment, never from files
    if os.environ.get("CF_ACCOUNT_ID"):
        s["cf_account"] = os.environ["CF_ACCOUNT_ID"]
    if os.environ.get("CF_API_TOKEN"):
        s["cf_token"] = os.environ["CF_API_TOKEN"]
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["video", "qshorts"])
    ap.add_argument("script")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--mode", default=None)
    ap.add_argument("--no-shorts", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    settings = load_settings()
    mode = (a.mode or settings.get("mode") or "A").upper()
    if mode == "B" and not (settings.get("cf_account") and settings.get("cf_token")):
        print("NOTE: Cloudflare key nahi mili - Mode A (drawn) use ho raha hai.")
        mode = "A"
    from engine import pipeline, quickshorts
    try:
        if a.kind == "video":
            pipeline.make_video(a.script, preview=a.preview, mode=mode, settings=settings, out_name=a.out,
                                shorts=not a.no_shorts)
        else:
            quickshorts.render_pair(a.script, mode=mode, settings=settings, out_name=a.out)
    except KeyboardInterrupt:
        print("STOPPED")
        sys.exit(2)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
