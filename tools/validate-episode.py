#!/usr/bin/env python3
"""Validate episode JSON schema + content rules.

Usage:
  python3 tools/validate-episode.py ep007                 # one episode
  python3 tools/validate-episode.py ep001 ep002 ep003     # multiple
  python3 tools/validate-episode.py                       # all scripts/ep*.json
  python3 tools/validate-episode.py --staged              # files staged in git

Exits non-zero on any failure. Prints a per-file pass/fail summary.
"""

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_DIR = os.path.join(ROOT, "scripts")

REQUIRED_TOP = ["episode", "title", "titleZh", "titleEn", "date", "source", "level",
                "characters", "segments", "vocabulary", "grammar", "practiceZh"]
REQUIRED_SPEAKERS = ["host", "news", "slow", "vocab"]
# nhNNN = the all-Japanese show: a Japanese "guide" talks around two news readings.
NH_SPEAKERS = ["guide", "news"]
CHAR_FIELDS = ["voice", "role", "lang", "rate"]
VOCAB_FIELDS = ["ja", "reading", "en", "zh"]
GRAMMAR_FIELDS = ["pattern", "meaning", "meaningZh", "formation", "example",
                  "translation", "note", "noteZh", "level"]
LEVELS = {"N5-N4", "N4-N3", "N3-N2"}

JA_CHAR_RE = re.compile(r"[぀-ゟ゠-ヿ一-鿿]")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CONTENT_VERSION_RE = re.compile(r"^\d{10}$")


def add(errs, path, msg):
    errs.append(f"{path}: {msg}")


