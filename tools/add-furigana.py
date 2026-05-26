#!/usr/bin/env python3
"""Add furigana (ruby HTML) to Japanese segments in episode scripts."""

import json
import os
import sys
from pykakasi import kakasi

ROOT = os.path.dirname(os.path.dirname(__file__))
SCRIPT_DIR = os.path.join(ROOT, "scripts")

kks = kakasi()


def has_kanji(text):
    return any("一" <= c <= "鿿" for c in text)


def to_ruby_html(text, vocab_list=None):
    """Convert Japanese text to HTML with <ruby> tags and vocab highlights."""
    vocab_map = {}
    if vocab_list:
        for v in sorted(vocab_list, key=lambda x: -len(x["ja"])):
            vocab_map[v["ja"]] = v

    tokens = kks.convert(text)
    html_parts = []
    i = 0
    while i < len(tokens):
        orig = tokens[i]["orig"]
        hira = tokens[i]["hira"]

        # Check if current position starts a vocab word
        remaining_text = "".join(t["orig"] for t in tokens[i:])
        matched_vocab = None
        for vja, vdata in vocab_map.items():
            if remaining_text.startswith(vja):
                matched_vocab = vdata
                break

        if matched_vocab:
            vja = matched_vocab["ja"]
            inner_html = ""
            consumed = ""
            while i < len(tokens) and len(consumed) < len(vja):
                t = tokens[i]
                if has_kanji(t["orig"]) and t["orig"] != t["hira"]:
                    inner_html += f'<ruby>{t["orig"]}<rt>{t["hira"]}</rt></ruby>'
                else:
                    inner_html += t["orig"]
                consumed += t["orig"]
                i += 1
            en = matched_vocab["en"].replace('"', "&quot;")
            reading = matched_vocab["reading"]
            html_parts.append(
                f'<span class="vw" data-ja="{vja}" '
                f'data-reading="{reading}" data-en="{en}">'
                f"{inner_html}</span>"
            )
        else:
            if has_kanji(orig) and orig != hira:
                html_parts.append(f"<ruby>{orig}<rt>{hira}</rt></ruby>")
            else:
                html_parts.append(orig)
            i += 1

    return "".join(html_parts)


def process_episode(ep_path):
    with open(ep_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    vocab_list = data.get("vocabulary", [])
    ja_speakers = set()
    for name, char in data["characters"].items():
        if char.get("lang") == "ja":
            ja_speakers.add(name)

    changed = False
    for seg in data["segments"]:
        if seg["speaker"] in ja_speakers:
            ruby = to_ruby_html(seg["text"], vocab_list)
            if ruby != seg.get("ruby"):
                seg["ruby"] = ruby
                changed = True

    if changed:
        with open(ep_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  Updated: {os.path.basename(ep_path)}")
    else:
        print(f"  No changes: {os.path.basename(ep_path)}")


def main():
    files = sorted(f for f in os.listdir(SCRIPT_DIR) if f.endswith(".json") and not f.endswith(".timing.json"))
    if len(sys.argv) > 1:
        files = [f"{sys.argv[1]}.json"]

    print("Adding furigana...")
    for f in files:
        process_episode(os.path.join(SCRIPT_DIR, f))
    print("Done!")


if __name__ == "__main__":
    main()
