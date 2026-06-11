#!/usr/bin/env python3
"""Audit furigana (ruby) readings produced by add-furigana.py / pykakasi.

pykakasi has no contextual analysis, so it routinely mislabels multi-reading
kanji. This tool flags the failure modes we have actually hit, for manual
review — it does not rewrite anything.

Usage:
  python3 tools/audit-furigana.py ep020              # one episode
  python3 tools/audit-furigana.py                    # all scripts/ep*.json
  python3 tools/audit-furigana.py --readings         # also dump every distinct
                                                     # base=reading pair for review

Exits non-zero if any suspicious reading is found.
"""

import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_DIR = os.path.join(ROOT, "scripts")

RUBY = re.compile(r"<ruby>([^<]+)<rt>([^<]+)</rt></ruby>")
DIGITS = set("0123456789０１２３４５６７８９")
KANJI_NUMERALS = set("一二三四五六七八九十百千")
HIRAGANA = re.compile(r"[぀-ゟ]+$")

# Days 1-10 take special readings; furigana must cover digit+日 together.
DATE_READING = {"1": "ついたち", "2": "ふつか", "3": "みっか", "4": "よっか",
                "5": "いつか", "6": "むいか", "7": "なのか", "8": "ようか",
                "9": "ここのか", "10": "とおか"}

# Readings pykakasi has emitted before that are wrong in (nearly) any context.
KNOWN_BAD = {
    ("止まり", "どまり"): "とまり (rendaku only inside compounds)",
    ("今年", "こんねん"): "ことし",
    ("万人", "ばんにん"): "まんにん",
    ("間に", "まに"): "あいだに (unless 間に合う)",
    ("分く", "わく"): "mis-split: should be 分(ふん) + く",
    ("時間走", "じかんそう"): "mis-split: should be 時間(じかん) + 走(はし)",
}


def plain_before(html, pos):
    """Last plain-text character before pos, with tags/rt stripped."""
    s = re.sub(r"<rt>[^<]*</rt>", "", html[:pos])
    s = re.sub(r"<[^>]+>", "", s)
    return s[-1] if s else ""


def audit_ruby(html, where, findings):
    # date readings: bare 日=にち right after a standalone day number 1-10
    for m in re.finditer(r"(?<![0-9０-９])([1-9]|10)<ruby>日<rt>にち</rt></ruby>", html):
        findings.append(f"{where}: {m.group(1)}日=にち — should be "
                        f"<ruby>{m.group(1)}日<rt>{DATE_READING[m.group(1)]}</rt></ruby>")
    for m in RUBY.finditer(html):
        base, rt = m.group(1), m.group(2)
        prev = plain_before(html, m.start())
        ctx = f"…{prev}{base}({rt})"
        if (base, rt) in KNOWN_BAD:
            findings.append(f"{where}: {ctx} — expected {KNOWN_BAD[(base, rt)]}")
            continue
        # okurigana mismatch: trailing kana of base must be a suffix of rt
        tail = HIRAGANA.search(base)
        if tail and not rt.endswith(tail.group(0)):
            findings.append(f"{where}: {ctx} — base/rt okurigana mismatch")
        if base == "人" and rt == "にん" and prev not in DIGITS and prev not in "何約数":
            findings.append(f"{where}: {ctx} — 人 after a verb/の reads ひと")
        if base == "時" and rt == "とき" and prev in DIGITS:
            findings.append(f"{where}: {ctx} — clock time reads じ")
        if base == "日" and rt == "にち" and prev not in DIGITS \
                and prev not in KANJI_NUMERALS:
            findings.append(f"{where}: {ctx} — 〜の日/〜い日 reads ひ")
        if base == "間" and rt == "かん" and prev == "の":
            findings.append(f"{where}: {ctx} — 〜の間 reads あいだ")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dump_readings = "--readings" in sys.argv
    if args:
        files = [os.path.join(SCRIPT_DIR, f"{a}.json") for a in args]
    else:
        files = sorted(f for f in glob.glob(os.path.join(SCRIPT_DIR, "ep*.json"))
                       if "timing" not in f)

    findings, pairs = [], {}
    for path in files:
        name = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        for i, seg in enumerate(d.get("segments", [])):
            ruby = seg.get("ruby")
            if not ruby:
                continue
            audit_ruby(ruby, f"{name} seg{i}", findings)
            for m in RUBY.finditer(ruby):
                pairs.setdefault((m.group(1), m.group(2)), name)

    if dump_readings:
        print(f"--- {len(pairs)} distinct base=reading pairs ---")
        for (base, rt), name in sorted(pairs.items(), key=lambda x: x[0][1]):
            print(f"  {base}={rt}  ({name})")
        # bases with multiple readings deserve a second look
        by_base = {}
        for (base, rt) in pairs:
            by_base.setdefault(base, []).append(rt)
        multi = {b: r for b, r in by_base.items() if len(r) > 1}
        if multi:
            print("--- bases with multiple readings (verify each) ---")
            for base, rts in sorted(multi.items()):
                print(f"  {base}: {', '.join(rts)}")

    if findings:
        # de-dup: replay/slow segments repeat the same sentence
        for line in dict.fromkeys(findings):
            print(f"  SUSPECT {line}")
        print(f"\n{len(findings)} suspicious reading(s) in {len(files)} file(s).")
        sys.exit(1)
    print(f"All {len(files)} file(s) clean.")


if __name__ == "__main__":
    main()