def validate(ep_path, errs):
    name = os.path.basename(ep_path)
    try:
        with open(ep_path, "r", encoding="utf-8") as f:
            d = json.load(f)
    except json.JSONDecodeError as e:
        add(errs, name, f"invalid JSON ({e})")
        return
    except FileNotFoundError:
        add(errs, name, "file not found")
        return

    for k in REQUIRED_TOP:
        if k not in d:
            add(errs, name, f"missing top-level field '{k}'")

    if "episode" in d and not isinstance(d["episode"], int):
        add(errs, name, "'episode' must be int")
    if "date" in d and not DATE_RE.match(str(d.get("date", ""))):
        add(errs, name, f"'date' must be YYYY-MM-DD, got {d.get('date')!r}")
    if "level" in d and d["level"] not in LEVELS:
        add(errs, name, f"'level' must be one of {sorted(LEVELS)}, got {d['level']!r}")
    if "contentVersion" in d and not CONTENT_VERSION_RE.match(str(d["contentVersion"])):
        add(errs, name, f"'contentVersion' must be 10 digits (YYYYMMDDNN), got {d['contentVersion']!r}")

    is_nh = name.startswith("nh")
    chars = d.get("characters", {})
    for sp in (NH_SPEAKERS if is_nh else REQUIRED_SPEAKERS):
        if sp not in chars:
            add(errs, name, f"characters missing '{sp}'")
            continue
        for f in CHAR_FIELDS:
            if f not in chars[sp]:
                add(errs, name, f"characters.{sp} missing '{f}'")

    if is_nh:
        if "host" in chars:
            add(errs, name, "nh episodes have no English host (use 'guide')")
    elif chars.get("host", {}).get("lang") != "en":
        add(errs, name, "characters.host.lang must be 'en'")
    for sp in ("guide", "news", "slow", "vocab"):
        if chars.get(sp, {}).get("lang") not in (None, "ja"):
            add(errs, name, f"characters.{sp}.lang must be 'ja'")

    ja_speakers = {sp for sp, c in chars.items() if c.get("lang") == "ja"}

    zh_covered = {"今日のニュースです。", "また明日。"}
    for entry in d.get("practiceZh", []) or []:
        if isinstance(entry, str) and "\n" in entry:
            zh_covered.add(entry.split("\n")[0].strip())

    segs = d.get("segments", [])
    if not isinstance(segs, list) or not segs:
        add(errs, name, "'segments' must be a non-empty list")
    for i, s in enumerate(segs or []):
        if "speaker" not in s or "text" not in s:
            add(errs, name, f"segments[{i}] missing speaker/text")
            continue
        sp = s["speaker"]
        if sp not in chars:
            add(errs, name, f"segments[{i}] unknown speaker '{sp}'")
        text = s["text"]

        if sp == "host":
            if JA_CHAR_RE.search(text):
                add(errs, name, f"segments[{i}] host has Japanese characters: {text[:40]!r}")
            # heuristic: catch romaji of Japanese words by looking for tell-tale capitalised words
            # quoted between quotes/apostrophes — host should describe meanings, not pronounce
            for m in re.finditer(r"'([A-Z][a-z]{2,})'", text):
                add(errs, name, f"segments[{i}] host has suspected romaji {m.group(0)!r} — describe meaning, don't pronounce")

        if sp in ja_speakers and "ruby" not in s:
            add(errs, name, f"segments[{i}] {sp}-segment missing 'ruby' field — run add-furigana.py")

        # /zh/ pages show a Chinese line under every news sentence: from its own
        # "zh" field, or from practiceZh when the breakdown covers the sentence.
        if sp == "news" and not s.get("zh") and text.strip() not in zh_covered:
            add(errs, name, f"segments[{i}] news sentence has no Chinese translation — add a 'zh' field: {text[:30]!r}")
        # English pages show an English line under every news sentence.
        if sp == "news" and not s.get("en") and text.strip() not in ("今日のニュースです。", "また明日。"):
            add(errs, name, f"segments[{i}] news sentence has no English translation — add an 'en' field: {text[:30]!r}")
        # The all-Japanese show translates the talk too: it is the hardest part.
        if sp == "guide" and (not s.get("zh") or not s.get("en")):
            add(errs, name, f"segments[{i}] guide line needs both 'zh' and 'en' fields: {text[:30]!r}")

    vocab = d.get("vocabulary", [])
    if not isinstance(vocab, list):
        add(errs, name, "'vocabulary' must be a list")
    else:
        for i, v in enumerate(vocab):
            for f in VOCAB_FIELDS:
                if f not in v:
                    add(errs, name, f"vocabulary[{i}] missing '{f}'")

    grammar = d.get("grammar", [])
    if not isinstance(grammar, list):
        add(errs, name, "'grammar' must be a list")
    else:
        for i, g in enumerate(grammar):
            for f in GRAMMAR_FIELDS:
                if f not in g:
                    add(errs, name, f"grammar[{i}] missing '{f}'")

    if not isinstance(d.get("practiceZh", []), list):
        add(errs, name, "'practiceZh' must be a list")


def staged_episode_jsons():
    try:
        out = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=ROOT, text=True,
        )
    except subprocess.CalledProcessError:
        return []
    files = []
    for line in out.splitlines():
        if line.startswith(("scripts/ep", "scripts/nh")) and line.endswith(".json") and not line.endswith(".timing.json"):
            files.append(os.path.join(ROOT, line))
    return files


def main():
    args = sys.argv[1:]
    if args == ["--staged"]:
        paths = staged_episode_jsons()
        if not paths:
            print("validate-episode: no staged episode JSONs")
            return 0
    elif args:
        paths = []
        for a in args:
            stem = a if a.endswith(".json") else f"{a}.json"
            paths.append(os.path.join(SCRIPT_DIR, os.path.basename(stem)))
    else:
        paths = sorted(
            os.path.join(SCRIPT_DIR, f)
            for f in os.listdir(SCRIPT_DIR)
            if f.startswith(("ep", "nh")) and f.endswith(".json") and not f.endswith(".timing.json")
        )

    all_errs = []
    for p in paths:
        errs = []
        validate(p, errs)
        if errs:
            for e in errs:
                print(f"  FAIL {e}")
            all_errs.extend(errs)
        else:
            print(f"  OK   {os.path.basename(p)}")

    if all_errs:
        print(f"\n{len(all_errs)} error(s) across {len(paths)} file(s).")
        return 1
    print(f"\nAll {len(paths)} file(s) passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
