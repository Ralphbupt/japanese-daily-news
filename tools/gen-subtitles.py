#!/usr/bin/env python3
"""Generate VTT and SRT subtitle files from episode scripts + timing data."""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
SCRIPT_DIR = os.path.join(ROOT, "scripts")
OUT_DIR = os.path.join(ROOT, "subtitles")


def fmt_vtt(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def fmt_srt(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def speaker_label(speaker):
    return {"host": "Host", "news": "News", "slow": "Slow", "vocab": "Vocab"}.get(
        speaker, speaker
    )


def main():
    ep = sys.argv[1] if len(sys.argv) > 1 else None
    os.makedirs(OUT_DIR, exist_ok=True)

    files = sorted(
        f
        for f in os.listdir(SCRIPT_DIR)
        if f.endswith(".json") and not f.endswith(".timing.json")
    )
    if ep:
        files = [f"{ep}.json"]

    for fname in files:
        ep_id = fname.replace(".json", "")
        script_path = os.path.join(SCRIPT_DIR, fname)
        timing_path = os.path.join(SCRIPT_DIR, f"{ep_id}.timing.json")

        with open(script_path, "r", encoding="utf-8") as f:
            script = json.load(f)

        segments = script["segments"]

        if os.path.exists(timing_path):
            with open(timing_path, "r", encoding="utf-8") as f:
                timing = json.load(f)
            timing_segs = timing["segments"]
        else:
            print(f"  {ep_id}: no timing data, skipping (run gen-episode.py first)")
            continue

        if len(timing_segs) != len(segments):
            print(
                f"  {ep_id}: segment count mismatch "
                f"({len(timing_segs)} timing vs {len(segments)} script), skipping"
            )
            continue

        # --- VTT ---
        vtt_lines = ["WEBVTT", ""]
        for i, (seg, t) in enumerate(zip(segments, timing_segs)):
            label = speaker_label(seg["speaker"])
            start = fmt_vtt(t["start"])
            end = fmt_vtt(t["end"])
            text = seg["text"]
            vtt_lines.append(f"{start} --> {end}")
            vtt_lines.append(f"<v {label}>{text}")
            vtt_lines.append("")

        vtt_path = os.path.join(OUT_DIR, f"{ep_id}.vtt")
        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(vtt_lines))

        # --- SRT ---
        srt_lines = []
        for i, (seg, t) in enumerate(zip(segments, timing_segs)):
            label = speaker_label(seg["speaker"])
            start = fmt_srt(t["start"])
            end = fmt_srt(t["end"])
            text = seg["text"]
            srt_lines.append(str(i + 1))
            srt_lines.append(f"{start} --> {end}")
            srt_lines.append(f"[{label}] {text}")
            srt_lines.append("")

        srt_path = os.path.join(OUT_DIR, f"{ep_id}.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))

        print(f"  {ep_id}: {vtt_path}")
        print(f"  {ep_id}: {srt_path}")


if __name__ == "__main__":
    main()
