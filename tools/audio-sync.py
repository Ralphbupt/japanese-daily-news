#!/usr/bin/env python3
"""Upload episode mp3s to R2, where the site and the RSS feeds play them from.

    python3 tools/audio-sync.py epNNN [nhNNN ...]   upload these episodes
    python3 tools/audio-sync.py                     upload every new or changed mp3 in audio/
    python3 tools/audio-sync.py --dry               only say what would be uploaded

audio/epNNN.mp3 goes to the jpnotes-audio bucket as podcast/epNNN.mp3, served at
https://audio.jpnotes.dev/podcast/epNNN.mp3 (podcast.jpnotes.dev/audio/* redirects
there). A file is sent when the bucket has no object of that name or its MD5
differs (a re-recorded episode keeps its name, so objects are cached for a day).

It also records each file's size in site/src/data/audio-bytes.json: the RSS
enclosure needs the length, and the mp3s are not in git. Commit that file with
the episode. Run this BEFORE pushing: pages only point at audio that is already
in the bucket.

Auth: $CLOUDFLARE_API_TOKEN (an API token with R2 edit; the cron server keeps it
in its crontab), else the local wrangler login (`npx wrangler login`).
$CLOUDFLARE_ACCOUNT_ID is optional.
"""
import argparse, concurrent.futures as cf, hashlib, json, os, re, subprocess, sys, threading, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIO = ROOT / "audio"
SIZES = ROOT / "site/src/data/audio-bytes.json"
BUCKET = "jpnotes-audio"
PREFIX = "podcast/"
API = "https://api.cloudflare.com/client/v4"
CACHE = "public, max-age=86400"

_tok = {"value": None}
_tok_lock = threading.Lock()


def token(stale=None):
    """The API token from the environment, or wrangler's OAuth token (about an hour
    long; a 401 comes back here with the token that failed)."""
    if os.environ.get("CLOUDFLARE_API_TOKEN"):
        return os.environ["CLOUDFLARE_API_TOKEN"]
    with _tok_lock:
        if _tok["value"] and _tok["value"] != stale:
            return _tok["value"]
        subprocess.run(["npx", "--yes", "wrangler", "whoami"], cwd=ROOT, capture_output=True, timeout=180)   # refreshes it
        conf = (Path.home() / "Library/Preferences/.wrangler/config/default.toml").read_text()
        _tok["value"] = re.search(r'oauth_token\s*=\s*"([^"]+)"', conf).group(1)
        return _tok["value"]


def call(method, path, tok, data=None, headers=None):
    for attempt in range(8):
        req = urllib.request.Request(API + path, data=data, method=method,
                                     headers={"Authorization": "Bearer " + tok, "User-Agent": "jdn-audio-sync", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 401 and attempt < 3 and not os.environ.get("CLOUDFLARE_API_TOKEN"):
                tok = token(stale=tok)
                continue
            if e.code in (429, 500, 502, 503, 504) and attempt < 7:
                time.sleep(20 if e.code == 429 else 3 * (attempt + 1))
                continue
            raise RuntimeError(f"{method} {path}: HTTP {e.code} {e.read()[:300]!r}")
        except (urllib.error.URLError, TimeoutError):
            if attempt == 7:
                raise
            time.sleep(3 * (attempt + 1))


def remote(tok, account):
    have, cursor = {}, None
    while True:
        q = "?per_page=1000&prefix=" + urllib.parse.quote(PREFIX) + ("&cursor=" + urllib.parse.quote(cursor) if cursor else "")
        res = call("GET", f"/accounts/{account}/r2/buckets/{BUCKET}/objects{q}", tok)
        for o in res.get("result") or []:
            have[o["key"]] = o.get("etag", "").strip('"')
        info = res.get("result_info") or {}
        cursor = info.get("cursor")
        if not cursor or not info.get("is_truncated"):
            return have


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", help="episode ids (epNNN / nhNNN); none = all of audio/")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    if args.ids:
        paths = [AUDIO / f"{i}.mp3" for i in args.ids]
        missing = [p.name for p in paths if not p.exists()]
        if missing:
            sys.exit("no such file in audio/: " + ", ".join(missing))
    else:
        paths = sorted(AUDIO.glob("*.mp3"))
    files = {PREFIX + p.name: p for p in paths}

    tok = token()
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or call("GET", "/accounts", tok)["result"][0]["id"]
    have = remote(tok, account)
    todo = [k for k, p in files.items() if have.get(k) != hashlib.md5(p.read_bytes()).hexdigest()]
    print(f"{len(files)} local, {len(have)} in the bucket, {len(todo)} to upload", flush=True)

    if not args.dry and todo:
        done, lock, start = [0], threading.Lock(), time.time()

        def send(key):
            with lock:   # stay under the API's 1,200 calls / 5 min
                wait = start + done[0] * 0.27 - time.time()
                done[0] += 1
                n = done[0]
            if wait > 0:
                time.sleep(wait)
            call("PUT", f"/accounts/{account}/r2/buckets/{BUCKET}/objects/{urllib.parse.quote(key)}", tok,
                 files[key].read_bytes(), {"Content-Type": "audio/mpeg", "Cache-Control": CACHE})
            if n % 50 == 0:
                print(f"  {n}/{len(todo)}", flush=True)

        with cf.ThreadPoolExecutor(6) as ex:
            list(ex.map(send, todo))
        print(f"uploaded {len(todo)} files in {int(time.time() - start)} s")
    else:
        for k in todo[:20]:
            print("  ", k)

    if not args.dry:
        sizes = json.loads(SIZES.read_text()) if SIZES.exists() else {}
        sizes.update({p.stem: p.stat().st_size for p in files.values()})
        SIZES.write_text(json.dumps(dict(sorted(sizes.items())), indent=0) + "\n")


if __name__ == "__main__":
    sys.exit(main())
